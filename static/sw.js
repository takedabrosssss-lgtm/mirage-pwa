const CACHE = 'mirage-shell-v12';
const SHELL = ['/', '/static/styles.css?v=12', '/static/app.js?v=12', '/static/icon.svg', '/manifest.webmanifest'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith('mirage-shell-') && key !== CACHE).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  const isShellAsset = url.pathname === '/' || url.pathname === '/static/app.js' || url.pathname === '/static/styles.css' || url.pathname === '/static/icon.svg' || url.pathname === '/manifest.webmanifest';
  if (!isShellAsset) return;
  event.respondWith((async () => {
    try {
      const response = await fetch(request, {cache: 'no-store'});
      if (response.ok) {
        const cache = await caches.open(CACHE);
        await cache.put(request, response.clone());
      }
      return response;
    } catch (error) {
      const hit = await caches.match(request, {ignoreSearch: true});
      return hit || caches.match('/');
    }
  })());
});
