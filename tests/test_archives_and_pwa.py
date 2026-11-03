"""Тесты заданий прошлых лет и файлов для установки приложения."""

import json
import re
from pathlib import Path

import pytest

import app as app_module
from catalog.archives import check_archive, get_archives, read_archives

ROOT = Path(__file__).parent.parent


def make_archive(**changes):
    """Создаёт правильную запись архива. В тесте меняем только нужные поля."""
    item = {
        "id": "archive",
        "series_id": None,
        "title": "Олимпиада",
        "stage": None,
        "subjects": ["math"],
        "grade_from": 7,
        "grade_to": 9,
        "country": "Казахстан",
        "season": "2025-2026",
        "tasks_url": "https://example.org/tasks",
        "solutions_url": None,
        "last_checked": "2026-11-04",
    }
    item.update(changes)
    return item


def test_correct_archive_has_no_errors():
    assert check_archive(make_archive()) == []


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"season": None}, id="нет учебного года"),
        pytest.param({"tasks_url": None}, id="нет ссылки на задания"),
        pytest.param({"tasks_url": "javascript:alert(1)"}, id="опасная ссылка"),
        pytest.param({"solutions_url": "решения"}, id="неверная ссылка на решения"),
        pytest.param({"subjects": ["Физика"]}, id="неизвестный предмет"),
        pytest.param({"grade_from": 10}, id="классы перепутаны"),
        pytest.param({"last_checked": "03-15"}, id="дата проверки без года"),
    ],
)
def test_bad_archive_is_an_error(changes):
    assert check_archive(make_archive(**changes))


def test_archives_are_sorted_newest_first(tmp_path):
    path = tmp_path / "archives.json"
    items = [make_archive(id="old", season="2023-2024"), make_archive(id="new", season="2025-2026")]
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    assert [item["id"] for item in get_archives(path)] == ["new", "old"]


def test_real_archives_have_no_errors():
    _items, errors = read_archives()
    assert errors == []


def test_api_includes_archives():
    response = app_module.app.test_client().get("/api/events")
    assert response.status_code == 200
    assert "archives" in response.json


def test_service_worker_opens_from_site_root():
    response = app_module.app.test_client().get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.content_type


def test_service_worker_only_lists_existing_files():
    """Если файла из списка нет, офлайн-режим не установится вообще."""
    text = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")
    paths = re.findall(r'"/(static/[^"]+)"', text)
    assert paths
    for path in paths:
        assert (ROOT / path).is_file(), path


def test_manifest_allows_installation():
    client = app_module.app.test_client()
    response = client.get("/static/manifest.webmanifest")
    assert response.status_code == 200
    manifest = json.loads(response.text)
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    for icon in manifest["icons"]:
        assert (ROOT / icon["src"].lstrip("/")).is_file()


def test_home_page_links_manifest():
    response = app_module.app.test_client().get("/")
    assert "manifest.webmanifest" in response.text
