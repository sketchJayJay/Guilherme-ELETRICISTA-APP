self.addEventListener('push', event => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch(e) { data = {body: event.data ? event.data.text() : ''}; }
  const title = data.title || 'Guilherme Elétrica e Climatização';
  const options = {
    body: data.body || 'Você tem um novo serviço.',
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    data: { url: data.url || '/me' },
    vibrate: [200, 100, 200],
    tag: data.url || 'guilherme-eletrica'
  };
  event.waitUntil(self.registration.showNotification(title, options));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/me';
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list => {
    for (const client of list) { if ('focus' in client) { client.navigate(target); return client.focus(); } }
    if (clients.openWindow) return clients.openWindow(target);
  }));
});
