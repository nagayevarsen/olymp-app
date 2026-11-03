"""Чтение и проверка каталога событий из файла events.json.

Проверить файл после правки можно командой:
    .venv\\Scripts\\python -m catalog.events
"""

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from catalog.dates import get_status, get_urgency, days_until, is_closing_soon, parse_date, today_kz

EVENTS_FILE = Path(__file__).parent.parent / "data" / "events.json"

# Допустимые значения. Благодаря этим спискам опечатка вроде "Math" не создаст
# в фильтрах второй предмет. Новый предмет нужно добавить сюда и в файл перевода.
EVENT_TYPES = ("olympiad", "contest", "material")
EVENT_FORMATS = ("offline", "online")
SUBJECTS = (
    "math", "informatics", "ai", "robotics", "physics", "chemistry", "biology",
    "geography", "history", "economics", "kazakh_language", "russian_language",
    "english_language", "literature", "other",
)

# События из этой страны попадают в раздел «Казахстан», остальные — в «Международные».
HOME_COUNTRY = "Казахстан"

# Эти поля должны быть в каждой записи. Значением дат, возраста, сезона
# и стоимости может быть null: это значит «организатор не указал».
REQUIRED_FIELDS = (
    "id", "title", "type", "subjects", "grade_from", "grade_to", "age_from",
    "age_to", "country", "season", "registration_start", "registration_deadline",
    "event_date", "format", "fee_kzt", "summary", "source_url", "last_checked",
)
DATE_FIELDS = ("registration_start", "registration_deadline", "event_date")

# Шаблон учебного года, например 2026-2027.
SEASON_PATTERN = re.compile(r"([0-9]{4})-([0-9]{4})")


def is_filled_text(value):
    """Проверяет, что значение — непустой текст."""
    return isinstance(value, str) and value.strip() != ""


def is_valid_grade(value):
    """Проверяет, что значение — номер класса от 1 до 11."""
    # True и False в Python тоже считаются числами, поэтому исключаем их явно.
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 11


def is_whole_number(value):
    """Проверяет, что значение — целое число, а не True или False."""
    return isinstance(value, int) and not isinstance(value, bool)


def is_valid_season(value):
    """Проверяет учебный год: второй год должен идти сразу за первым."""
    if not isinstance(value, str):
        return False
    match = SEASON_PATTERN.fullmatch(value)
    return match is not None and int(match[2]) == int(match[1]) + 1


def is_valid_url(value):
    """Проверяет, что это обычная веб-ссылка.

    Это ещё и защита: ссылка вида javascript:... могла бы запустить чужой код.
    """
    if not isinstance(value, str):
        return False
    parts = urlparse(value)
    return parts.scheme in ("http", "https") and parts.netloc != ""


def check_event(event):
    """Проверяет одну запись и возвращает два списка: ошибки и предупреждения.

    Ошибка: запись нельзя показывать, например, нет ссылки на источник.
    Предупреждение: запись показываем, но дату нужно исправить. Код считает
    такую дату неизвестной и не обещает, что регистрация открыта.
    """
    if not isinstance(event, dict):
        return ["запись должна быть объектом в фигурных скобках"], []

    missing = [field for field in REQUIRED_FIELDS if field not in event]
    if missing:
        return ["нет полей: " + ", ".join(missing)], []

    errors = []
    warnings = []

    for field in ("id", "title", "country", "summary"):
        if not is_filled_text(event[field]):
            errors.append(f"поле {field} должно быть непустым текстом")

    if event["type"] not in EVENT_TYPES:
        errors.append(f"неизвестный тип: {event['type']}")
    if event["format"] not in EVENT_FORMATS:
        errors.append(f"неизвестный формат: {event['format']}")

    subjects = event["subjects"]
    if not isinstance(subjects, list) or not subjects:
        errors.append("поле subjects должно быть непустым списком")
    else:
        unknown = [str(subject) for subject in subjects if subject not in SUBJECTS]
        if unknown:
            errors.append("неизвестные предметы: " + ", ".join(unknown))

    grades_are_valid = is_valid_grade(event["grade_from"]) and is_valid_grade(event["grade_to"])
    if not grades_are_valid:
        errors.append("классы должны быть числами от 1 до 11")
    elif event["grade_from"] > event["grade_to"]:
        errors.append("класс «от» больше класса «до»")

    age_from = event["age_from"]
    age_to = event["age_to"]
    for age in (age_from, age_to):
        if age is not None and not (is_whole_number(age) and 3 <= age <= 30):
            errors.append("возраст должен быть числом от 3 до 30 или null")
    if is_whole_number(age_from) and is_whole_number(age_to) and age_from > age_to:
        errors.append("возраст «от» больше возраста «до»")

    if event["season"] is not None and not is_valid_season(event["season"]):
        errors.append("season должен выглядеть как 2026-2027 или быть null")

    fee = event["fee_kzt"]
    if fee is not None and not (is_whole_number(fee) and fee >= 0):
        errors.append("fee_kzt: 0 — бесплатно, число — цена в тенге, null — неизвестно")

    if not is_valid_url(event["source_url"]):
        errors.append("нужна ссылка на официальный источник (http или https)")

    # Дата проверки обещана в каждой карточке, поэтому без неё запись не показываем.
    if parse_date(event["last_checked"]) is None:
        errors.append("last_checked должна быть датой ГГГГ-ММ-ДД")

    for field in DATE_FIELDS:
        if event[field] is not None and parse_date(event[field]) is None:
            warnings.append(f"{field}: дата не в формате ГГГГ-ММ-ДД: {event[field]}")

    start = parse_date(event["registration_start"])
    deadline = parse_date(event["registration_deadline"])
    if start is not None and deadline is not None and start > deadline:
        warnings.append("начало регистрации позже дедлайна")

    return errors, warnings


