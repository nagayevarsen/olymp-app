// Логика страницы: загружаем тексты и события, затем рисуем карточки.

// Тексты интерфейса на выбранном языке. Пока есть только русский.
let texts = {};

// Возвращает текст по его коду. Если текста нет, показывает сам код.
function t(key) {
  return texts[key] || key;
}

// Создаёт элемент страницы с текстом. textContent показывает данные как
// обычный текст, поэтому код из файла с данными не сможет запуститься.
function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

// Строка вида "Название: значение". Если даты нет, просим уточнить у организатора.
function makeDateRow(label, value) {
  return makeElement("p", "event-row", `${t(label)}: ${value || t("not_announced")}`);
}

// Текст метки срочности.
function urgencyText(event) {
  if (event.days_left === 0) return t("last_day");
  return `${t("days_left")}: ${event.days_left}`;
}

// Собирает одну карточку события.
function makeCard(event) {
  const card = makeElement("article", "event-card");

  const badges = makeElement("div", "badges");
  if (event.is_example) {
    badges.append(makeElement("span", "badge badge-example", t("example_badge")));
  }
  badges.append(makeElement("span", "badge", t(`type_${event.type}`)));
  if (event.status) {
    badges.append(makeElement("span", "badge", t(`status_${event.status}`)));
  }
  // Цвет срочности показываем только у открытых событий.
  if (event.status === "open" && event.urgency) {
    badges.append(makeElement("span", `badge urgency-${event.urgency}`, urgencyText(event)));
  }
  card.append(badges);

  card.append(makeElement("h2", "event-title", event.title));
  if (event.stage) card.append(makeElement("p", "event-row", event.stage));
  card.append(makeElement("p", "event-summary", event.summary));

  const subjects = event.subjects.map((subject) => t(`subject_${subject}`)).join(", ");
  card.append(makeElement("p", "event-row", subjects));
  card.append(makeElement(
    "p",
    "event-row",
    `${t("grades")}: ${event.grade_from}–${event.grade_to} · ${event.country} · ${t(`format_${event.format}`)}`,
  ));

  // У учебных материалов нет дат регистрации.
  if (event.type !== "material") {
    card.append(makeDateRow("registration_start", event.registration_start));
    card.append(makeDateRow("deadline", event.registration_deadline));
    card.append(makeDateRow("event_date", event.event_date));
  }

  const link = makeElement("a", "event-link", t("official_source"));
  link.href = event.source_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer"; // чужой сайт не получит доступа к нашей вкладке
  card.append(link);

  card.append(makeElement("p", "event-checked", `${t("checked")}: ${event.last_checked}`));
  return card;
}

// Загружает JSON с сервера. Если сервер вернул ошибку, сообщает об этом.
async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

async function start() {
  const message = document.getElementById("message");
  try {
    texts = await loadJson("/static/i18n/ru.json");
    document.getElementById("app-title").textContent = t("app_title");

    const data = await loadJson("/api/events");
    // Прошедшие события не показываем как действующие.
    const activeEvents = data.events.filter((event) => event.status !== "closed");

    document.getElementById("event-list").append(...activeEvents.map(makeCard));
    message.textContent = activeEvents.length === 0 ? t("empty_list") : "";
  } catch (error) {
    console.error(error);
    message.textContent = t("catalog_error");
  }
}

start();
