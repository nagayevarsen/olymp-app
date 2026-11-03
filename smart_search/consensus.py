"""Сверка ответов разных моделей.

Записи об одном событии объединяются по адресу его официальной страницы.
Уровень доверия потом ставит код, а не сама модель.
"""

from urllib.parse import urlparse

TRUST_VERIFIED = "verified"  # подтверждено на официальной странице
TRUST_MODELS_AGREE = "models_agree"  # модели согласны, проверьте страницу
TRUST_UNCONFIRMED = "unconfirmed"  # не подтверждено


def url_key(url):
    """Приводит ссылку к одному виду: www, регистр и последний / не важны."""
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{host}{parts.path.rstrip('/')}"


def merge_answers(answers):
    """Объединяет записи. answers — это список пар (название модели, запись)."""
    groups = {}
    for provider, candidate in answers:
        groups.setdefault(url_key(candidate["official_url"]), []).append((provider, candidate))

    merged = []
    for group in groups.values():
        base = dict(group[0][1])
        by_deadline = {}
        for provider, candidate in group:
            deadline = candidate["registration_deadline"]
            if deadline is not None:
                by_deadline.setdefault(deadline, {"providers": set(), "quote": None})
                by_deadline[deadline]["providers"].add(provider)
                by_deadline[deadline]["quote"] = by_deadline[deadline]["quote"] or candidate["date_quote"]

        base["providers"] = sorted({provider for provider, _ in group})
        # Варианты дедлайна: если модели спорят, их будет несколько.
        base["variants"] = [
            {"deadline": deadline, "quote": info["quote"], "providers": sorted(info["providers"])}
            for deadline, info in sorted(by_deadline.items())
        ]
        merged.append(base)
    return merged


def apply_verdict(item, confirmed_variant):
    """Выбирает дедлайн и ставит уровень доверия.

    Если страница подтвердила дату, верим ей. Если модели спорят и страница не помогла,
    дату не показываем: лучше честно попросить уточнить, чем выбрать наугад.
    """
    result = {key: value for key, value in item.items() if key not in ("variants", "providers")}
    variants = item["variants"]

    if confirmed_variant is not None:
        chosen, trust = confirmed_variant, TRUST_VERIFIED
    elif len(variants) == 1:
        chosen = variants[0]
        trust = TRUST_MODELS_AGREE if len(chosen["providers"]) >= 2 else TRUST_UNCONFIRMED
    else:
        chosen, trust = None, TRUST_UNCONFIRMED

    result["registration_deadline"] = chosen["deadline"] if chosen else None
    result["date_quote"] = chosen["quote"] if chosen else None
    result["trust"] = trust
    # Эта пометка включает на экране «уточните на сайте организатора».
    result["needs_check"] = result["registration_deadline"] is None
    return result
