// Работа со страницей: загрузка данных, вкладки, форма, карточки и сохранение.
// Правила отбора лежат в filters.js, правила дат — в dates.js.

const SAVED_KEY = "olymp.saved";
const FILTERS_KEY = "olymp.filters";

const PRICE_TIERS = ["2000", "5000", "15000", "25000", "over25000"];

// Всё, что приложение сейчас помнит.
const state = {
  texts: {},
  events: [],
  tab: "closing",
  filters: emptyFilters(),
  savedIds: [],
  today: todayKz(),
};

// Короткий доступ к элементу страницы по его id.
const byId = (id) => document.getElementById(id);

// Возвращает текст по коду. Если текста нет, показывает сам код.
function t(key) {
  return state.texts[key] || key;
}

// ---------- Память браузера ----------
// Браузер может запретить доступ к памяти, например в приватном режиме.
// Тогда приложение работает как обычно, только ничего не запоминает.

function readStored(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value === null ? fallback : value;
  } catch {
    return fallback;
  }
}

function writeStored(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Память недоступна: данные останутся только до закрытия страницы.
  }
}

// Восстанавливает условия поиска. Дату и текст поиска не запоминаем:
// они нужны для одного конкретного поиска.
function loadFilters() {
  const stored = readStored(FILTERS_KEY, {});
  const filters = { ...emptyFilters(), ...stored, search: "", date: "" };
  if (!Array.isArray(filters.subjects)) filters.subjects = [];
  return filters;
}

function saveFilters() {
  const { search, date, ...toRemember } = state.filters;
  writeStored(FILTERS_KEY, toRemember);
}

function loadSavedIds() {
  const stored = readStored(SAVED_KEY, []);
  return Array.isArray(stored) ? stored.filter((id) => typeof id === "string") : [];
}

// ---------- Оформление значений ----------

// Создаёт элемент с текстом. textContent показывает данные как обычный текст,
// поэтому код из файла с данными не сможет запуститься.
function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

// Показывает дату словами, например «11 ноября 2026 г.»
function formatDate(text) {
  if (!isValidDate(text)) return t("not_announced");
  return new Intl.DateTimeFormat(t("locale"), {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  }).format(new Date(`${text}T00:00:00Z`));
}

function formatFee(fee) {
  if (fee === null) return t("not_announced");
  if (fee === 0) return t("fee_free");
  return `${new Intl.NumberFormat(t("locale")).format(fee)} ${t("currency")}`;
}

function formatAge(event) {
  const parts = [];
  if (event.age_from !== null) parts.push(`${t("age_from")} ${event.age_from}`);
  if (event.age_to !== null) parts.push(`${t("age_to")} ${event.age_to}`);
  return parts.join(" ");
}

// Показывает текущие дату и время в Казахстане.
function updateClock() {
  const now = new Date();
  const shifted = new Date(now.getTime() + KZ_OFFSET_MS);
  const formatted = new Intl.DateTimeFormat(t("locale"), {
    day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC",
  }).format(shifted);
  byId("clock").textContent = `${t("clock_prefix")}: ${formatted}`;

  // Наступил новый день: статусы и метки нужно пересчитать.
  const newToday = todayKz(now);
  if (newToday !== state.today) {
    state.today = newToday;
    byId("date").min = newToday;
    render();
  }
}

// ---------- Сохранение ----------

// Все этапы той же олимпиады. Если олимпиада одна, в списке будет только она сама.
function stagesOf(event) {
  if (!event.series_id) return [event];
  return state.events.filter((other) => other.series_id === event.series_id);
}

function setSaved(ids, shouldSave) {
  const others = state.savedIds.filter((id) => !ids.includes(id));
  state.savedIds = shouldSave ? [...others, ...ids] : others;
  writeStored(SAVED_KEY, state.savedIds);
  byId("transfer-link").hidden = true;
  byId("transfer-note").textContent = "";
  render();
}

