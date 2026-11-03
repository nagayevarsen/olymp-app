"""Задания прошлых лет из файла archives.json.

Каждая запись связана с олимпиадой или конкурсом через series_id и показывается
внутри их карточки. Здесь хранятся только факты и ссылки на официальные страницы.
Сами задания мы не копируем: они принадлежат организаторам.
"""

import json
from pathlib import Path

from catalog.dates import parse_date
from catalog.events import is_filled_text, is_valid_season, is_valid_url

ARCHIVES_FILE = Path(__file__).parent.parent / "data" / "archives.json"

REQUIRED_FIELDS = ("id", "series_id", "stage", "season", "tasks_url", "solutions_url", "last_checked")


def check_archive(item):
    """Проверяет одну запись и возвращает список ошибок."""
    if not isinstance(item, dict):
        return ["запись должна быть объектом в фигурных скобках"]

    missing = [field for field in REQUIRED_FIELDS if field not in item]
    if missing:
        return ["нет полей: " + ", ".join(missing)]

    errors = []
    for field in ("id", "series_id"):
        if not is_filled_text(item[field]):
            errors.append(f"поле {field} должно быть непустым текстом")

    # Задания всегда относятся к конкретному учебному году.
    if not is_valid_season(item["season"]):
        errors.append("season должен выглядеть как 2025-2026")
    if not is_valid_url(item["tasks_url"]):
        errors.append("нужна ссылка на официальную страницу с заданиями")
    if item["solutions_url"] is not None and not is_valid_url(item["solutions_url"]):
        errors.append("solutions_url должна быть ссылкой или null")
    if parse_date(item["last_checked"]) is None:
        errors.append("last_checked должна быть датой ГГГГ-ММ-ДД")
    return errors


def read_archives(path=ARCHIVES_FILE):
    """Читает файл и возвращает годные записи и список ошибок."""
    raw_items = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw_items, list):
        raise ValueError("archives.json должен содержать список записей")

    items = []
    errors = []
    seen_ids = set()
    for number, item in enumerate(raw_items, start=1):
        item_errors = check_archive(item)
        name = item.get("id") if isinstance(item, dict) else None
        if not item_errors and item["id"] in seen_ids:
            item_errors = ["такой id уже есть в архиве"]
        errors.extend(f"Архив, запись {number} ({name or 'без id'}): {e}" for e in item_errors)
        if not item_errors:
            seen_ids.add(item["id"])
            items.append(item)
    return items, errors


def get_archives(path=ARCHIVES_FILE):
    """Возвращает записи для приложения: сначала самые новые учебные годы."""
    items, _errors = read_archives(path)
    items.sort(key=lambda item: item["stage"] or "")
    items.sort(key=lambda item: item["season"], reverse=True)
    return items


def find_unlinked(events, archives):
    """Находит записи, которые нигде не покажутся, потому что не связаны с событием."""
    series = {
        event["series_id"] for event in events
        if event["type"] != "material" and event.get("series_id")
    }
    problems = []
    for item in archives:
        if item["series_id"] not in series:
            problems.append(f"Архив {item['id']}: нет события с series_id {item['series_id']}")
    for event in events:
        if event["type"] == "material" and event.get("series_id") not in series:
            problems.append(f"Материал {event['id']}: не связан ни с одним событием через series_id")
    return problems
