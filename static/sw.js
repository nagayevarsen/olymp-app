// Офлайн-режим. Этот файл (service worker) работает в браузере отдельно от
// страницы, хранит копии файлов и отдаёт их, когда интернета нет.

// После серьёзных изменений в приложении увеличьте номер версии.
const CACHE_NAME = "olymp-v3";
const API_URL = "/api/events";

// Через столько миллисекунд перестаём ждать сервер и показываем сохранённые данные.
const NETWORK_TIMEOUT_MS = 5000;

const APP_FILES = [
  "/",
  "/static/style.css",
  "/static/theme.js",
  "/static/dates.js",
  "/static/filters.js",
  "/static/app.js",
  "/static/i18n/ru.json",
  "/static/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon-maskable-512.png",
  "/static/icons/apple-touch-icon.png",
];

// Установка: сохраняем файлы приложения и, если получится, каталог.
self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(APP_FILES);
    await cache.add(API_URL).catch(() => {});
    await self.skipWaiting();
  })());
});

// Активация: удаляем копии старых версий и начинаем управлять открытыми страницами.
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

// Каталог: сначала пробуем сервер, чтобы данные были свежими.
// Если он молчит или вернул ошибку, показываем сохранённую копию.
async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const network = fetch(request).then((response) => {
    if (response.ok) cache.put(API_URL, response.clone());
    return response;
  });
  const timeout = new Promise((_, reject) => {
    setTimeout(() => reject(new Error("timeout")), NETWORK_TIMEOUT_MS);
  });

  try {
    const response = await Promise.race([network, timeout]);
    if (response.ok) return response;
    return (await cache.match(API_URL)) || response;
  } catch {
    network.catch(() => {}); // запрос мог упасть позже, это уже не важно
    return (await cache.match(API_URL)) || network;
  }
}

// Файлы приложения: сразу отдаём копию, поэтому страница открывается мгновенно,
// даже если бесплатный сервер ещё просыпается. Новая версия скачивается в фоне
// и появится при следующем открытии.
async function cacheFirstThenUpdate(event, cacheKey) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(cacheKey);
  const update = fetch(event.request)
    .then((response) => {
      if (response.ok) cache.put(cacheKey, response.clone());
      return response;
    })
    .catch(() => null);
  event.waitUntil(update);
  return cached || (await update) || Response.error();
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Запросы к чужим сайтам и отправку данных (POST) не трогаем.
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;

  if (url.pathname === API_URL) {
    event.respondWith(networkFirst(event.request));
  } else if (event.request.mode === "navigate") {
    // Адрес с ?saved=... открывает ту же страницу, поэтому копия у них общая.
    event.respondWith(cacheFirstThenUpdate(event, "/"));
  } else {
    event.respondWith(cacheFirstThenUpdate(event, event.request));
  }
});
