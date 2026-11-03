"""Сервер приложения. Он отдаёт страницу и данные каталога.

Запуск: .venv\\Scripts\\python app.py
После этого откройте в браузере http://127.0.0.1:5000
"""

import mimetypes
from datetime import datetime, timezone

import json

from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context

from catalog.archives import ARCHIVES_FILE, get_archives
from catalog.dates import today_kz
from catalog.events import EVENTS_FILE, SUBJECTS, get_catalog
from smart_search.models import COUNTRIES, parse_search_request
from smart_search.pipeline import load_demo_results
from smart_search.setup import build_service

# Сообщаем серверу тип файла установки, иначе на Windows он может быть неизвестен.
mimetypes.add_type("application/manifest+json", ".webmanifest")

app = Flask(__name__)
# Форма поиска очень маленькая, поэтому большие запросы сервер сразу отклоняет.
app.config["MAX_CONTENT_LENGTH"] = 4096

search_service = build_service()


@app.get("/")
def home():
    """Отдаёт главную страницу."""
    return render_template("index.html")


@app.get("/sw.js")
def service_worker():
    """Отдаёт файл офлайн-режима.

    Он должен открываться из корня сайта, иначе управлял бы только папкой static.
    max_age=0 заставляет браузер проверять, не вышла ли новая версия.
    """
    return send_from_directory(app.static_folder, "sw.js", max_age=0)


@app.get("/api/events")
def api_events():
    """Отдаёт события с посчитанными статусами и задания прошлых лет."""
    today = today_kz()
    try:
        events = get_catalog(today, EVENTS_FILE)
        archives = get_archives(ARCHIVES_FILE)
    except (OSError, ValueError):
        # Файла нет или в нём ошибка: записываем причину в журнал сервера,
        # а странице сообщаем, что каталог сейчас недоступен.
        app.logger.exception("Не удалось прочитать каталог")
        return jsonify(error="catalog_unavailable"), 503
    return jsonify(
        today=today.isoformat(),
        # Точное время ответа: офлайн приложение покажет, насколько свежи данные.
        generated_at=datetime.now(timezone.utc).isoformat(),
        events=events,
        archives=archives,
        # Полный список предметов для формы поиска: он один на сервер и страницу.
        subjects=SUBJECTS,
        countries=COUNTRIES,
    )


@app.post("/api/smart-search")
def api_smart_search():
    """Запускает умный поиск и по строкам отдаёт прогресс, а затем результат.

    Условия поиска приходят в теле запроса, а не в адресе, поэтому не попадают
    в журналы сервера. Мы их не сохраняем.
    """
    try:
        search_request = parse_search_request(request.get_json(silent=True))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    def lines():
        for event in search_service.run(search_request):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return Response(
        stream_with_context(lines()),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/api/smart-search/demo")
def api_smart_search_demo():
    """Сохранённые результаты на случай, если до живого поиска не достучаться."""
    return jsonify(type="result", source="demo", notice="unavailable", results=load_demo_results(today_kz()))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