def read_catalog(path=EVENTS_FILE):
    """Читает файл и возвращает годные записи и список найденных проблем.

    Если сам файл повреждён, Python сообщит об ошибке (ValueError).
    """
    # encoding нужен, чтобы русские буквы читались правильно и на Windows.
    raw_events = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw_events, list):
        raise ValueError("events.json должен содержать список записей")

    events = []
    errors = []
    warnings = []
    seen_ids = set()

    for number, event in enumerate(raw_events, start=1):
        event_errors, event_warnings = check_event(event)
        name = event.get("id") if isinstance(event, dict) else None
        label = f"Запись {number} ({name or 'без id'})"

        if not event_errors and event["id"] in seen_ids:
            event_errors = ["такой id уже есть в каталоге"]

        errors.extend(f"{label}: {problem}" for problem in event_errors)
        warnings.extend(f"{label}: {problem}" for problem in event_warnings)

        if not event_errors:
            seen_ids.add(event["id"])
            events.append(event)

    return events, errors, warnings


def add_display_info(event, today):
    """Возвращает копию записи с разделом, статусом и срочностью."""
    result = dict(event)
    result["region"] = "kazakhstan" if event["country"].strip() == HOME_COUNTRY else "international"

    # У учебных материалов нет регистрации, поэтому и статуса нет.
    if event["type"] == "material":
        result.update(status=None, urgency=None, days_left=None, closing_soon=False)
        return result

    start = event["registration_start"]
    deadline = event["registration_deadline"]
    result["status"] = get_status(start, deadline, today)
    result["urgency"] = get_urgency(deadline, today)
    result["days_left"] = days_until(deadline, today)
    result["closing_soon"] = is_closing_soon(start, deadline, today)
    return result


def sort_key(event):
    """Правило сортировки: ближайший дедлайн первым, без дедлайна в конце."""
    deadline = parse_date(event["registration_deadline"])
    return (deadline or date.max, event["title"])


def get_catalog(today, path=EVENTS_FILE):
    """Возвращает записи для приложения: со статусами и в порядке дедлайнов."""
    events, _errors, _warnings = read_catalog(path)
    return sorted((add_display_info(event, today) for event in events), key=sort_key)


def main():
    """Печатает отчёт о файле. Код 1 в конце означает, что есть ошибки."""
    # Без этой строки русский текст может отображаться неправильно на Windows.
    sys.stdout.reconfigure(encoding="utf-8")
    events, errors, warnings = read_catalog()
    print(f"Годных записей: {len(events)}. Сегодня в Казахстане: {today_kz()}")
    for problem in errors:
        print("ОШИБКА:", problem)
    for problem in warnings:
        print("ПРЕДУПРЕЖДЕНИЕ:", problem)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
