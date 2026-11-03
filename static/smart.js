// Умный поиск на странице: форма, прогресс и результаты.
// Условия поиска нигде не запоминаются и живут только до закрытия страницы.

const SMART_STEPS = ["role_official", "role_international", "role_university", "role_contests", "compare", "verify"];
const SMART_TIMEOUT_MS = 100000; // сколько ждём сервер, прежде чем показать запасной режим
const SMART_MAX_SUBJECTS = 5;

const smart = {
  subjects: [],
  isRunning: false,
};

// Заполняет форму умного поиска.
function buildSmartForm() {
  const grades = Array.from({ length: 12 }, (_, index) => String(index + 1));
  fillSelect("smart-grade", [["", t("choose")], ...grades.map((grade) => [grade, grade])]);
  fillSelect("smart-country", state.countries.map((country) => [country, country]));

  const subjects = [...state.subjects]
    .sort((a, b) => t(`subject_${a}`).localeCompare(t(`subject_${b}`), t("locale")));
  byId("smart-subjects").replaceChildren(...subjects.map((subject) => {
    const chip = makeElement("button", "chip", t(`subject_${subject}`));
    chip.type = "button";
    chip.setAttribute("aria-pressed", "false");
    chip.addEventListener("click", () => {
      const isOn = smart.subjects.includes(subject);
      if (!isOn && smart.subjects.length >= SMART_MAX_SUBJECTS) {
        byId("smart-error").textContent = t("smart_too_many_subjects");
        return;
      }
      byId("smart-error").textContent = "";
      smart.subjects = isOn ? smart.subjects.filter((item) => item !== subject) : [...smart.subjects, subject];
      chip.classList.toggle("is-on", !isOn);
      chip.setAttribute("aria-pressed", String(!isOn));
    });
    return chip;
  }));

  byId("smart-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runSmartSearch();
  });
}

// Читает форму. Если чего-то не хватает, показывает подсказку и возвращает null.
function readSmartForm() {
  const grade = Number(byId("smart-grade").value);
  if (!grade) {
    byId("smart-error").textContent = t("smart_need_grade");
    return null;
  }
  if (smart.subjects.length === 0) {
    byId("smart-error").textContent = t("smart_need_subject");
    return null;
  }
  const age = byId("smart-age").valueAsNumber;
  if (!Number.isNaN(age) && (!Number.isInteger(age) || age < 3 || age > 30)) {
    byId("smart-error").textContent = t("smart_bad_age");
    return null;
  }
  byId("smart-error").textContent = "";
  return {
    grade,
    age: Number.isNaN(age) ? null : age,
    country: byId("smart-country").value,
    subjects: smart.subjects,
  };
}

// Показывает список этапов и отмечает состояние каждого.
function showSteps(states) {
  byId("smart-progress").hidden = false;
  byId("smart-progress").replaceChildren(...SMART_STEPS.map((name) => {
    const stepState = states[name] || "waiting";
    const mark = { waiting: "○", running: "…", done: "✓" }[stepState];
    const row = makeElement("li", `smart-step smart-step-${stepState}`);
    row.append(makeElement("span", "smart-step-mark", mark));
    row.append(makeElement("span", "", t(`step_${name}`)));
    return row;
  }));
}

// Запускает поиск и читает ответ сервера по строкам, пока он приходит.
async function runSmartSearch() {
  if (smart.isRunning) return;
  const body = readSmartForm();
  if (body === null) return;

  smart.isRunning = true;
  byId("smart-submit").disabled = true;
  byId("smart-notice").hidden = true;
  byId("smart-results").replaceChildren();
  const states = {};
  showSteps(states);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), SMART_TIMEOUT_MS);
  try {
    const response = await fetch("/api/smart-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`smart search: ${response.status}`);

    const result = await readEvents(response, (event) => {
      states[event.step] = event.state;
      showSteps(states);
    });
    if (result === null) throw new Error("smart search: no result");
    showSmartResult(result);
  } catch (error) {
    // Сервер недоступен или не ответил вовремя: показываем сохранённые результаты.
    console.error(error);
    await showSavedDemo();
  } finally {
    clearTimeout(timer);
    smart.isRunning = false;
    byId("smart-submit").disabled = false;
    byId("smart-progress").hidden = true;
  }
}

// Разбирает поток: каждая строка — отдельное событие. Возвращает итоговый результат.
async function readEvents(response, onStep) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  const handleLine = (line) => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === "step") onStep(event);
    if (event.type === "result") result = event;
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    lines.forEach(handleLine);
  }
  handleLine(buffer);
  return result;
}

// Запасной режим, если сервер совсем недоступен. Копия лежит в памяти устройства.
async function showSavedDemo() {
  try {
    showSmartResult(await loadJson("/api/smart-search/demo"));
  } catch (error) {
    console.error(error);
    showNotice(t("smart_failed"));
  }
}

function showNotice(text) {
  byId("smart-notice").hidden = false;
  byId("smart-notice").textContent = text;
}

// Честно объясняет, откуда взялись результаты.
function noticeFor(result) {
  if (result.source === "demo") return t(`smart_notice_${result.notice || "unavailable"}`);
  if (result.source === "stub") return t("smart_notice_stub");
  return null;
}

function showSmartResult(result) {
  const notice = noticeFor(result);
  if (notice) showNotice(notice);

  // Прошедшие события браузер убирает ещё раз: сохранённая копия могла устареть.
  const shown = result.results.filter((item) => (
    getStatus(item.registration_start, item.registration_deadline, state.today) !== "closed"
  ));
  if (shown.length === 0) {
    byId("smart-results").replaceChildren(makeElement("p", "message", t("smart_empty")));
    return;
  }
  byId("smart-results").replaceChildren(...shown.map(makeSmartCard));
}

// Карточка результата с уровнем доверия.
function makeSmartCard(item) {
  const card = makeElement("article", "event-card smart-card");
  const status = getStatus(item.registration_start, item.registration_deadline, state.today);

  const badges = makeElement("div", "badges");
  badges.append(makeElement("span", `badge trust-${item.trust}`, t(`trust_${item.trust}`)));
  badges.append(makeElement("span", `badge status-${status}`, t(`status_${status}`)));
  card.append(badges);

  card.append(makeElement("h2", "event-title", item.title));
  if (item.summary) card.append(makeElement("p", "event-summary", item.summary));
  if (item.subjects.length > 0) card.append(makeElement("p", "event-row", item.subjects.join(", ")));
  if (item.grade_from !== null && item.grade_to !== null) {
    card.append(makeElement("p", "event-row", `${t("grades")}: ${item.grade_from}–${item.grade_to}`));
  }
  card.append(makeRow("deadline", formatDate(item.registration_deadline), "event-row event-deadline"));
  card.append(makeRow("event_date", formatDate(item.event_date)));
  if (item.date_quote) card.append(makeElement("blockquote", "smart-quote", item.date_quote));

  const links = makeElement("div", "card-links");
  links.append(makeLink(t("official_source"), item.official_url));
  card.append(links);
  return card;
}
