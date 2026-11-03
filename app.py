"""Сервер приложения. Он отдаёт страницу и данные каталога.

Запуск: .venv\\Scripts\\python app.py
После этого откройте в браузере http://127.0.0.1:5000
"""

import mimetypes
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, send_from_directory

from catalog.archives import ARCHIVES_FILE, get_archives
from catalog.dates import today_kz
from catalog.events import EVENTS_FILE, get_catalog

# Сообщаем серверу тип файла установки, иначе на Windows он может быть неизвестен.
mimetypes.add_type("application/manifest+json", ".webmanifest")

app = Flask(__name__)


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
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
