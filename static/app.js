// Работа со страницей: загрузка данных, вкладки, форма, карточки и сохранение.
// Правила отбора лежат в filters.js, правила дат — в dates.js.

const SAVED_KEY = "olymp.saved";
const FILTERS_KEY = "olymp.filters";

const PRICE_TIERS = ["2000", "5000", "15000", "25000", "over25000"];

// Всё, что приложение сейчас помнит.
const state = {
  texts: {},
  events: [],
  archives: [],
  subjects: [],
  countries: [],
  dataToday: null, // день, когда сервер подготовил данные
  dataLoadedAt: null, // точное время этого ответа сервера
  tab: "closing",
  filters: emptyFilters(),
  savedIds: [],
  openIds: new Set(), // какие карточки сейчас раскрыты
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

// Восстанавливает условия поиска. Текст поиска не запоминаем:
// он нужен для одного конкретного поиска.
function loadFilters() {
  const stored = readStored(FILTERS_KEY, {});
  const filters = { ...emptyFilters(), ...stored, search: "" };
  if (!Array.isArray(filters.subjects)) filters.subjects = [];
  // Раньше в типах был «учебный материал»: такой сохранённый выбор больше не действует.
  if (filters.type === "material") filters.type = "";
  return filters;
}

function saveFilters() {
  const { search, ...toRemember } = state.filters;
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

// Показывает момент времени с датой и часами по времени Казахстана.
function formatMoment(moment) {
  const shifted = new Date(moment.getTime() + KZ_OFFSET_MS);
  return new Intl.DateTimeFormat(t("locale"), {
    day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC",
  }).format(shifted);
}

// Показывает текущие дату и время в Казахстане.
function updateClock() {
  const now = new Date();
  byId("clock").textContent = `${t("clock_prefix")}: ${formatMoment(now)}`;

  // Наступил новый день: статусы и метки нужно пересчитать.
  const newToday = todayKz(now);
  if (newToday !== state.today) {
    state.today = newToday;
    updateOfflineNote();
    render();
  }
}

// Честно предупреждает, если интернета нет или данные загружены не сегодня.
function updateOfflineNote() {
  const note = byId("offline-note");
  const isOld = state.dataToday !== null && state.dataToday !== state.today;
  note.hidden = state.dataToday === null || (navigator.onLine && !isOld);
  if (!note.hidden) {
    // В старой сохранённой копии точного времени может не быть, тогда покажем только дату.
    const loadedAt = new Date(state.dataLoadedAt);
    const when = Number.isNaN(loadedAt.getTime()) ? formatDate(state.dataToday) : formatMoment(loadedAt);
    note.textContent = `${t("offline_note")}: ${when}`;
  }
}

// Подпись на кнопке называет тему, на которую можно переключиться.
function updateThemeButton() {
  byId("theme-toggle").textContent = t(currentTheme() === "dark" ? "theme_to_light" : "theme_to_dark");
}

// ---------- Сохранение ----------

// Все этапы той же олимпиады. Если этап один, в списке будет только сама запись.
function stagesOf(event) {
  if (!event.series_id) return [event];
  return state.events.filter((other) => other.series_id === event.series_id && other.type !== "material");
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

function makeRow(label, value, className = "event-row") {
  return makeElement("p", className, `${t(label)}: ${value}`);
}

// Ссылка на чужой сайт, которая открывается в новой вкладке.
function makeLink(text, href, className = "event-link") {
  const link = makeElement("a", className, text);
  link.href = href;
  link.target = "_blank";
  link.rel = "noopener noreferrer"; // чужой сайт не получит доступа к нашей вкладке
  return link;
}

// Блок регистрации: кнопка на официальный сайт или понятное объяснение, почему её нет.
function makeRegistration(event, status) {
  const box = makeElement("div", "registration");
  if (status === "open") {
    box.append(makeLink(t("register"), event.registration_url || event.source_url, "button button-primary"));
    box.append(makeElement("p", "note", t("register_note")));
  } else if (status === "soon") {
    const text = isValidDate(event.registration_start)
      ? `${t("status_soon")}. ${t("opens_on")}: ${formatDate(event.registration_start)}`
      : t("status_soon");
    box.append(makeElement("p", "registration-note", text));
  } else {
    box.append(makeElement("p", "registration-note", t(`status_${status}`)));
  }
  return box;
}

// Ссылки на задания и решения одной записи архива.
function makeArchiveLinks(item) {
  const links = makeElement("div", "card-links");
  links.append(makeLink(t("archive_tasks"), item.tasks_url));
  if (item.solutions_url) links.append(makeLink(t("archive_solutions"), item.solutions_url));
  return links;
}

// Задания прошлых лет: можно выбрать любой период. Если заданий нет, возвращает null.
function makePastEditions(event) {
  if (!event.series_id) return null;
  const editions = state.archives.filter((item) => item.series_id === event.series_id);
  if (editions.length === 0) return null;

  const box = makeElement("div", "card-section");
  box.append(makeElement("h3", "card-section-title", t("past_tasks")));

  const label = makeElement("label", "card-section-label");
  label.append(makeElement("span", "", t(`period_${event.type}`)));
  const select = makeElement("select", "field");
  editions.forEach((item) => {
    const text = item.stage ? `${item.season} · ${item.stage}` : item.season;
    const option = makeElement("option", "", text);
    option.value = item.id;
    select.append(option);
  });
  label.append(select);
  box.append(label);

  // Сразу показываем самый новый период, а при выборе меняем ссылки.
  let links = makeArchiveLinks(editions[0]);
  box.append(links);
  select.addEventListener("change", () => {
    const newLinks = makeArchiveLinks(editions.find((item) => item.id === select.value));
    links.replaceWith(newLinks);
    links = newLinks;
  });
  return box;
}

// Учебные материалы этой олимпиады. Если их нет, возвращает null.
function makeMaterials(event) {
  if (!event.series_id) return null;
  const materials = state.events.filter((other) => other.type === "material" && other.series_id === event.series_id);
  if (materials.length === 0) return null;

  const box = makeElement("div", "card-section");
  box.append(makeElement("h3", "card-section-title", t("materials")));
  const links = makeElement("div", "card-links card-links-column");
  materials.forEach((material) => links.append(makeLink(material.title, material.source_url)));
  box.append(links);
  return box;
}

// Собирает карточку: сверху краткая часть, а по нажатию открываются подробности.
function makeCard(event) {
  const card = makeElement("details", "event-card");
  card.open = state.openIds.has(event.id);
  card.addEventListener("toggle", () => {
    if (card.open) state.openIds.add(event.id);
    else state.openIds.delete(event.id);
  });

  // Статус считаем заново в браузере, поэтому офлайн он тоже будет верным.
  const status = getStatus(event.registration_start, event.registration_deadline, state.today);

  const summary = makeElement("summary", "card-summary");
  const badges = makeElement("div", "badges");
  if (event.is_example) badges.append(makeElement("span", "badge badge-example", t("example_badge")));
  badges.append(makeElement("span", "badge", t(`type_${event.type}`)));
  badges.append(makeElement("span", `badge status-${status}`, t(`status_${status}`)));
  // Метку срочности показываем только у открытых событий.
  if (status === "open") {
    const days = daysUntil(event.registration_deadline, state.today);
    const text = days === 0 ? t("last_day") : `${t("days_left")}: ${days}`;
    const color = getUrgency(event.registration_deadline, state.today);
    badges.append(makeElement("span", `badge urgency-${color}`, text));
    card.classList.add(`card-${color}`); // цветная полоска на краю карточки
  }
  summary.append(badges);
  summary.append(makeElement("h2", "event-title", event.title));
  if (event.stage) summary.append(makeElement("p", "event-stage", event.stage));
  summary.append(makeRow("deadline", formatDate(event.registration_deadline), "event-row event-deadline"));
  summary.append(makeElement("span", "card-more", t("details")));
  card.append(summary);

  const body = makeElement("div", "card-body");
  body.append(makeRegistration(event, status));
  body.append(makeElement("p", "event-summary", event.summary));
  body.append(makeElement("p", "event-row", event.subjects.map((subject) => t(`subject_${subject}`)).join(", ")));
  body.append(makeElement(
    "p",
    "event-row",
    `${t("grades")}: ${event.grade_from}–${event.grade_to} · ${event.country} · ${t(`format_${event.format}`)}`,
  ));
  const ageText = formatAge(event);
  if (ageText) body.append(makeRow("age", ageText));
  if (event.season) body.append(makeRow("season", event.season));
  body.append(makeRow("fee", formatFee(event.fee_kzt)));
  body.append(makeRow("registration_start", formatDate(event.registration_start)));
  body.append(makeRow("event_date", formatDate(event.event_date)));

  const links = makeElement("div", "card-links");
  links.append(makeLink(t("official_source"), event.source_url));
  body.append(links);
  body.append(makeElement("p", "event-checked", `${t("checked")}: ${formatDate(event.last_checked)}`));

  const pastEditions = makePastEditions(event);
  if (pastEditions) body.append(pastEditions);
  const materials = makeMaterials(event);
  if (materials) body.append(materials);

  body.append(makeSaveButtons(event));
  card.append(body);
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

// Заполняет списки формы.
function buildForm() {
  const grades = Array.from({ length: 12 }, (_, index) => String(index + 1));
  fillSelect("grade", [["", t("any")], ...grades.map((grade) => [grade, grade])]);

  const seasons = state.events.filter((event) => event.type !== "material").map((event) => event.season);
  const uniqueSeasons = [...new Set(seasons.filter(Boolean))].sort().reverse();
  fillSelect("season", [["", t("any")], ...uniqueSeasons.map((season) => [season, season])]);
  // Сохранённого года больше нет в каталоге: сбрасываем его, иначе список будет пустым.
  if (!uniqueSeasons.includes(state.filters.season)) state.filters.season = "";

  fillSelect("type", [["", t("any")], ...["olympiad", "contest"].map((type) => [type, t(`type_${type}`)])]);
  fillSelect("format", [["", t("any")], ...["offline", "online"].map((format) => [format, t(`format_${format}`)])]);
  fillSelect("cost", [["", t("any_cost")], ["free", t("cost_free")], ["paid", t("cost_paid")]]);
  fillSelect("price-tier", [["", t("any_cost")], ...PRICE_TIERS.map((tier) => [tier, t(`price_${tier}`)])]);

  // Показываем все предметы сразу, даже если событий по ним пока нет.
  const subjects = [...state.subjects]
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
}

// Показывает значения из state в полях формы.
function showFiltersInForm() {
  const filters = state.filters;
  byId("search").value = filters.search;
  byId("grade").value = filters.grade === null ? "" : String(filters.grade);
  byId("age").value = filters.age === null ? "" : String(filters.age);
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

  // Умный поиск работает отдельно: у него своя форма и свои результаты.
  const isSmartTab = tab === "smart";
  byId("smart-panel").hidden = !isSmartTab;
  byId("catalog-panel").hidden = isSmartTab;
  if (isSmartTab) return;

  byId("search-form").hidden = isSavedTab;
  byId("price-field").hidden = filters.cost !== "paid";
  // Подпись периода зависит от выбранного типа: олимпиада или конкурс.
  byId("season-label").textContent = t(filters.type ? `period_${filters.type}` : "period_any");

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
  document.querySelectorAll("[data-i18n-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nLabel));
  });
  updateThemeButton();
}

// Подключает офлайн-режим. Браузер разрешает его только на HTTPS и на этом компьютере.
function registerOfflineMode() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/sw.js").catch((error) => console.error(error));
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
  byId("theme-toggle").addEventListener("click", () => {
    toggleTheme();
    updateThemeButton();
  });
  window.addEventListener("online", updateOfflineNote);
  window.addEventListener("offline", updateOfflineNote);
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
    state.archives = data.archives;
    state.subjects = data.subjects;
    state.countries = data.countries;
    state.dataToday = data.today;
    state.dataLoadedAt = data.generated_at;
    state.filters = loadFilters();
    state.savedIds = loadSavedIds();

    buildForm();
    buildSmartForm();
    showFiltersInForm();
    connectEvents();
    importSavedFromLink();

    updateOfflineNote();
    render();
    registerOfflineMode();
  } catch (error) {
    console.error(error);
    byId("message").textContent = t("catalog_error") === "catalog_error"
      ? "Не удалось загрузить каталог."
      : t("catalog_error");
  }
}

start();
