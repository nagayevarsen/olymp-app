"""Вся логика дат: сегодняшний день в Казахстане, статусы и срочность.

Здесь нет ни сервера, ни интернета, ни ИИ. Только простые функции:
дали на вход даты, получили ответ. Поэтому их легко проверять тестами.
"""

import re
from datetime import date, datetime, timedelta, timezone

# Казахстан живёт по единому времени UTC+5. Смещение задано прямо здесь,
# поэтому результат не зависит от настроек часового пояса на компьютере.
KZ_TIMEZONE = timezone(timedelta(hours=5))

# Статусы регистрации. Это коды для программы, а не текст для человека:
# текст на русском, казахском и английском будет лежать в файлах перевода.
STATUS_OPEN = "open"  # регистрация открыта
STATUS_SOON = "soon"  # скоро откроется
STATUS_CLOSED = "closed"  # регистрация закрыта
STATUS_UNANNOUNCED = "unannounced"  # дата следующего этапа не объявлена

# Цвета меток срочности.
URGENCY_RED = "red"
URGENCY_YELLOW = "yellow"
URGENCY_GREEN = "green"

# Главный экран показывает события, которые закрываются за столько дней.
CLOSING_SOON_DAYS = 14

# Шаблон даты: ровно 4 цифры, дефис, 2 цифры, дефис, 2 цифры.
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def today_kz(now=None):
    """Возвращает сегодняшнюю дату по времени Казахстана.

    Параметр now нужен только тестам: так можно проверить любой момент
    времени, не дожидаясь его. В обычной работе берётся текущее время.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    return now.astimezone(KZ_TIMEZONE).date()


def current_season(today):
    """Возвращает учебный сезон: с августа начинается новый, например 2026-2027."""
    first_year = today.year if today.month >= 8 else today.year - 1
    return f"{first_year}-{first_year + 1}"


def parse_date(text):
    """Превращает строку ГГГГ-ММ-ДД в дату.

    Если даты нет или она записана неправильно, возвращает None. Например:
    "03-15" (нет года), "2026-02-30" (такого дня нет), "15.03.2026".
    """
    if not isinstance(text, str) or not DATE_PATTERN.fullmatch(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        # Формат верный, но такого дня в календаре нет.
        return None


def days_until(deadline_text, today):
    """Считает, сколько дней осталось до дедлайна.

    0 означает «сегодня», отрицательное число значит, что дедлайн прошёл.
    Если дата неизвестна или записана с ошибкой, возвращает None.
    """
    deadline = parse_date(deadline_text)
    if deadline is None:
        return None
    return (deadline - today).days


def get_status(registration_start_text, deadline_text, today):
    """Определяет статус регистрации.

    Порядок проверок важен: каждая следующая выполняется, только если
    предыдущие не сработали.
    """
    start = parse_date(registration_start_text)
    deadline = parse_date(deadline_text)

    # 1. Дедлайн прошёл: событие больше не действует.
    if deadline is not None and deadline < today:
        return STATUS_CLOSED

    # 2. Начало регистрации ещё впереди.
    if start is not None and start > today:
        return STATUS_SOON

    # 3. Дедлайн неизвестен: мы не можем обещать, что регистрация идёт.
    if deadline is None:
        return STATUS_UNANNOUNCED

    # 4. Остался один случай: дедлайн сегодня или позже, начало не в будущем.
    return STATUS_OPEN


def get_urgency(deadline_text, today):
    """Возвращает цвет срочности или None, если метка не нужна.

    Меньше 3 дней — красный, меньше 7 — жёлтый, остальное — зелёный.
    """
    days = days_until(deadline_text, today)
    if days is None or days < 0:
        return None
    if days < 3:
        return URGENCY_RED
    if days < 7:
        return URGENCY_YELLOW
    return URGENCY_GREEN


def is_closing_soon(registration_start_text, deadline_text, today):
    """Проверяет, попадает ли событие на главный экран.

    Подходят только открытые события с дедлайном в ближайшие 14 дней.
    """
    status = get_status(registration_start_text, deadline_text, today)
    if status != STATUS_OPEN:
        return False
    return days_until(deadline_text, today) <= CLOSING_SOON_DAYS
