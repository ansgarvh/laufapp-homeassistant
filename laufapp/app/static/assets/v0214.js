(() => {
  'use strict';

  const root = document.getElementById('screen');
  if (!root) return;

  function enhanceWeekView() {
    const toolbar = root.querySelector('.week-toolbar');
    const dayStrip = root.querySelector('.day-strip');
    const title = toolbar?.querySelector('.week-title');
    if (title && dayStrip) {
      title.classList.add('week-title-days');
      dayStrip.before(title);
    }

    root.querySelectorAll('.week-workout').forEach(card => {
      const statusText = card.querySelector('.week-info span')?.textContent?.trim() || '';
      card.classList.toggle('status-completed', /(?:^|·\s*)absolviert\s*$/i.test(statusText));
    });
  }

  const observer = new MutationObserver(enhanceWeekView);
  observer.observe(root, { childList: true, subtree: true });
  enhanceWeekView();
})();
