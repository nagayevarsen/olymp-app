"""Весь путь умного поиска: от формы до готовых карточек.

Метод run() отдаёт события по одному, и страница сразу показывает прогресс.
Если живой поиск недоступен, пользователь получает сохранённые результаты для демо.
"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from pathlib import Path

from catalog.dates import STATUS_CLOSED, current_season, get_status
from smart_search.consensus import TRUST_MODELS_AGREE, TRUST_UNCONFIRMED, TRUST_VERIFIED, apply_verdict, merge_answers
from smart_search.models import parse_answer
from smart_search.official import is_official_url
from smart_search.prompts import ROLES, build_prompt
from smart_search.providers import SearchTask
from smart_search.verify import find_confirmed_variant

logger = logging.getLogger(__name__)

DEMO_FILE = Path(__file__).parent.parent / "data" / "demo_results.json"

# Лимиты времени в секундах.
SEARCH_TIMEOUT_SECONDS = 60
VERIFY_TIMEOUT_SECONDS = 25

MAX_PAGES_TO_VERIFY = 12
MAX_PARALLEL_SEARCHES = 3

TRUST_ORDER = {TRUST_VERIFIED: 0, TRUST_MODELS_AGREE: 1, TRUST_UNCONFIRMED: 2}


def load_demo_results(today, path=DEMO_FILE):
    """Читает сохранённые результаты. Прошедшие события код убирает и здесь."""
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    return [item for item in items if not is_expired(item, today)]


def is_expired(item, today):
    """Проверяет, что дедлайн уже прошёл. Решает код, а не ИИ."""
    return get_status(item.get("registration_start"), item.get("registration_deadline"), today) == STATUS_CLOSED


def fits_person(item, request):
    """Убирает событие, если оно точно не подходит по классу или возрасту."""
    grade_from, grade_to = item.get("grade_from"), item.get("grade_to")
    if grade_from is not None and request.grade < grade_from:
        return False
    if grade_to is not None and request.grade > grade_to:
        return False
    if request.age is not None:
        age_from, age_to = item.get("age_from"), item.get("age_to")
        if age_from is not None and request.age < age_from:
            return False
        if age_to is not None and request.age > age_to:
            return False
    return True


def sort_key(item):
    """Сначала самое надёжное, внутри — ближайший дедлайн."""
    return (TRUST_ORDER[item["trust"]], item["registration_deadline"] or "9999", item["title"])


def step(name, state):
    """Событие прогресса для экрана."""
    return {"type": "step", "step": name, "state": state}


class SearchService:
    """Собирает вместе модели, проверку страниц, кэш и лимиты."""

    def __init__(self, providers, make_fetch, domains, cache, daily_limit, subject_names, source, today_func):
        self.providers = providers
        self.make_fetch = make_fetch  # создаёт функцию открытия страницы
        self.domains = domains
        self.cache = cache
        self.daily_limit = daily_limit
        self.subject_names = subject_names
        self.source = source  # live — настоящий ИИ, stub — заглушки
        self.today_func = today_func
        self.slots = threading.BoundedSemaphore(MAX_PARALLEL_SEARCHES)

    def run(self, request):
        """Главный метод: отдаёт события прогресса, а в конце результат."""
        today = self.today_func()
        season = current_season(today)
        # Возраста в ключе нет: он не уходит в ИИ и не хранится в кэше.
        key = (today, season, request.grade, request.country, request.subjects)

        cached = self.cache.get(key)
        if cached is not None:
            yield self.final(request, cached, today, "cache", None)
            return

        if not self.providers:
            yield self.demo(today, "unavailable")
            return
        if not self.slots.acquire(blocking=False):
            yield self.demo(today, "busy")
            return

        try:
            if not self.daily_limit.try_take(today):
                yield self.demo(today, "daily_limit")
                return

            answers = None
            for event in self.ask_models(request, today, season):
                if isinstance(event, list):
                    answers = event
                else:
                    yield event

            if answers is None:
                yield self.demo(today, "unavailable")
                return

            yield step("compare", "running")
            items = self.compare(answers, today, season)
            yield step("compare", "done")

            yield step("verify", "running")
            results = self.verify(items, today, season)
            yield step("verify", "done")

            self.cache.put(key, results)
            yield self.final(request, results, today, self.source, None)
        except Exception:
            # Причину пишем в журнал без условий поиска, а пользователю показываем запасной режим.
            logger.exception("Умный поиск завершился ошибкой")
            yield self.demo(today, "unavailable")
        finally:
            self.slots.release()

    def ask_models(self, request, today, season):
        """Параллельно отправляет задания всем моделям. Прогресс идёт по мере ответов."""
        tasks = {}
        for role in ROLES:
            yield step(f"role_{role}", "running")
            prompt = build_prompt(role, request, today, season, self.subject_names(request.subjects))
            tasks[role] = SearchTask(role=role, prompt=prompt, today=today, season=season)

        left_per_role = {role: len(self.providers) for role in ROLES}
        answers = []
        answered_providers = 0

        # Если время вышло, мы просто не ждём оставшиеся ответы.
        executor = ThreadPoolExecutor(max_workers=len(ROLES) * len(self.providers))
        try:
            futures = {
                executor.submit(provider.search, task): (provider, role)
                for role, task in tasks.items()
                for provider in self.providers
            }
            try:
                for future in as_completed(futures, timeout=SEARCH_TIMEOUT_SECONDS):
                    provider, role = futures[future]
                    try:
                        for candidate in parse_answer(future.result()):
                            answers.append((provider.name, candidate))
                        answered_providers += 1
                    except Exception as error:
                        # Одна модель сломалась: остальные ответы всё равно используем.
                        # Текст ошибки не пишем: он может содержать условия поиска.
                        logger.warning("Модель %s не ответила: %s", provider.name, type(error).__name__)
                    left_per_role[role] -= 1
                    if left_per_role[role] == 0:
                        yield step(f"role_{role}", "done")
            except FuturesTimeout:
                logger.warning("Вышло время ожидания ответов от моделей")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        for role, left in left_per_role.items():
            if left > 0:
                yield step(f"role_{role}", "done")

        # Если не ответила ни одна модель, поиск считается недоступным.
        if answered_providers > 0:
            yield answers

    def compare(self, answers, today, season):
        """Сверяет ответы и убирает то, что показывать нельзя. Это делает код."""
        official = [
            (provider, candidate) for provider, candidate in answers
            if is_official_url(candidate["official_url"], self.domains)
        ]
        items = []
        for item in merge_answers(official):
            # Чужой сезон: дата относится к другому учебному году.
            if item["season"] is not None and item["season"] != season:
                continue
            # Если все варианты дедлайна прошли, событие просрочено.
            deadlines = [variant["deadline"] for variant in item["variants"]]
            if deadlines and all(deadline < today.isoformat() for deadline in deadlines):
                continue
            items.append(item)
        return items

    def verify(self, items, today, season):
        """Параллельно открывает официальные страницы и выставляет уровень доверия."""
        fetch = self.make_fetch(today, self.domains)
        to_check = items[:MAX_PAGES_TO_VERIFY]
        confirmed = {}

        executor = ThreadPoolExecutor(max_workers=5)
        try:
            futures = {
                executor.submit(find_confirmed_variant, item, fetch, season): index
                for index, item in enumerate(to_check)
            }
            try:
                for future in as_completed(futures, timeout=VERIFY_TIMEOUT_SECONDS):
                    confirmed[futures[future]] = future.result()
            except FuturesTimeout:
                logger.warning("Вышло время проверки страниц")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        results = [apply_verdict(item, confirmed.get(index)) for index, item in enumerate(items)]
        return sorted((item for item in results if not is_expired(item, today)), key=sort_key)

    def final(self, request, results, today, source, notice):
        """Готовит ответ: убирает просроченное и то, что не подходит человеку."""
        shown = [item for item in results if not is_expired(item, today) and fits_person(item, request)]
        return {"type": "result", "source": source, "notice": notice, "results": shown}

    def demo(self, today, notice):
        """Запасной режим: заранее сохранённые результаты с честной пометкой."""
        return {"type": "result", "source": "demo", "notice": notice, "results": load_demo_results(today)}
