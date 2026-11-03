// Проверяет логику браузера. Даты сверяются с той же таблицей, что и в Python,
// поэтому оба языка обязаны считать одинаково.
const fs = require("fs");
const path = require("path");

Object.assign(globalThis, require("../static/dates.js"));
const { eventsForTab, matchesFilters, emptyFilters } = require("../static/filters.js");

const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "date_cases.json"), "utf-8"));
let failures = 0;

function check(name, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures += 1;
    console.log(`ОШИБКА: ${name}: получено ${JSON.stringify(actual)}, ожидалось ${JSON.stringify(expected)}`);
  }
}

// Часть 1. Таблица дат.
const todayOf = (item) => item.today || cases.today;
for (const item of cases.today_kz) check(item.name, todayKz(new Date(item.utc)), item.expected);
for (const item of cases.parse_date) check(item.name, isValidDate(item.text), item.valid);
for (const item of cases.status) check(item.name, getStatus(item.start, item.deadline, todayOf(item)), item.expected);
for (const item of cases.urgency) check(item.name, getUrgency(item.deadline, todayOf(item)), item.expected);
for (const item of cases.closing_soon) check(item.name, isClosingSoon(item.start, item.deadline, todayOf(item)), item.expected);

// Часть 2. Фильтры.
const TODAY = "2026-11-10";

function makeEvent(changes) {
  return {
    id: "event", title: "Олимпиада Ёлка", stage: null, type: "olympiad", subjects: ["math"],
    grade_from: 7, grade_to: 9, age_from: null, age_to: null, region: "kazakhstan",
    season: "2026-2027", registration_start: "2026-11-01", registration_deadline: "2026-11-20",
    format: "online", fee_kzt: null, ...changes,
  };
}

function passes(eventChanges, filterChanges) {
  return matchesFilters(makeEvent(eventChanges), { ...emptyFilters(), ...filterChanges });
}

check("без фильтров подходит всё", passes({}, {}), true);
check("поиск без учёта регистра и ё", passes({}, { search: "елка" }), true);
check("поиск мимо", passes({}, { search: "физика" }), false);
check("класс внутри диапазона", passes({}, { grade: 9 }), true);
check("класс вне диапазона", passes({}, { grade: 10 }), false);
check("возраст: ограничения нет", passes({}, { age: 13 }), true);
check("возраст внутри границ", passes({ age_from: 12, age_to: 15 }, { age: 13 }), true);
check("возраст младше границы", passes({ age_from: 14 }, { age: 13 }), false);
check("возраст старше границы", passes({ age_to: 12 }, { age: 13 }), false);
check("предмет совпал", passes({ subjects: ["math", "ai"] }, { subjects: ["ai", "physics"] }), true);
check("предмет не совпал", passes({}, { subjects: ["physics"] }), false);
check("раздел Казахстан", passes({}, { region: "kazakhstan" }), true);
check("раздел международные", passes({}, { region: "international" }), false);
check("тип не совпал", passes({}, { type: "contest" }), false);
check("формат не совпал", passes({}, { format: "offline" }), false);
check("сезон совпал", passes({}, { season: "2026-2027" }), true);
check("сезон не совпал", passes({}, { season: "2025-2026" }), false);

// Стоимость. Цена выбирается как верхняя граница, поэтому цена 2000 входит и в «до 5000».
check("бесплатно подходит", passes({ fee_kzt: 0 }, { cost: "free" }), true);
check("платное не бесплатно", passes({ fee_kzt: 100 }, { cost: "free" }), false);
check("неизвестная цена не бесплатна", passes({}, { cost: "free" }), false);
check("неизвестная цена не платная", passes({}, { cost: "paid" }), false);
check("бесплатное не платное", passes({ fee_kzt: 0 }, { cost: "paid" }), false);
check("платно с любой ценой", passes({ fee_kzt: 100 }, { cost: "paid" }), true);
check("цена до 2000", passes({ fee_kzt: 2000 }, { cost: "paid", priceTier: "2000" }), true);
check("цена выше 2000", passes({ fee_kzt: 2001 }, { cost: "paid", priceTier: "2000" }), false);
check("цена 2000 входит в до 5000", passes({ fee_kzt: 2000 }, { cost: "paid", priceTier: "5000" }), true);
check("цена ровно 25000 не считается больше 25000", passes({ fee_kzt: 25000 }, { cost: "paid", priceTier: "over25000" }), false);
check("цена больше 25000", passes({ fee_kzt: 25001 }, { cost: "paid", priceTier: "over25000" }), true);

// Часть 3. Вкладки.
const catalog = [
  makeEvent({ id: "red", registration_deadline: "2026-11-11" }),
  makeEvent({ id: "later", registration_deadline: "2026-12-20" }),
  makeEvent({ id: "closed", registration_start: "2026-10-01", registration_deadline: "2026-11-09" }),
  makeEvent({ id: "soon", registration_start: "2026-12-01", registration_deadline: "2026-12-05" }),
  makeEvent({ id: "material", type: "material", registration_start: null, registration_deadline: null, season: null }),
];

function idsFor(tab, filterChanges = {}, saved = []) {
  return eventsForTab(catalog, tab, { ...emptyFilters(), ...filterChanges }, TODAY, saved).map((event) => event.id);
}

check("вкладка 14 дней", idsFor("closing"), ["red"]);
check("вкладка всё без закрытых и материалов", idsFor("all"), ["red", "later", "soon"]);
check("мои показывают и закрытое", idsFor("saved", { grade: 11 }, ["closed", "red"]), ["red", "closed"]);
check("материал не показывается в мои отдельно", idsFor("saved", {}, ["material"]), []);

if (failures > 0) {
  console.log(`Ошибок: ${failures}`);
  process.exit(1);
}
console.log("Все проверки логики браузера пройдены.");
