(() => {
  'use strict';

  const OVERLAY_ID = 'v0225-run-detail-overlay';
  let lastTrigger = null;
  let previousBodyOverflow = '';

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
  const number = value => value === null || value === undefined || value === '' ? null : Number(value);
  const fmt0 = value => Number(value).toLocaleString('de-DE', { maximumFractionDigits: 0 });
  const fmt1 = value => Number(value).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fmt2 = value => Number(value).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const baseUrl = () => new URL('.', document.baseURI);
  const apiPath = path => new URL(String(path).replace(/^\/+/, ''), baseUrl()).toString();

  async function api(path) {
    const response = await fetch(apiPath(path), { headers: { Accept: 'application/json' } });
    let data = null;
    try { data = await response.json(); } catch { data = null; }
    if (!response.ok) throw new Error(data?.detail || `Fehler ${response.status}`);
    return data;
  }

  function secondsText(value) {
    let seconds = Math.max(0, Math.round(Number(value) || 0));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    seconds %= 60;
    return hours
      ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
      : `${minutes}:${String(seconds).padStart(2, '0')}`;
  }

  function paceText(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || seconds <= 0) return '–';
    const rounded = Math.round(seconds);
    return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')} /km`;
  }

  function startedText(value) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value || '–');
    return parsed.toLocaleString('de-DE', {
      weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

  function sourceText(source) {
    const value = String(source || '');
    if (value.includes('hae') || value.includes('health_auto_export')) return 'Health Auto Export';
    if (value.startsWith('apple_health')) return 'Apple Health';
    if (value === 'manual') return 'Manuell';
    if (value === 'screenshot') return 'Fitness-Screenshot';
    return value ? value.replaceAll('_', ' ') : 'Laufapp';
  }

  const TYPE = { easy: 'Easy', quality: 'Qualität', long: 'Longrun', raceprep: 'Race Prep', race: 'Rennen' };

  function stat(label, value, hint = '', tone = '') {
    return `<div class="v0225-stat ${tone ? `tone-${esc(tone)}` : ''}">
      <span>${esc(label)}</span><strong>${value}</strong>${hint ? `<small>${esc(hint)}</small>` : ''}
    </div>`;
  }

  function chartSvg(metric, inverse = false) {
    const points = Array.isArray(metric?.points) ? metric.points.filter(p => Number.isFinite(Number(p.value))) : [];
    if (!points.length) return '<div class="v0225-chart-empty">Keine Zeitreihe in dieser Datenquelle</div>';
    const values = points.map(p => Number(p.value));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(1e-9, max - min);
    const coords = points.map((point, index) => {
      const x = points.length === 1 ? 50 : index / (points.length - 1) * 100;
      const normalized = inverse ? (max - Number(point.value)) / span : (Number(point.value) - min) / span;
      const y = max === min ? 25 : 43 - normalized * 34;
      return [x, y];
    });
    if (coords.length === 1) {
      return `<svg class="v0225-spark" viewBox="0 0 100 50" preserveAspectRatio="none" aria-hidden="true"><circle cx="50" cy="25" r="2.8"></circle></svg>`;
    }
    return `<svg class="v0225-spark" viewBox="0 0 100 50" preserveAspectRatio="none" aria-hidden="true"><polyline points="${coords.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ')}"></polyline></svg>`;
  }

  function rangeText(metric, formatter) {
    if (!metric || metric.minimum === null || metric.minimum === undefined || metric.maximum === null || metric.maximum === undefined) return '–';
    return `${formatter(metric.minimum)} – ${formatter(metric.maximum)}`;
  }

  function chartRow({ label, main, metric, formatter, tone, inverse = false, subtitle = '' }) {
    const range = metric ? rangeText(metric, formatter) : '–';
    return `<article class="v0225-chart-row tone-${esc(tone)}">
      <div class="v0225-chart-copy"><span>${esc(label)}</span><strong>${main}</strong>${subtitle ? `<small>${esc(subtitle)}</small>` : ''}</div>
      <div class="v0225-chart-visual">${chartSvg(metric, inverse)}</div>
      <div class="v0225-chart-range">${esc(range)}</div>
    </article>`;
  }

  function routeSvg(route) {
    const points = Array.isArray(route?.points) ? route.points.filter(p => Number.isFinite(Number(p.lat)) && Number.isFinite(Number(p.lon))) : [];
    if (points.length < 2) {
      return '<div class="v0225-route-empty"><strong>Keine GPS-Route verfügbar</strong><span>Der Lauf bleibt trotzdem mit allen vorhandenen Messwerten auswertbar.</span></div>';
    }
    const meanLat = points.reduce((sum, p) => sum + Number(p.lat), 0) / points.length;
    const lonScale = Math.max(0.2, Math.cos(meanLat * Math.PI / 180));
    const projected = points.map(p => ({ x: Number(p.lon) * lonScale, y: Number(p.lat) }));
    const xs = projected.map(p => p.x), ys = projected.map(p => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const spanX = Math.max(1e-8, maxX - minX), spanY = Math.max(1e-8, maxY - minY);
    const pad = 7;
    const coords = projected.map(p => ({
      x: pad + (p.x - minX) / spanX * (100 - pad * 2),
      y: 100 - pad - (p.y - minY) / spanY * (100 - pad * 2)
    }));
    const start = coords[0], end = coords[coords.length - 1];
    return `<svg class="v0225-route-svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" role="img" aria-label="GPS-Strecke des Laufs">
      <g class="v0225-route-grid"><path d="M0 25H100M0 50H100M0 75H100M25 0V100M50 0V100M75 0V100"></path></g>
      <polyline class="v0225-route-line" points="${coords.map(p => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ')}"></polyline>
      <circle class="v0225-route-start" cx="${start.x.toFixed(2)}" cy="${start.y.toFixed(2)}" r="2.8"></circle>
      <circle class="v0225-route-end" cx="${end.x.toFixed(2)}" cy="${end.y.toFixed(2)}" r="2.8"></circle>
    </svg>`;
  }

  function detailHtml(data) {
    const run = data.run || {};
    const workout = data.workout || null;
    const summary = data.summary || {};
    const series = data.series || {};
    const route = data.route || {};
    const title = workout?.title || `${fmt1(summary.distance_km || run.distance_km || 0)} km Lauf`;
    const type = workout?.workout_type ? (TYPE[workout.workout_type] || workout.workout_type) : 'Lauf';
    const shoe = [run.shoe_brand, run.shoe_model, run.shoe_nickname].filter(Boolean).join(' · ');
    const routeMeta = route.available ? `${fmt0(route.original_points || route.points?.length || 0)} GPS-Punkte` : 'ohne GPS-Route';
    const rpe = number(summary.effort_rpe);

    const stats = [
      stat('Strecke', summary.distance_km != null ? `${fmt2(summary.distance_km)} km` : '–', '', 'distance'),
      stat('Trainingszeit', summary.training_time_s != null ? secondsText(summary.training_time_s) : '–', '', 'time'),
      stat('Verstrichene Zeit', summary.elapsed_time_s != null ? secondsText(summary.elapsed_time_s) : '–', '', 'time'),
      stat('Ø Pace', summary.pace_s_per_km != null ? paceText(summary.pace_s_per_km) : '–', '', 'pace'),
      stat('Höhenmeter', summary.elevation_gain_m != null ? `${fmt0(summary.elevation_gain_m)} m` : '–', '', 'elevation'),
      stat('Ø Herzfrequenz', summary.average_heart_rate_bpm != null ? `${fmt0(summary.average_heart_rate_bpm)} bpm` : '–', '', 'heart'),
      stat('Ø Leistung', summary.average_power_w != null ? `${fmt0(summary.average_power_w)} W` : '–', '', 'power'),
      stat('Ø Kadenz', summary.average_cadence_spm != null ? `${fmt0(summary.average_cadence_spm)} spm` : '–', '', 'cadence'),
      stat('Aktivitätskalorien', summary.active_calories_kcal != null ? `${fmt0(summary.active_calories_kcal)} kcal` : '–', '', 'calories'),
      stat('Gesamtkalorien', summary.total_calories_kcal != null ? `${fmt0(summary.total_calories_kcal)} kcal` : '–', 'nicht getrennt gespeichert', 'calories'),
      stat('Anstrengung', rpe != null ? `${fmt0(rpe)} · ${esc(summary.effort_label || '')}` : '–', rpe == null ? 'RPE kann ergänzt werden' : '', 'effort'),
      stat('Schrittlänge', summary.stride_length_m != null ? `${fmt2(summary.stride_length_m)} m` : '–', '', 'dynamics'),
      stat('Vertikale Oszillation', summary.vertical_oscillation_cm != null ? `${fmt1(summary.vertical_oscillation_cm)} cm` : '–', '', 'dynamics'),
      stat('Bodenkontaktzeit', summary.ground_contact_time_ms != null ? `${fmt0(summary.ground_contact_time_ms)} ms` : '–', '', 'dynamics')
    ].join('');

    const charts = [
      chartRow({ label: 'Höhe', main: summary.elevation_gain_m != null ? `Höhenmeter: ${fmt0(summary.elevation_gain_m)} m` : 'Höhenprofil', metric: series.elevation, formatter: v => `${fmt0(v)} m`, tone: 'elevation' }),
      chartRow({ label: 'Herzfrequenz', main: summary.average_heart_rate_bpm != null ? `Ø ${fmt0(summary.average_heart_rate_bpm)} bpm` : '–', metric: series.heart_rate, formatter: v => `${fmt0(v)} bpm`, tone: 'heart' }),
      chartRow({ label: 'Pace', main: summary.pace_s_per_km != null ? `Ø ${paceText(summary.pace_s_per_km)}` : '–', metric: series.pace, formatter: paceText, tone: 'pace', inverse: true }),
      chartRow({ label: 'Leistung', main: summary.average_power_w != null ? `Ø ${fmt0(summary.average_power_w)} W` : '–', metric: series.running_power, formatter: v => `${fmt0(v)} W`, tone: 'power' }),
      chartRow({ label: 'Kadenz', main: summary.average_cadence_spm != null ? `Ø ${fmt0(summary.average_cadence_spm)} spm` : '–', metric: series.cadence, formatter: v => `${fmt0(v)} spm`, tone: 'cadence' }),
      chartRow({ label: 'Vertikale Oszillation', main: summary.vertical_oscillation_cm != null ? `Ø ${fmt1(summary.vertical_oscillation_cm)} cm` : '–', metric: series.vertical_oscillation, formatter: v => `${fmt1(v)} cm`, tone: 'dynamics' }),
      chartRow({ label: 'Bodenkontaktzeit', main: summary.ground_contact_time_ms != null ? `Ø ${fmt0(summary.ground_contact_time_ms)} ms` : '–', metric: series.ground_contact_time, formatter: v => `${fmt0(v)} ms`, tone: 'contact' }),
      chartRow({ label: 'Schrittlänge', main: summary.stride_length_m != null ? `Ø ${fmt2(summary.stride_length_m)} m` : '–', metric: series.stride_length, formatter: v => `${fmt2(v)} m`, tone: 'dynamics' })
    ].join('');

    return `<div class="v0225-run-detail-shell">
      <header class="v0225-run-detail-head">
        <button class="v0225-back" type="button" data-v0225-close aria-label="Zurück">‹</button>
        <strong>Laufdetails</strong>
        <button class="v0225-edit-top" type="button" data-v0225-edit="${Number(run.id)}">•••</button>
      </header>
      <main class="v0225-run-detail-main">
        <section class="v0225-run-hero">
          <div class="v0225-run-title-row"><div><span class="eyebrow">Absolvierter Lauf</span><h1>${esc(title)}</h1></div><span class="pill ${esc(workout?.workout_type || 'completed')}">${esc(type)}</span></div>
          <div class="v0225-run-meta"><span>${esc(startedText(run.started_at))}</span><span>${esc(sourceText(run.source))}</span><span>${esc(routeMeta)}</span></div>
        </section>

        <section class="v0225-route-card">
          <div class="v0225-route-caption"><div><span class="eyebrow">GPS-Strecke</span><strong>${route.available ? 'Deine Route' : 'Keine Route gespeichert'}</strong></div><span>${route.available ? `${fmt0(route.points?.length || 0)} dargestellt` : ''}</span></div>
          <div class="v0225-route-canvas">${routeSvg(route)}</div>
          <p>${esc(data.notes?.map || route.privacy_note || '')}</p>
        </section>

        <section class="v0225-section"><div class="v0225-section-title"><h2>Trainingsdetails</h2><span>alle verfügbaren Werte</span></div><div class="v0225-stat-grid">${stats}</div></section>

        <section class="v0225-section"><div class="v0225-section-title"><h2>Verlauf</h2><span>zeitaufgelöste Messwerte</span></div><div class="v0225-chart-list">${charts}</div></section>

        <section class="v0225-section"><div class="v0225-section-title"><h2>Weitere Infos</h2></div><article class="v0225-info-card">
          <div><span>Datenquelle</span><strong>${esc(sourceText(run.source))}</strong></div>
          <div><span>Schuh</span><strong>${esc(shoe || 'nicht zugeordnet')}</strong></div>
          <div><span>Planbezug</span><strong>${esc(workout ? `${workout.title} · ${type}` : 'kein Training verknüpft')}</strong></div>
          ${run.notes ? `<div class="wide"><span>Notiz</span><strong>${esc(run.notes)}</strong></div>` : ''}
          <div class="wide note"><span>Gesamtkalorien</span><strong>${esc(data.notes?.total_calories || '')}</strong></div>
        </article></section>

        <button class="button primary v0225-legacy-edit" type="button" data-v0225-edit="${Number(run.id)}">Eigene Angaben & KI-Feedback</button>
      </main>
    </div>`;
  }

  function ensureOverlay() {
    let overlay = document.getElementById(OVERLAY_ID);
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.className = 'v0225-run-detail-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Laufdetails');
    document.body.appendChild(overlay);
    overlay.addEventListener('click', event => {
      if (event.target.closest('[data-v0225-close]')) closeDetail();
      const edit = event.target.closest('[data-v0225-edit]');
      if (edit) openLegacyEditor(Number(edit.dataset.v0225Edit));
    });
    return overlay;
  }

  async function openDetail(runId, trigger = null) {
    if (!Number.isInteger(Number(runId)) || Number(runId) <= 0) return;
    lastTrigger = trigger;
    const overlay = ensureOverlay();
    previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    overlay.classList.add('open');
    overlay.innerHTML = '<div class="v0225-detail-loading"><div class="loader"></div><strong>Laufdetails werden geladen …</strong></div>';
    try {
      const data = await api(`api/v2/runs/${Number(runId)}/detail-view`);
      overlay.innerHTML = detailHtml(data);
      overlay.querySelector('[data-v0225-close]')?.focus({ preventScroll: true });
    } catch (error) {
      overlay.innerHTML = `<div class="v0225-detail-error"><strong>Die Laufdetails konnten nicht geladen werden.</strong><p>${esc(error.message || error)}</p><button class="button" type="button" data-v0225-close>Zurück</button></div>`;
    }
  }

  function closeDetail(restoreFocus = true) {
    const overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) return;
    overlay.classList.remove('open');
    overlay.innerHTML = '';
    document.body.style.overflow = previousBodyOverflow;
    if (restoreFocus && lastTrigger?.isConnected) lastTrigger.focus({ preventScroll: true });
  }

  function bypassClick(row) {
    if (!row) return false;
    row.dataset.v0225Bypass = '1';
    row.click();
    setTimeout(() => delete row.dataset.v0225Bypass, 0);
    return true;
  }

  async function waitForRunRow(runId) {
    for (let attempt = 0; attempt < 30; attempt++) {
      const row = document.querySelector(`.run-row[data-run-edit="${Number(runId)}"]`);
      if (row) return row;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    return null;
  }

  async function openLegacyEditor(runId) {
    const direct = lastTrigger?.matches?.(`.run-row[data-run-edit="${Number(runId)}"]`) ? lastTrigger : null;
    closeDetail(false);
    if (direct?.isConnected && bypassClick(direct)) return;
    const progress = document.querySelector('#bottom-nav [data-view="progress"]');
    if (!progress) return;
    progress.click();
    const row = await waitForRunRow(runId);
    if (row) bypassClick(row);
  }

  document.addEventListener('click', async event => {
    const runRow = event.target.closest?.('.run-row[data-run-edit]');
    if (runRow) {
      if (runRow.dataset.v0225Bypass === '1') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      openDetail(Number(runRow.dataset.runEdit), runRow);
      return;
    }

    const completed = event.target.closest?.('.week-workout.status-completed');
    if (!completed || event.target.closest('[data-workout-menu],.drag-handle')) return;
    const workoutId = Number(completed.dataset.workout);
    if (!Number.isInteger(workoutId) || workoutId <= 0) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    try {
      const info = await api(`api/v2/workouts/${workoutId}/run-info`);
      const run = info.run || info.single_same_day_candidate;
      if (run?.id) openDetail(Number(run.id), completed);
    } catch {
      // The existing workout menu remains available; a failed optional detail
      // lookup must never break normal week interactions.
    }
  }, true);

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.getElementById(OVERLAY_ID)?.classList.contains('open')) closeDetail();
  });
})();
