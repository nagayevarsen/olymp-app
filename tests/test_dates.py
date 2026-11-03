"""Тесты логики дат.

Сами случаи лежат в date_cases.json. По этой же таблице позже будет
проверяться версия логики для браузера, чтобы Python и JavaScript
всегда считали одинаково.
"""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from catalog.dates import get_status, get_urgency, is_closing_soon, parse_date, today_kz

CASES = json.loads(
    (Path(__file__).parent / "date_cases.json").read_text(encoding="utf-8")
)
DEFAULT_TODAY = date.fromisoformat(CASES["today"])


def cases_for(section):
    """Готовит случаи из таблицы так, чтобы pytest показывал их названия."""
    return [pytest.param(case, id=case["name"]) for case in CASES[section]]


def today_for(case):
    """У случая может быть своя дата «сегодня», иначе берём общую."""
    return date.fromisoformat(case["today"]) if "today" in case else DEFAULT_TODAY


@pytest.mark.parametrize("case", cases_for("today_kz"))
def test_today_kz(case):
    moment = datetime.fromisoformat(case["utc"])
    assert today_kz(moment) == date.fromisoformat(case["expected"])


@pytest.mark.parametrize("case", cases_for("parse_date"))
def test_parse_date(case):
    assert (parse_date(case["text"]) is not None) == case["valid"]


@pytest.mark.parametrize("case", cases_for("status"))
def test_status(case):
    assert get_status(case["start"], case["deadline"], today_for(case)) == case["expected"]


@pytest.mark.parametrize("case", cases_for("urgency"))
def test_urgency(case):
    assert get_urgency(case["deadline"], today_for(case)) == case["expected"]


@pytest.mark.parametrize("case", cases_for("closing_soon"))
def test_closing_soon(case):
    assert is_closing_soon(case["start"], case["deadline"], today_for(case)) == case["expected"]
