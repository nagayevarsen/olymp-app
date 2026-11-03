// Отбор событий: форма поиска и вкладки. Здесь только логика, без работы со
// страницей, поэтому всё это можно проверить тестами. Работает и офлайн.

// Значения формы, когда ничего не выбрано.
function emptyFilters() {
  return {
    search: "", grade: null, age: null, season: "", subjects: [],
    region: "", type: "", format: "", cost: "", priceTier: "",
  };
}

// Приводит текст к одному виду, чтобы «Ёлка» находилась по слову «елка».
function normalizeText(text) {
  return text.toLowerCase().replaceAll("ё", "е").trim();
}

// Проверяет стоимость. Если цена неизвестна (null), событие подходит только
// под «любую стоимость»: нельзя обещать, что оно бесплатное или платное.
function matchesCost(fee, cost, priceTier) {
  if (cost === "") return true;
  if (fee === null) return false;
  if (cost === "free") return fee === 0;
  if (fee === 0) return false;
  if (priceTier === "") return true;
  if (priceTier === "over25000") return fee > 25000;
  return fee <= Number(priceTier); // «до 5000» включает и более дешёвые события
}

// Проверяет одно событие по всем полям формы.
function matchesFilters(event, filters) {
  if (filters.search !== "") {
    const place = normalizeText(`${event.title} ${event.stage || ""}`);
    if (!place.includes(normalizeText(filters.search))) return false;
  }
  if (filters.grade !== null && (filters.grade < event.grade_from || filters.grade > event.grade_to)) {
    return false;
  }
  // Возраст убирает событие, только если организатор указал ограничение.
  if (filters.age !== null) {
    if (event.age_from !== null && filters.age < event.age_from) return false;
    if (event.age_to !== null && filters.age > event.age_to) return false;
  }
  if (filters.season !== "" && event.season !== filters.season) return false;
  if (filters.subjects.length > 0 && !event.subjects.some((subject) => filters.subjects.includes(subject))) {
    return false;
  }
  if (filters.region !== "" && event.region !== filters.region) return false;
  if (filters.type !== "" && event.type !== filters.type) return false;
  if (filters.format !== "" && event.format !== filters.format) return false;
  return matchesCost(event.fee_kzt, filters.cost, filters.priceTier);
}

// Возвращает события для вкладки: closing, all или saved.
// Учебные материалы отдельно не показываем: они находятся внутри карточки события.
function eventsForTab(events, tab, filters, today, savedIds) {
  const contests = events.filter((event) => event.type !== "material");

  // «Мои» показывает всё сохранённое, включая закрытое: там статус честно виден.
  if (tab === "saved") return contests.filter((event) => savedIds.includes(event.id));

  const found = contests.filter((event) => (
    getStatus(event.registration_start, event.registration_deadline, today) !== "closed"
    && matchesFilters(event, filters)
  ));
  if (tab === "closing") {
    return found.filter((event) => isClosingSoon(event.registration_start, event.registration_deadline, today));
  }
  return found;
}

// Эта часть нужна только для тестов в Node.js. В браузере она не выполняется.
if (typeof module !== "undefined") {
  module.exports = { emptyFilters, matchesFilters, eventsForTab };
}