function makeSaveButton(label, isOn, ids) {
  const button = makeElement("button", `button ${isOn ? "button-on" : "button-secondary"}`, label);
  button.type = "button";
  button.setAttribute("aria-pressed", String(isOn));
  button.addEventListener("click", () => setSaved(ids, !isOn));
  return button;
}

function makeSaveButtons(event) {
  const box = makeElement("div", "card-actions");
  const stages = stagesOf(event);
  const isSaved = state.savedIds.includes(event.id);

  if (stages.length > 1) {
    box.append(makeSaveButton(t(isSaved ? "saved_stage" : "save_stage"), isSaved, [event.id]));
    const stageIds = stages.map((stage) => stage.id);
    const allSaved = stageIds.every((id) => state.savedIds.includes(id));
    box.append(makeSaveButton(t(allSaved ? "saved_series" : "save_series"), allSaved, stageIds));
  } else {
    box.append(makeSaveButton(t(isSaved ? "saved" : "save"), isSaved, [event.id]));
  }
  return box;
}

// Создаёт ссылку со списком сохранённых событий. Сервер её не хранит.
async function makeTransferLink() {
  const url = new URL(window.location.href);
  url.search = "";
  url.hash = "";
  url.searchParams.set("saved", state.savedIds.join(","));

  const field = byId("transfer-link");
  field.value = url.toString();
  field.hidden = false;
  try {
    await navigator.clipboard.writeText(field.value);
    byId("transfer-note").textContent = `${t("link_copied")} ${t("link_update_note")}`;
  } catch {
    // Браузер не разрешил копирование: пользователь скопирует ссылку сам.
    field.select();
    byId("transfer-note").textContent = `${t("link_manual")} ${t("link_update_note")}`;
  }
}

// Добавляет события из ссылки для переноса и убирает её из адресной строки.
function importSavedFromLink() {
  const url = new URL(window.location.href);
  const value = url.searchParams.get("saved");
  if (value === null) return;

  // Берём только те id, которые действительно есть в каталоге.
  const known = state.events.map((event) => event.id);
  const incoming = value.split(",").filter((id) => known.includes(id));
  const added = incoming.filter((id) => !state.savedIds.includes(id));
  state.savedIds = [...state.savedIds, ...added];
  writeStored(SAVED_KEY, state.savedIds);

  url.searchParams.delete("saved");
  history.replaceState(null, "", url);
  state.tab = "saved";
  byId("transfer-note").textContent = `${t("imported")}: ${added.length}`;
}

// ---------- Карточка события ----------

function makeRow(label, value) {
  return makeElement("p", "event-row", `${t(label)}: ${value}`);
}

function makeCard(event) {
  const card = makeElement("article", "event-card");
  const isMaterial = event.type === "material";
  // Статус считаем заново в браузере, поэтому офлайн он тоже будет верным.
  const status = isMaterial
    ? null
    : getStatus(event.registration_start, event.registration_deadline, state.today);

  const badges = makeElement("div", "badges");
  if (event.is_example) badges.append(makeElement("span", "badge badge-example", t("example_badge")));
  badges.append(makeElement("span", "badge", t(`type_${event.type}`)));
  if (status) badges.append(makeElement("span", `badge status-${status}`, t(`status_${status}`)));
  // Метку срочности показываем только у открытых событий.
  if (status === "open") {
    const days = daysUntil(event.registration_deadline, state.today);
    const text = days === 0 ? t("last_day") : `${t("days_left")}: ${days}`;
    const color = getUrgency(event.registration_deadline, state.today);
    badges.append(makeElement("span", `badge urgency-${color}`, text));
  }
  card.append(badges);

  card.append(makeElement("h2", "event-title", event.title));
  if (event.stage) card.append(makeElement("p", "event-stage", event.stage));
  card.append(makeElement("p", "event-summary", event.summary));

  const subjects = event.subjects.map((subject) => t(`subject_${subject}`)).join(", ");
  card.append(makeElement("p", "event-row", subjects));
  card.append(makeElement(
    "p",
    "event-row",
    `${t("grades")}: ${event.grade_from}–${event.grade_to} · ${event.country} · ${t(`format_${event.format}`)}`,
  ));
  const ageText = formatAge(event);
  if (ageText) card.append(makeRow("age", ageText));
  if (event.season) card.append(makeRow("season", event.season));
  card.append(makeRow("fee", formatFee(event.fee_kzt)));

  // У учебных материалов нет дат регистрации.
  if (!isMaterial) {
    card.append(makeRow("registration_start", formatDate(event.registration_start)));
    card.append(makeRow("deadline", formatDate(event.registration_deadline)));
    card.append(makeRow("event_date", formatDate(event.event_date)));
  }

  const link = makeElement("a", "event-link", t("official_source"));
  link.href = event.source_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer"; // чужой сайт не получит доступа к нашей вкладке
  card.append(link);

  card.append(makeElement("p", "event-checked", `${t("checked")}: ${formatDate(event.last_checked)}`));
  card.append(makeSaveButtons(event));
  return card;
}

