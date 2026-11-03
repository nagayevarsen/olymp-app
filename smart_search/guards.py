"""Защита от лишних расходов: кэш, лимит запросов в день и лимит одновременных поисков.

Всё хранится в памяти сервера и пропадает при перезапуске. Поэтому главная защита
бюджета — жёсткий лимит расходов в личном кабинете сервиса ИИ.
"""

import threading
import time


class ResultCache:
    """Хранит готовые результаты. Они не привязаны к человеку и живут ограниченное время."""

    def __init__(self, ttl_seconds=6 * 60 * 60, max_items=200, clock=time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self.clock = clock
        self.items = {}
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            item = self.items.get(key)
            if item is None:
                return None
            saved_at, value = item
            if self.clock() - saved_at > self.ttl_seconds:
                del self.items[key]
                return None
            return value

    def put(self, key, value):
        with self.lock:
            if len(self.items) >= self.max_items and key not in self.items:
                # Места нет: удаляем самую старую запись.
                oldest = min(self.items, key=lambda name: self.items[name][0])
                del self.items[oldest]
            self.items[key] = (self.clock(), value)


class DailyLimit:
    """Считает живые поиски за день. С новым днём счётчик начинается заново."""

    def __init__(self, limit):
        self.limit = limit
        self.day = None
        self.used = 0
        self.lock = threading.Lock()

    def try_take(self, today):
        """Возвращает True, если поиск разрешён, и сразу учитывает его."""
        with self.lock:
            if today != self.day:
                self.day = today
                self.used = 0
            if self.used >= self.limit:
                return False
            self.used += 1
            return True
