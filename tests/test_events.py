"""Тесты проверки каталога и работы сервера."""

import json
from datetime import date
from pathlib import Path

import pytest

import app as app_module
from catalog.events import SUBJECTS, check_event, get_catalog, read_catalog

TODAY = date(2026, 11, 10)


def make_event(**changes):
    """Создаёт правильную запись. В тесте меняем только нужные поля."""
    event = {
        "id": "test-event",
        "title": "Тестовое событие",
        "type": "olympiad",
        "subjects": ["math"],
        "grade_from": 7,
        "grade_to": 11,
        "age_from": None,
        "age_to": None,
        "country": "Казахстан",
        "season": "2026-2027",
        "fee_kzt": None,
        "registration_start": "2026-10-01",
        "registration_deadline": "2026-11-20",
        "event_date": "2026-12-01",
        "format": "online",
        "summary": "Краткое условие.",
        "source_url": "https://example.org/event",
        "registration_url": None,
        "last_checked": "2026-11-04",
    }
    event.update(changes)
    return event


def write_catalog(tmp_path, events):
    """Записывает временный файл каталога и возвращает путь к нему."""
    path = tmp_path / "events.json"
    path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    return path


def test_correct_event_has_no_problems():
    assert check_event(make_event()) == ([], [])


def test_twelfth_grade_is_allowed():
    assert check_event(make_event(grade_to=12)) == ([], [])


def test_every_subject_has_russian_name():
    """Иначе в форме вместо названия предмета появится его код."""
    path = Path(__file__).parent.parent / "static" / "i18n" / "ru.json"
    texts = json.loads(path.read_text(encoding="utf-8"))
    assert [subject for subject in SUBJECTS if f"subject_{subject}" not in texts] == []


def test_api_sends_full_subject_list():
    response = app_module.app.test_client().get("/api/events")
    assert response.json["subjects"] == list(SUBJECTS)


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"type": "квиз"}, id="неизвестный тип"),
        pytest.param({"type": ["olympiad"]}, id="тип записан списком"),
        pytest.param({"format": "очно"}, id="неизвестный формат"),
        pytest.param({"subjects": [["math"]]}, id="предмет записан списком"),
        pytest.param({"subjects": []}, id="нет предметов"),
        pytest.param({"subjects": ["Математика"]}, id="неизвестный предмет"),
        pytest.param({"grade_from": 13, "grade_to": 13}, id="класс вне диапазона"),
        pytest.param({"grade_from": True}, id="класс не число"),
        pytest.param({"grade_from": 9, "grade_to": 7}, id="классы перепутаны"),
        pytest.param({"source_url": ""}, id="нет ссылки"),
        pytest.param({"source_url": "example.org"}, id="ссылка без https"),
        pytest.param({"source_url": "javascript:alert(1)"}, id="опасная ссылка"),
        pytest.param({"registration_url": "javascript:alert(1)"}, id="опасная ссылка регистрации"),
        pytest.param({"last_checked": "03-15"}, id="дата проверки без года"),
        pytest.param({"title": " "}, id="пустое название"),
        pytest.param({"season": "2026"}, id="сезон из одного года"),
        pytest.param({"season": "2026-2028"}, id="сезон через год"),
        pytest.param({"age_from": 2}, id="возраст вне диапазона"),
        pytest.param({"age_from": 16, "age_to": 14}, id="возраст перепутан"),
        pytest.param({"fee_kzt": -1}, id="отрицательная цена"),
        pytest.param({"fee_kzt": "5000"}, id="цена текстом"),
    ],
)
def test_bad_event_is_an_error(changes):
    errors, _warnings = check_event(make_event(**changes))
    assert errors


def test_missing_field_is_an_error():
    event = make_event()
    del event["source_url"]
    errors, _warnings = check_event(event)
    assert "source_url" in errors[0]


def test_bad_deadline_is_a_warning_and_status_is_unannounced(tmp_path):
    event = make_event(registration_deadline="03-15")
    errors, warnings = check_event(event)
    assert errors == []
    assert warnings

    catalog = get_catalog(TODAY, write_catalog(tmp_path, [event]))
    assert catalog[0]["status"] == "unannounced"
    assert catalog[0]["closing_soon"] is False


def test_start_after_deadline_is_a_warning():
    _errors, warnings = check_event(make_event(registration_start="2026-12-30"))
    assert warnings


def test_bad_and_repeated_records_are_excluded(tmp_path):
    path = write_catalog(
        tmp_path,
        [make_event(), make_event(), make_event(id="no-link", source_url=""), "текст"],
    )
    events, errors, _warnings = read_catalog(path)
    assert [event["id"] for event in events] == ["test-event"]
    assert len(errors) == 3


def test_catalog_is_sorted_by_deadline_with_empty_last(tmp_path):
    path = write_catalog(
        tmp_path,
        [
            make_event(id="no-deadline", registration_deadline=None),
            make_event(id="later", registration_deadline="2026-12-20"),
            make_event(id="sooner", registration_deadline="2026-11-12"),
        ],
    )
    assert [event["id"] for event in get_catalog(TODAY, path)] == ["sooner", "later", "no-deadline"]


def test_past_event_is_closed(tmp_path):
    path = write_catalog(tmp_path, [make_event(registration_deadline="2026-11-09")])
    event = get_catalog(TODAY, path)[0]
    assert event["status"] == "closed"
    assert event["urgency"] is None
    assert event["closing_soon"] is False


def test_material_has_no_status(tmp_path):
    material = make_event(
        type="material", registration_start=None, registration_deadline=None, event_date=None
    )
    event = get_catalog(TODAY, write_catalog(tmp_path, [material]))[0]
    assert event["status"] is None
    assert event["closing_soon"] is False


def test_region_is_set_from_country(tmp_path):
    path = write_catalog(
        tmp_path,
        [
            make_event(id="kz", country="Казахстан"),
            make_event(id="world", country="Международная"),
        ],
    )
    regions = {event["id"]: event["region"] for event in get_catalog(TODAY, path)}
    assert regions == {"kz": "kazakhstan", "world": "international"}


def test_broken_file_is_reported(tmp_path):
    path = tmp_path / "events.json"
    path.write_text("{ сломанный файл", encoding="utf-8")
    with pytest.raises(ValueError):
        read_catalog(path)


def test_real_catalog_has_no_errors():
    """Ошибка в настоящем файле данных должна остановить тесты."""
    _events, errors, _warnings = read_catalog()
    assert errors == []


def test_home_page_opens():
    response = app_module.app.test_client().get("/")
    assert response.status_code == 200
    assert "<h1" in response.text


def test_api_returns_events_with_status(tmp_path, monkeypatch):
    path = write_catalog(tmp_path, [make_event(registration_deadline="2099-01-01")])
    monkeypatch.setattr(app_module, "EVENTS_FILE", path)
    response = app_module.app.test_client().get("/api/events")
    assert response.status_code == 200
    assert response.json["events"][0]["status"] == "open"
    date.fromisoformat(response.json["today"])


def test_api_reports_broken_catalog(tmp_path, monkeypatch):
    path = tmp_path / "events.json"
    path.write_text("{ сломанный файл", encoding="utf-8")
    monkeypatch.setattr(app_module, "EVENTS_FILE", path)
    response = app_module.app.test_client().get("/api/events")
    assert response.status_code == 503
    assert response.json["error"] == "catalog_unavailable"
