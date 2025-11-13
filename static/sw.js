const CACHE_NAME = 'wildlife-incident-v1';
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/wildlife_bg.jpg',
  '/static/sw.js'
];

// Install event - cache essential files
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});