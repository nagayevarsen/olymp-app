"""Сервер приложения. Он отдаёт страницу и список событий.

Запуск: .venv\\Scripts\\python app.py
После этого откройте в браузере http://127.0.0.1:5000
"""

from flask import Flask, jsonify, render_template

from catalog.dates import today_kz
from catalog.events import EVENTS_FILE, get_catalog

app = Flask(__name__)


@app.get("/")
def home():
    """Отдаёт главную страницу."""
    return render_template("index.html")


@app.get("/api/events")
def api_events():
    """Отдаёт список событий с уже посчитанными статусами."""
    today = today_kz()
    try:
        events = get_catalog(today, EVENTS_FILE)
    except (OSError, ValueError):
        # Файла нет или в нём ошибка: записываем причину в журнал сервера,
        # а странице сообщаем, что каталог сейчас недоступен.
        app.logger.exception("Не удалось прочитать каталог")
        return jsonify(error="catalog_unavailable"), 503
    return jsonify(today=today.isoformat(), events=events)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
