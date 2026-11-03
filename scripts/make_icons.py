"""Рисует собственные иконки приложения: медаль на синем фоне.

Запуск: .venv\\Scripts\\python scripts\\make_icons.py
Посторонние библиотеки не нужны: PNG собирается стандартными средствами Python.
"""

import math
import struct
import zlib
from pathlib import Path

ICONS = Path(__file__).parent.parent / "static" / "icons"

BLUE = (40, 81, 200)
RIBBON = (168, 193, 255)
GOLD = (242, 192, 55)
DARK_GOLD = (201, 145, 18)


def mix(under, over, amount):
    """Смешивает два цвета. amount от 0 (только нижний) до 1 (только верхний)."""
    return tuple(round(a + (b - a) * amount) for a, b in zip(under, over))


def coverage(distance, pixel):
    """Сглаживает края фигур: 1 внутри, 0 снаружи, плавно на границе."""
    return max(0.0, min(1.0, 0.5 - distance / pixel))


def segment_distance(x, y, ax, ay, bx, by):
    """Расстояние от точки до отрезка: так рисуем ленты медали."""
    dx, dy = bx - ax, by - ay
    part = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - ax - part * dx, y - ay - part * dy)


def rounded_square_distance(x, y, radius):
    """Расстояние до края квадрата со скруглёнными углами."""
    qx = abs(x - 0.5) - (0.5 - radius)
    qy = abs(y - 0.5) - (0.5 - radius)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    return outside + min(max(qx, qy), 0.0) - radius


def pixel_color(x, y, pixel, rounded):
    """Возвращает цвет точки. x и y заданы долями от размера: от 0 до 1."""
    color = BLUE
    for start_x in (0.36, 0.64):
        distance = segment_distance(x, y, start_x, 0.2, 0.5, 0.52) - 0.06
        color = mix(color, RIBBON, coverage(distance, pixel))

    disk = math.hypot(x - 0.5, y - 0.6)
    color = mix(color, GOLD, coverage(disk - 0.22, pixel))
    ring = abs(disk - 0.15) - 0.015
    color = mix(color, DARK_GOLD, coverage(ring, pixel))

    alpha = coverage(rounded_square_distance(x, y, 0.2), pixel) if rounded else 1.0
    return (*color, round(alpha * 255))


def write_png(path, size, rounded):
    """Рисует картинку по точкам и сохраняет её в формате PNG."""
    pixel = 1 / size
    rows = bytearray()
    for row in range(size):
        rows.append(0)  # в PNG каждая строка начинается с байта способа сжатия
        for column in range(size):
            rows.extend(pixel_color((column + 0.5) / size, (row + 0.5) / size, pixel, rounded))

    def chunk(kind, data):
        checksum = zlib.crc32(kind + data)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def main():
    ICONS.mkdir(parents=True, exist_ok=True)
    write_png(ICONS / "icon-192.png", 192, rounded=True)
    write_png(ICONS / "icon-512.png", 512, rounded=True)
    # Android сам обрезает такую иконку по форме, поэтому фон идёт до самого края.
    write_png(ICONS / "icon-maskable-512.png", 512, rounded=False)
    # Значок для экрана iPhone: система сама скругляет углы.
    write_png(ICONS / "apple-touch-icon.png", 180, rounded=False)


if __name__ == "__main__":
    main()
