const CACHE_NAME = 'medai-v1';
const ASSETS = [
  '/user-portal.html',
  '/login.html',
  '/css/style.css',
  '/js/app.js',
  '/js/html5-qrcode.min.js',
  '/vendor/css/all.min.css',
  '/icon-192.svg',
  '/icon-512.svg'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS).catch(err => console.log("Cache compilation skipped offline: ", err));
    })
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      return cachedResponse || fetch(e.request);
    })
  );
});
