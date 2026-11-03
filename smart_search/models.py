"""Проверка данных на входе и выходе умного поиска.

Форму заполняет пользователь, а ответы пишет ИИ, который читает чужие сайты.
Поэтому ничему не доверяем: каждое значение проверяет код.
"""

import json
from dataclasses import dataclass

from catalog.dates import parse_date
from catalog.events import SUBJECTS, is_valid_season, is_valid_url

COUNTRIES = ("Казахстан", "Кыргызстан", "Узбекистан", "Россия", "Другая страна")
MAX_SUBJECTS = 5
MAX_RESULTS_PER_ANSWER = 20

# Длинный текст из ответа ИИ обрезаем: на экране он не нужен, а вред может принести.
MAX_TITLE_LENGTH = 200
MAX_SUMMARY_LENGTH = 500
MAX_QUOTE_LENGTH = 300


@dataclass(frozen=True)
class SearchRequest:
    """Условия поиска. Они живут только во время запроса и нигде не сохраняются."""

    grade: int
    subjects: tuple
    country: str
    age: int | None = None


def is_whole_number(value):
    """Проверяет, что значение — целое число, а не True или False."""
    return isinstance(value, int) and not isinstance(value, bool)


def parse_search_request(data):
    """Проверяет форму. Если что-то не так, сообщает ошибкой ValueError."""
    if not isinstance(data, dict):
        raise ValueError("bad_request")

    grade = data.get("grade")
    if not is_whole_number(grade) or not 1 <= grade <= 12:
        raise ValueError("bad_grade")

    age = data.get("age")
    if age is not None and (not is_whole_number(age) or not 3 <= age <= 30):
        raise ValueError("bad_age")

    # Страну выбирают из списка, поэтому чужой текст не попадёт в запрос к ИИ.
    country = data.get("country")
    if country not in COUNTRIES:
        raise ValueError("bad_country")

    subjects = data.get("subjects")
    if not isinstance(subjects, list) or not 1 <= len(subjects) <= MAX_SUBJECTS:
        raise ValueError("bad_subjects")
    if any(subject not in SUBJECTS for subject in subjects):
        raise ValueError("bad_subjects")

    return SearchRequest(grade=grade, subjects=tuple(sorted(set(subjects))), country=country, age=age)


def clean_text(value, max_length):
    """Возвращает обрезанный текст или None, если это не текст."""
    if not isinstance(value, str) or not value.strip():
        return None
    return " ".join(value.split())[:max_length]


def clean_date(value):
    """Оставляет только настоящую дату ГГГГ-ММ-ДД. Всё остальное считаем неизвестным."""
    return value if parse_date(value) is not None else None


def clean_number(value, smallest, largest):
    """Оставляет число из допустимого диапазона, иначе None."""
    return value if is_whole_number(value) and smallest <= value <= largest else None


def clean_candidate(raw):
    """Приводит одну запись от ИИ к понятному виду. Без названия и ссылки вернёт None."""
    if not isinstance(raw, dict):
        return None

    title = clean_text(raw.get("title"), MAX_TITLE_LENGTH)
    url = raw.get("official_url")
    if title is None or not is_valid_url(url):
        return None

    season = raw.get("season")
    subjects = raw.get("subjects")
    return {
        "title": title,
        "official_url": url,
        "grade_from": clean_number(raw.get("grade_from"), 1, 12),
        "grade_to": clean_number(raw.get("grade_to"), 1, 12),
        "age_from": clean_number(raw.get("age_from"), 3, 30),
        "age_to": clean_number(raw.get("age_to"), 3, 30),
        "subjects": [s for s in (clean_text(s, 60) for s in subjects) if s] if isinstance(subjects, list) else [],
        "registration_start": clean_date(raw.get("registration_start")),
        "registration_deadline": clean_date(raw.get("registration_deadline")),
        "event_date": clean_date(raw.get("event_date")),
        "season": season if is_valid_season(season) else None,
        "summary": clean_text(raw.get("summary"), MAX_SUMMARY_LENGTH),
        "date_quote": clean_text(raw.get("date_quote"), MAX_QUOTE_LENGTH),
    }


def parse_answer(text):
    """Достаёт записи из ответа ИИ. Если ответ не разобрать, сообщает ValueError."""
    if not isinstance(text, str):
        raise ValueError("answer is not text")

    # Модели иногда добавляют текст вокруг JSON, поэтому берём часть от [ до ].
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end < start:
        raise ValueError("answer has no JSON list")

    # json.JSONDecodeError — это тоже ValueError.
    items = json.loads(text[start:end + 1])
    if not isinstance(items, list):
        raise ValueError("answer is not a list")

    cleaned = (clean_candidate(item) for item in items[:MAX_RESULTS_PER_ANSWER])
    return [candidate for candidate in cleaned if candidate is not None]
