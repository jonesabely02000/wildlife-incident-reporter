const CACHE_NAME = 'wildlife-incident-v4';
const urlsToCache = [
  '/',
  '/report',
  '/incidents',
  '/offline',
  '/export',
  '/static/wildlife_bg.jpg',
  '/static/sw.js'
];

// Install event - cache essential files
self.addEventListener('install', event => {
  console.log('🚀 Service Worker installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 Opened cache');
        // Don't wait for all URLs - cache critical ones first
        return cache.addAll(['/', '/offline'])
          .then(() => {
            console.log('✅ Critical pages cached');
            // Cache other URLs in background
            return cache.addAll(urlsToCache.filter(url => url !== '/' && url !== '/offline'));
          });
      })
      .then(() => {
        console.log('⚡ Service Worker installed');
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('❌ Cache installation failed:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('🔄 Service Worker activating...');
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => {
      console.log('✅ Service Worker activated');
      return self.clients.claim();
    })
  );
});

// Fetch event - smart caching strategy
self.addEventListener('fetch', event => {
  // Skip non-GET requests and cross-origin requests
  if (event.request.method !== 'GET') return;
  if (!event.request.url.startsWith(self.location.origin)) return;
  
  const requestUrl = new URL(event.request.url);
  
  // Handle navigation requests (HTML pages)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      handleNavigationRequest(event.request)
    );
    return;
  }
  
  // Handle API requests
  if (requestUrl.pathname.startsWith('/api/')) {
    event.respondWith(
      handleApiRequest(event.request)
    );
    return;
  }
  
  // Handle static assets
  event.respondWith(
    handleStaticRequest(event.request)
  );
});

// Handle HTML page navigation
async function handleNavigationRequest(request) {
  try {
    // Try network first for fresh content
    const networkResponse = await fetch(request);
    
    // Cache the successful response
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, networkResponse.clone());
    
    return networkResponse;
  } catch (error) {
    console.log('📄 Network failed for navigation, trying cache:', request.url);
    
    // Network failed - try cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // No cache found - serve offline page
    console.log('📄 No cache found, serving offline page');
    return caches.match('/offline');
  }
}

// Handle API requests
async function handleApiRequest(request) {
  try {
    // Try network first for API calls
    const networkResponse = await fetch(request);
    return networkResponse;
  } catch (error) {
    console.log('🔌 API call failed offline:', request.url);
    
    // For GET API calls, try cache
    if (request.method === 'GET') {
      const cachedResponse = await caches.match(request);
      if (cachedResponse) {
        return cachedResponse;
      }
    }
    
    // Return offline error for API calls
    return new Response(
      JSON.stringify({ 
        error: 'offline',
        message: 'You are offline. Please check your connection.',
        canWorkOffline: true
      }), 
      { 
        status: 408,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// Handle static assets (CSS, JS, images)
async function handleStaticRequest(request) {
  // Try cache first for static assets
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    // Not in cache - try network
    const networkResponse = await fetch(request);
    
    // Cache the successful response for next time
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, networkResponse.clone());
    
    return networkResponse;
  } catch (error) {
    console.log('📦 Static asset not available:', request.url);
    
    // Return empty responses for missing assets to prevent errors
    if (request.url.includes('.css')) {
      return new Response('', { headers: { 'Content-Type': 'text/css' } });
    }
    if (request.url.includes('.js')) {
      return new Response('// Offline', { headers: { 'Content-Type': 'application/javascript' } });
    }
    
    return new Response('', { status: 404 });
  }
}

// Listen for messages from the main thread
self.addEventListener('message', event => {
  console.log('📨 Message from client:', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      caches.open(CACHE_NAME)
        .then(cache => cache.addAll(event.data.urls))
        .then(() => {
          // Notify client that caching is complete
          self.clients.matchAll().then(clients => {
            clients.forEach(client => {
              client.postMessage({ type: 'CACHE_COMPLETE', urls: event.data.urls });
            });
          });
        })
    );
  }
});

console.log('👷 Service Worker loaded successfully');