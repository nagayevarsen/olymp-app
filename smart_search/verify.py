"""Открывает официальную страницу и проверяет, что дата и сезон на ней совпадают.

Это проверка кодом, а не ИИ: цитата должна дословно быть на странице, а дата —
быть в цитате вместе с годом.
"""

import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser

from catalog.dates import parse_date
from smart_search.official import is_official_url

PAGE_TIMEOUT_SECONDS = 8
MAX_PAGE_BYTES = 2_000_000
MAX_REDIRECTS = 3

MONTHS_RU = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
             "сентября", "октября", "ноября", "декабря")
MONTHS_KK = ("қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде", "тамыз",
             "қыркүйек", "қазан", "қараша", "желтоқсан")
MONTHS_EN = ("january", "february", "march", "april", "may", "june", "july", "august",
             "september", "october", "november", "december")


class TextExtractor(HTMLParser):
    """Вытаскивает видимый текст из страницы, пропуская скрипты и стили."""

    SKIPPED_TAGS = ("script", "style", "noscript", "template")

    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIPPED_TAGS:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIPPED_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth == 0:
            self.parts.append(data)


def normalize(text):
    """Приводит текст к одному виду: регистр, пробелы и разные тире не важны."""
    text = text.lower().replace(" ", " ")
    text = re.sub(r"[–—−]", "-", text)
    return " ".join(text.split())


def page_text(html):
    """Возвращает видимый текст страницы в едином виде."""
    extractor = TextExtractor()
    extractor.feed(html)
    return normalize(" ".join(extractor.parts))


def date_patterns(day):
    """Все способы записать дату с годом. Дата без года подтверждением не считается."""
    d, m, y = day.day, day.month, day.year
    months = (MONTHS_RU[m - 1], MONTHS_KK[m - 1], MONTHS_EN[m - 1])
    return (
        f"{y}-{m:02d}-{d:02d}",
        f"{d:02d}.{m:02d}.{y}",
        f"{d}.{m}.{y}",
        f"{d} {months[0]} {y}",
        f"{d} {months[1]} {y}",
        f"{y} жылғы {d} {months[1]}",
        f"{d} {months[2]} {y}",
        f"{months[2]} {d}, {y}",
    )


def text_has_date(text, day):
    """Ищет дату в тексте. Перед ней не должно быть цифры, иначе 5 совпадёт с 15."""
    return any(re.search(rf"(?<![0-9]){re.escape(pattern)}", text) for pattern in date_patterns(day))


def season_window(season):
    """Границы учебного сезона: с августа первого года по август второго."""
    first, second = (int(year) for year in season.split("-"))
    return date(first, 8, 1), date(second, 8, 31)


def text_has_quote(text, quote):
    """Ищет цитату целиком: вокруг неё не должно быть продолжения слова или числа."""
    return re.search(rf"(?<!\w){re.escape(quote)}(?!\w)", text) is not None


def check_page(html, deadline_text, quote, season):
    """Возвращает True, только если страница подтверждает и дату, и сезон.

    Цитата должна дословно быть на странице, а в ней — дедлайн с годом. Сезон сходится,
    если этот дедлайн попадает в учебный год: старая страница такую проверку не пройдёт.
    """
    deadline = parse_date(deadline_text)
    if deadline is None or not quote:
        return False

    clean_quote = normalize(quote)
    if not text_has_quote(page_text(html), clean_quote) or not text_has_date(clean_quote, deadline):
        return False

    start, end = season_window(season)
    return start <= deadline <= end


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Запрещает автоматические переходы, чтобы проверять адрес каждого перехода."""

    def redirect_request(self, *args, **kwargs):
        return None


def fetch_page(url, domains):
    """Скачивает страницу. Переходит только по официальным адресам.

    Благодаря этому ответ ИИ не сможет заставить сервер открыть чужой или
    внутренний адрес. Ошибки сообщаются через OSError или ValueError.
    """
    opener = urllib.request.build_opener(NoRedirect)
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not is_official_url(current, domains):
            raise ValueError("not an official address")
        request = urllib.request.Request(current, headers={"User-Agent": "olymp-app-checker"})
        try:
            with opener.open(request, timeout=PAGE_TIMEOUT_SECONDS) as response:
                content_type = response.headers.get_content_type()
                if content_type not in ("text/html", "text/plain"):
                    raise ValueError("not a text page")
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read(MAX_PAGE_BYTES)
                return body.decode(charset, errors="replace")
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location")
            if error.code in (301, 302, 303, 307, 308) and location:
                current = urllib.parse.urljoin(current, location)
                continue
            raise
    raise ValueError("too many redirects")


def find_confirmed_variant(item, fetch, season):
    """Открывает страницу и ищет дедлайн, который она подтверждает. Иначе вернёт None."""
    variants = [variant for variant in item["variants"] if variant["quote"]]
    if not variants:
        return None
    try:
        html = fetch(item["official_url"])
    except (OSError, ValueError):
        # Страница не открылась: это не значит, что данные неверны, но подтверждения нет.
        return None
    for variant in variants:
        if check_page(html, variant["deadline"], variant["quote"], season):
            return variant
    return None
