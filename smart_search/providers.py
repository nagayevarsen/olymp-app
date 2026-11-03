"""Слой над сервисами ИИ.

Остальной код знает только про метод search(), поэтому новый сервис добавляется
одним классом. Заглушки работают без ключей и денег и нужны для разработки и тестов.
"""

import json
import time
from dataclasses import dataclass
from datetime import date, timedelta

from smart_search.prompts import ROLES


@dataclass(frozen=True)
class SearchTask:
    """Одно задание для ИИ."""

    role: str
    prompt: str
    today: date
    season: str


class Provider:
    """Общий вид сервиса ИИ. Новый сервис должен реализовать только search()."""

    name = "base"

    def search(self, task):
        """Выполняет задание и возвращает текст ответа модели."""
        raise NotImplementedError


class StubProvider(Provider):
    """Заглушка: отвечает заранее заготовленными выдуманными записями.

    Записи подобраны так, чтобы проверить каждый случай: подтверждённую дату,
    согласие моделей, спор моделей, неофициальный сайт, прошедший дедлайн и чужой сезон.
    """

    def __init__(self, name, variant, delay_seconds=0):
        self.name = name
        self.variant = variant
        self.delay_seconds = delay_seconds

    def search(self, task):
        # Настоящая модель думает долго. Задержка показывает, как выглядит прогресс:
        # роли завершаются по очереди, а не все сразу.
        time.sleep(self.delay_seconds * (list(ROLES).index(task.role) + 1))
        return json.dumps(stub_answer(task, self.variant), ensure_ascii=False)


STUB_SITE = "https://example.org"


def stub_record(slug, title, task, deadline_days, **changes):
    """Создаёт запись заглушки. Дедлайн считается от сегодняшнего дня."""
    deadline = task.today + timedelta(days=deadline_days)
    record = {
        "title": f"ПРИМЕР: {title}",
        "grade_from": 7,
        "grade_to": 11,
        "age_from": None,
        "age_to": None,
        "subjects": ["Математика"],
        "registration_start": (task.today - timedelta(days=5)).isoformat(),
        "registration_deadline": deadline.isoformat(),
        "event_date": (task.today + timedelta(days=40)).isoformat(),
        "season": task.season,
        "summary": "Выдуманная запись режима разработки. Такого события не существует.",
        "official_url": f"{STUB_SITE}/{slug}",
        "date_quote": f"Регистрация открыта до {deadline.strftime('%d.%m.%Y')}",
    }
    record.update(changes)
    return record


def stub_answer(task, variant):
    """Возвращает записи заглушки для роли. Варианты a и b иногда расходятся."""
    if task.role == "official":
        records = [
            stub_record("confirmed", "Олимпиада с подтверждённой датой", task, 10),
            stub_record("agree", "Олимпиада, где согласны две модели", task, 12),
        ]
        return records
    if task.role == "international":
        return [stub_record("one-model", "Международная олимпиада от одной модели", task, 20)] if variant == "a" else []
    if task.role == "university":
        return [
            stub_record("past", "Олимпиада с прошедшим дедлайном", task, -3),
            stub_record("elsewhere", "Олимпиада без официальной ссылки", task, 8, official_url="https://unofficial.example.net/page"),
        ]
    return [
        stub_record("old-season", "Конкурс прошлого сезона", task, 15, season="2020-2021"),
        stub_record(
            "no-date", "Конкурс без даты на странице", task, 15,
            registration_start=None, registration_deadline=None, date_quote=None,
        ),
        stub_record("dispute", "Конкурс, о дате которого модели спорят", task, 18 if variant == "a" else 25),
    ]


def stub_pages(today):
    """Страницы, которые «открывает» проверка в режиме заглушек. Без интернета."""
    deadline = today + timedelta(days=10)
    return {
        f"{STUB_SITE}/confirmed": (
            "<html><body><h1>Олимпиада</h1><script>var x = 1;</script>"
            f"<p>Регистрация открыта до {deadline.strftime('%d.%m.%Y')}.</p></body></html>"
        ),
        f"{STUB_SITE}/agree": "<html><body><p>Страница без нужной даты.</p></body></html>",
    }


def make_stub_fetch(today):
    """Создаёт функцию открытия страницы для режима заглушек."""
    pages = stub_pages(today)

    def fetch(url):
        if url not in pages:
            raise OSError("page not available")
        return pages[url]

    return fetch


def make_stub_providers(delay_seconds=0):
    """Две заглушки, чтобы можно было проверить сверку ответов."""
    return [StubProvider("stub-a", "a", delay_seconds), StubProvider("stub-b", "b", delay_seconds)]
