self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload = {};
  try {
    payload = event.data.json();
  } catch (error) {
    payload = { body: event.data.text() };
  }

  const title = payload.title || "CFB Fantasy Alert";
  const body = payload.body || "New league update available.";
  const data = payload.data || payload.payload || {};

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data,
      icon: "/favicon.ico",
      badge: "/favicon.ico",
      tag: data.tag || data.alert_key || undefined,
      renotify: false,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const payload = event.notification.data || {};
  const targetPath = payload.url || payload.path || "/leagues";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.navigate(targetPath);
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetPath);
      }
      return undefined;
    })
  );
});
