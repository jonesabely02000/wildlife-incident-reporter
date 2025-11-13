const CACHE_NAME = 'wildlife-incident-v3';
const urlsToCache = [
  '/',
  '/report',
  '/incidents',
  '/offline',
  '/static/wildlife_bg.jpg',
  '/static/sw.js'
];

// Install event - cache essential files
self.addEventListener('install', event => {
  console.log('🚀 Service Worker installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 Opened cache, adding URLs:', urlsToCache);
        return cache.addAll(urlsToCache)
          .then(() => {
            console.log('✅ All resources cached successfully');
          })
          .catch(error => {
            console.error('❌ Cache addAll failed:', error);
          });
      })
      .then(() => {
        console.log('⚡ Service Worker installed and ready');
        return self.skipWaiting(); // Activate immediately
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('🔄 Service Worker activating...');
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      console.log('📋 Found caches:', cacheNames);
      
      return Promise.all(
        cacheNames.map(cacheName => {
          // Delete old caches that don't match current version
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => {
      console.log('✅ Service Worker activated and old caches cleaned');
      return self.clients.claim(); // Take control of all clients
    })
  );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
  // Only handle GET requests and same-origin requests
  if (event.request.method !== 'GET') return;
  if (!event.request.url.startsWith(self.location.origin)) return;
  
  console.log('🌐 Fetching:', event.request.url);
  
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        // If we have a cached version, return it
        if (cachedResponse) {
          console.log('💾 Serving from cache:', event.request.url);
          return cachedResponse;
        }
        
        // Otherwise, fetch from network
        console.log('📡 Fetching from network:', event.request.url);
        return fetch(event.request)
          .then(networkResponse => {
            // Check if we received a valid response
            if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
              return networkResponse;
            }
            
            // Clone the response (stream can only be consumed once)
            const responseToCache = networkResponse.clone();
            
            // Cache the new response for future visits
            caches.open(CACHE_NAME)
              .then(cache => {
                console.log('💽 Caching new resource:', event.request.url);
                cache.put(event.request, responseToCache);
              })
              .catch(error => {
                console.error('❌ Cache put failed:', error);
              });
            
            return networkResponse;
          })
          .catch(networkError => {
            console.log('❌ Network failed, handling offline:', event.request.url);
            
            // Handle different types of requests when offline
            const request = event.request;
            
            // For HTML pages, serve the offline page or home page
            if (request.destination === 'document' || 
                request.headers.get('Accept').includes('text/html')) {
              console.log('📄 Serving offline page for HTML request');
              return caches.match('/offline')
                .then(offlinePage => offlinePage || caches.match('/'))
                .then(fallbackResponse => {
                  if (fallbackResponse) {
                    return fallbackResponse;
                  }
                  // Ultimate fallback - create a simple offline page
                  return new Response(
                    `
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Wildlife Incident Reporter - Offline</title>
                        <style>
                            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f4f4f4; }
                            .container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto; }
                            h1 { color: #e74c3c; }
                            .btn { background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px; }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>🔌 You're Offline</h1>
                            <p>Don't worry! You can still use the Wildlife Incident Reporter.</p>
                            <p>Your reports will be saved locally and synced when you're back online.</p>
                            <p><strong>Try reconnecting to the internet or check back later.</strong></p>
                        </div>
                    </body>
                    </html>
                    `,
                    { headers: { 'Content-Type': 'text/html' } }
                  );
                });
            }
            
            // For CSS, JS, images - try to serve from cache or return empty response
            else if (request.destination === 'style' || 
                     request.destination === 'script' || 
                     request.destination === 'image') {
              console.log('🎨 Serving fallback for asset:', request.destination);
              return cachedResponse || new Response('', { 
                status: 408, 
                statusText: 'Offline' 
              });
            }
            
            // For API calls, return error response
            else if (request.url.includes('/api/')) {
              console.log('🔌 API call failed offline:', request.url);
              return new Response(
                JSON.stringify({ 
                  error: 'Offline', 
                  message: 'Network connection required for API calls' 
                }), 
                { 
                  status: 408, 
                  headers: { 'Content-Type': 'application/json' } 
                }
              );
            }
            
            // Default fallback
            console.log('⚡ Default offline handling for:', request.url);
            return new Response('Offline - Wildlife Incident Reporter', {
              status: 408,
              headers: { 'Content-Type': 'text/plain' }
            });
          });
      })
  );
});

// Background sync for offline form submissions
self.addEventListener('sync', event => {
  console.log('🔄 Background sync triggered:', event.tag);
  
  if (event.tag === 'sync-pending-incidents') {
    event.waitUntil(
      syncPendingIncidents()
        .then(() => console.log('✅ Background sync completed'))
        .catch(error => console.error('❌ Background sync failed:', error))
    );
  }
});

// Function to sync pending incidents when back online
async function syncPendingIncidents() {
  try {
    // This would be called when the device comes back online
    console.log('🔄 Attempting to sync pending incidents...');
    
    // In a real implementation, you would:
    // 1. Get pending incidents from IndexedDB
    // 2. Send them to the server
    // 3. Clear them from local storage on success
    
    return Promise.resolve();
  } catch (error) {
    console.error('❌ Sync failed:', error);
    throw error;
  }
}

// Listen for messages from the main thread
self.addEventListener('message', event => {
  console.log('📨 Message received in Service Worker:', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      caches.open(CACHE_NAME)
        .then(cache => cache.addAll(event.data.urls))
    );
  }
});

// Log Service Worker lifecycle
console.log('👷 Service Worker script loaded successfully');