// ---------- Форма поиска ----------

function fillSelect(id, options) {
  const select = byId(id);
  select.replaceChildren(...options.map(([value, label]) => {
    const option = makeElement("option", "", label);
    option.value = value;
    return option;
  }));
}

// Заполняет списки. Предметы и учебные годы берём из самого каталога.
function buildForm() {
  const grades = Array.from({ length: 11 }, (_, index) => String(index + 1));
  fillSelect("grade", [["", t("any")], ...grades.map((grade) => [grade, grade])]);

  const seasons = [...new Set(state.events.map((event) => event.season).filter(Boolean))].sort().reverse();
  fillSelect("season", [["", t("any")], ...seasons.map((season) => [season, season])]);

  fillSelect("type", [["", t("any")], ...["olympiad", "contest", "material"].map((type) => [type, t(`type_${type}`)])]);
  fillSelect("format", [["", t("any")], ...["offline", "online"].map((format) => [format, t(`format_${format}`)])]);
  fillSelect("cost", [["", t("any_cost")], ["free", t("cost_free")], ["paid", t("cost_paid")]]);
  fillSelect("price-tier", [["", t("any_cost")], ...PRICE_TIERS.map((tier) => [tier, t(`price_${tier}`)])]);

  const subjects = [...new Set(state.events.flatMap((event) => event.subjects))]
    .sort((a, b) => t(`subject_${a}`).localeCompare(t(`subject_${b}`), t("locale")));
  byId("subjects").replaceChildren(...subjects.map((subject) => {
    const chip = makeElement("button", "chip", t(`subject_${subject}`));
    chip.type = "button";
    chip.dataset.subject = subject;
    chip.addEventListener("click", () => {
      const chosen = state.filters.subjects;
      state.filters.subjects = chosen.includes(subject)
        ? chosen.filter((item) => item !== subject)
        : [...chosen, subject];
      filtersChanged();
    });
    return chip;
  }));

  byId("date").min = state.today;
}

// Показывает значения из state в полях формы.
function showFiltersInForm() {
  const filters = state.filters;
  byId("search").value = filters.search;
  byId("grade").value = filters.grade === null ? "" : String(filters.grade);
  byId("age").value = filters.age === null ? "" : String(filters.age);
  byId("date").value = filters.date;
  byId("season").value = filters.season;
  byId("type").value = filters.type;
  byId("format").value = filters.format;
  byId("cost").value = filters.cost;
  byId("price-tier").value = filters.priceTier;
}

// Читает значения из полей формы в state.
function readFiltersFromForm() {
  const filters = state.filters;
  filters.search = byId("search").value;
  filters.grade = byId("grade").value === "" ? null : Number(byId("grade").value);
  const age = byId("age").valueAsNumber;
  filters.age = Number.isInteger(age) ? age : null;
  filters.date = byId("date").value;
  filters.season = byId("season").value;
  filters.type = byId("type").value;
  filters.format = byId("format").value;
  filters.cost = byId("cost").value;
  // Цена имеет смысл только для платных событий.
  filters.priceTier = filters.cost === "paid" ? byId("price-tier").value : "";
}

function filtersChanged() {
  saveFilters();
  render();
}

