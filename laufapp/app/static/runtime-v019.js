(() => {
  'use strict';

  const originalFetch = window.fetch.bind(window);

  function currentMonday() {
    const now = new Date();
    const utc = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
    const offset = (utc.getUTCDay() + 6) % 7;
    utc.setUTCDate(utc.getUTCDate() - offset);
    return `${utc.getUTCFullYear()}-${String(utc.getUTCMonth() + 1).padStart(2, '0')}-${String(utc.getUTCDate()).padStart(2, '0')}`;
  }

  function validationMessage(detail) {
    if (typeof detail === 'string') return detail;
    const items = Array.isArray(detail) ? detail : detail ? [detail] : [];
    const messages = items.map(item => {
      if (typeof item === 'string') return item;
      return item?.msg || item?.message || item?.detail || '';
    }).filter(Boolean);
    return messages.length ? messages.join(' · ') : null;
  }

  window.fetch = async (input, init) => {
    let requestInput = input;
    const rawUrl = typeof input === 'string' ? input : input?.url;
    if (rawUrl) {
      try {
        const url = new URL(rawUrl, document.baseURI);
        if (url.pathname.endsWith('/api/plan/refresh')) {
          const settingsActive = document.querySelector('[data-view="settings"].active');
          const start = url.searchParams.get('start');
          if (settingsActive || !start || start === 'null' || start === 'undefined') {
            url.searchParams.set('start', currentMonday());
            requestInput = typeof input === 'string' ? url.toString() : new Request(url.toString(), input);
          }
        }
      } catch {
        // Never block networking if URL normalization itself fails.
      }
    }

    const response = await originalFetch(requestInput, init);
    if (response.ok || !String(response.headers.get('content-type') || '').includes('application/json')) return response;

    try {
      const data = await response.clone().json();
      const message = validationMessage(data?.detail);
      if (!message || typeof data?.detail === 'string') return response;
      const headers = new Headers(response.headers);
      headers.delete('content-length');
      headers.delete('content-encoding');
      headers.set('content-type', 'application/json');
      return new Response(JSON.stringify({...data, detail: message}), {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    } catch {
      return response;
    }
  };
})();
