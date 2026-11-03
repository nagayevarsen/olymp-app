// Логика дат для браузера. Это копия catalog/dates.py: без неё приложение
// офлайн показывало бы устаревшие статусы. Обе версии проверяются одной
// таблицей tests/date_cases.json. Меняете правило здесь — меняйте и в Python.

const KZ_OFFSET_MS = 5 * 60 * 60 * 1000; // Казахстан: UTC+5
const DAY_MS = 24 * 60 * 60 * 1000;
const CLOSING_SOON_DAYS = 14;

// Сегодняшняя дата в Казахстане как текст ГГГГ-ММ-ДД. Часовой пояс устройства не важен.
function todayKz(now = new Date()) {
  return new Date(now.getTime() + KZ_OFFSET_MS).toISOString().slice(0, 10);
}

// Проверяет, что это настоящая дата в формате ГГГГ-ММ-ДД.
function isValidDate(text) {
  if (typeof text !== "string" || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(text)) return false;
  if (text.startsWith("0000")) return false;
  const parsed = new Date(`${text}T00:00:00Z`);
  // Если дня нет в календаре, дата не совпадёт с исходным текстом.
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === text;
}

// Сколько дней до дедлайна: 0 — сегодня, меньше нуля — прошёл, null — неизвестно.
function daysUntil(deadline, today) {
  if (!isValidDate(deadline)) return null;
  return Math.round((Date.parse(`${deadline}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / DAY_MS);
}

// Статус регистрации. Даты в формате ГГГГ-ММ-ДД можно сравнивать как текст.
function getStatus(start, deadline, today) {
  const validStart = isValidDate(start) ? start : null;
  const validDeadline = isValidDate(deadline) ? deadline : null;

  if (validDeadline !== null && validDeadline < today) return "closed";
  if (validStart !== null && validStart > today) return "soon";
  if (validDeadline === null) return "unannounced";
  return "open";
}

// Цвет срочности или null, если метка не нужна.
function getUrgency(deadline, today) {
  const days = daysUntil(deadline, today);
  if (days === null || days < 0) return null;
  if (days < 3) return "red";
  if (days < 7) return "yellow";
  return "green";
}

// Открыто ли событие и закрывается ли оно в ближайшие 14 дней.
function isClosingSoon(start, deadline, today) {
  if (getStatus(start, deadline, today) !== "open") return false;
  return daysUntil(deadline, today) <= CLOSING_SOON_DAYS;
}

// Эта часть нужна только для тестов в Node.js. В браузере она не выполняется.
if (typeof module !== "undefined") {
  module.exports = { todayKz, isValidDate, daysUntil, getStatus, getUrgency, isClosingSoon };
}