function resetFilters() {
  state.filters = emptyFilters();
  showFiltersInForm();
  filtersChanged();
}

// Считает выбранные условия для подписи на кнопке «Фильтры».
function countActiveFilters() {
  const { search, region, subjects, ...others } = state.filters;
  const filled = Object.values(others).filter((value) => value !== "" && value !== null).length;
  return filled + subjects.length;
}

// ---------- Отрисовка экрана ----------

function render() {
  const { tab, filters } = state;
  const isSavedTab = tab === "saved";

  document.querySelectorAll(".tab").forEach((button) => {
    const isOn = button.dataset.tab === tab;
    button.classList.toggle("is-on", isOn);
    button.setAttribute("aria-pressed", String(isOn));
  });
  document.querySelectorAll(".segment").forEach((button) => {
    const isOn = button.dataset.region === filters.region;
    button.classList.toggle("is-on", isOn);
    button.setAttribute("aria-pressed", String(isOn));
  });
  document.querySelectorAll(".chip").forEach((chip) => {
    const isOn = filters.subjects.includes(chip.dataset.subject);
    chip.classList.toggle("is-on", isOn);
    chip.setAttribute("aria-pressed", String(isOn));
  });

  byId("search-form").hidden = isSavedTab;
  byId("date-field").hidden = tab === "prepare"; // у материалов нет регистрации
  byId("price-field").hidden = filters.cost !== "paid";

  const count = countActiveFilters();
  byId("filter-count").hidden = count === 0;
  byId("filter-count").textContent = String(count);

  const found = eventsForTab(state.events, tab, filters, state.today, state.savedIds);
  byId("event-list").replaceChildren(...found.map(makeCard));

  byId("transfer").hidden = !isSavedTab || state.savedIds.length === 0;

  const hasFilters = count > 0 || filters.search !== "" || filters.region !== "";
  const isEmpty = found.length === 0;
  byId("empty-reset").hidden = !(isEmpty && !isSavedTab && hasFilters);

  if (isEmpty) {
    byId("message").textContent = t(`empty_${tab}`);
  } else if (tab === "closing") {
    byId("message").textContent = `${t("title_closing")}. ${t("found")}: ${found.length}`;
  } else {
    byId("message").textContent = `${t("found")}: ${found.length}`;
  }
}

// ---------- Запуск ----------

// Подставляет переведённые тексты в элементы с пометкой data-i18n.
function applyTexts() {
  document.title = t("app_title");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
}

function connectEvents() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.tab = button.dataset.tab;
      byId("transfer-note").textContent = "";
      byId("transfer-link").hidden = true;
      render();
    });
  });
  document.querySelectorAll(".segment").forEach((button) => {
    button.addEventListener("click", () => {
      state.filters.region = button.dataset.region;
      filtersChanged();
    });
  });
  const form = byId("search-form");
  const onFormChange = () => {
    readFiltersFromForm();
    filtersChanged();
  };
  form.addEventListener("input", onFormChange);
  form.addEventListener("change", onFormChange);
  form.addEventListener("submit", (event) => event.preventDefault());
  byId("reset").addEventListener("click", resetFilters);
  byId("empty-reset").addEventListener("click", resetFilters);
  byId("make-link").addEventListener("click", makeTransferLink);
}

// Загружает JSON с сервера. Если сервер вернул ошибку, сообщает об этом.
async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

async function start() {
  try {
    state.texts = await loadJson("/static/i18n/ru.json");
    applyTexts();
    updateClock();
    setInterval(updateClock, 30000);

    const data = await loadJson("/api/events");
    state.events = data.events;
    state.filters = loadFilters();
    state.savedIds = loadSavedIds();

    buildForm();
    showFiltersInForm();
    connectEvents();
    importSavedFromLink();

    // Показываем сообщение об импорте, а render его не трогает.
    render();
  } catch (error) {
    console.error(error);
    byId("message").textContent = t("catalog_error") === "catalog_error"
      ? "Не удалось загрузить каталог."
      : t("catalog_error");
  }
}

start();
