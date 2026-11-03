# Поиск олимпиад

Приложение для поиска действующих официальных олимпиад, конкурсов и учебных материалов для школьников. Проект находится в разработке.

## Установка (Windows)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Запуск

```powershell
.venv\Scripts\python app.py
```

Затем откройте http://127.0.0.1:5000

## Проверка данных после правки `data/events.json`

```powershell
.venv\Scripts\python -m catalog.events
```

## Запуск тестов

```powershell
.venv\Scripts\python -m pytest
```
