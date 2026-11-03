// Выбор темы. Этот файл подключён в начале страницы, чтобы она сразу
// открывалась в нужной теме и не мигала белым.

const THEME_KEY = "olymp.theme";

// Если пользователь ещё не выбирал тему, браузер берёт её из настроек устройства.
function applyStoredTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") document.documentElement.dataset.theme = stored;
  } catch {
    // Память недоступна: остаётся тема устройства.
  }
}

// Какая тема видна сейчас.
function currentTheme() {
  const chosen = document.documentElement.dataset.theme;
  if (chosen) return chosen;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// Переключает тему и запоминает выбор на этом устройстве.
function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    // Память недоступна: тема сохранится только до закрытия страницы.
  }
}

applyStoredTheme();
