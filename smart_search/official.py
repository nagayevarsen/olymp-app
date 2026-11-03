"""Список официальных сайтов и проверка, что ссылка ведёт на один из них."""

import json
from pathlib import Path
from urllib.parse import urlparse

SITES_FILE = Path(__file__).parent.parent / "data" / "official_sites.json"


def load_official_domains(path=SITES_FILE):
    """Читает домены из файла. Лишние пробелы и регистр не важны."""
    sites = json.loads(Path(path).read_text(encoding="utf-8"))
    return frozenset(site["domain"].strip().lower().rstrip(".") for site in sites)


def is_official_url(url, domains):
    """Проверяет, что ссылка ведёт на официальный домен или его поддомен.

    Сравниваем домен целиком, поэтому адрес olymp.kz.evil.com не пройдёт как olymp.kz.
    Ссылки с логином или нестандартным портом тоже не принимаем: так маскируют подделки.
    """
    try:
        parts = urlparse(url)
        port = parts.port
    except (ValueError, TypeError, AttributeError):
        return False

    if parts.scheme not in ("http", "https") or parts.username or parts.password:
        return False
    if port not in (None, 80, 443):
        return False

    host = (parts.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return False
    return any(host == domain or host.endswith("." + domain) for domain in domains)
