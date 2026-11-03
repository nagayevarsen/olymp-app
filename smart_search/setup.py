"""Собирает сервис умного поиска по настройкам из переменных окружения."""

import json
import os
from pathlib import Path

from catalog.dates import today_kz
from smart_search.guards import DailyLimit, ResultCache
from smart_search.official import load_official_domains
from smart_search.pipeline import SearchService
from smart_search.providers import make_stub_fetch, make_stub_providers

RU_TEXTS = Path(__file__).parent.parent / "static" / "i18n" / "ru.json"
DEFAULT_DAILY_LIMIT = 50


def make_subject_names():
    """Переводит коды предметов в русские названия для запроса к ИИ."""
    texts = json.loads(RU_TEXTS.read_text(encoding="utf-8"))
    return lambda subjects: [texts[f"subject_{subject}"] for subject in subjects]


def read_daily_limit():
    """Берёт лимит из настроек. Если значение неверное, используем обычный."""
    try:
        return max(0, int(os.environ.get("SEARCH_DAILY_LIMIT", DEFAULT_DAILY_LIMIT)))
    except ValueError:
        return DEFAULT_DAILY_LIMIT


def build_service():
    """Создаёт сервис. Пока настоящие модели не подключены, работают заглушки."""
    return SearchService(
        providers=make_stub_providers(delay_seconds=0.4),
        make_fetch=lambda today, _domains: make_stub_fetch(today),
        # В режиме заглушек официальным считается только учебный домен example.org.
        domains=load_official_domains() | {"example.org"},
        cache=ResultCache(),
        daily_limit=DailyLimit(read_daily_limit()),
        subject_names=make_subject_names(),
        source="stub",
        today_func=today_kz,
    )
