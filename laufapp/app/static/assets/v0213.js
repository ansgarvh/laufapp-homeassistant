(() => {
  'use strict';

  const screen = document.getElementById('screen');
  if (!screen) return;

  const state = { period: '6m', metric: 'distance_km', data: null, request: 0 };
  const metrics = {
    distance_km: { label: 'Laufkilometer', field: 'distance_km', unit: 'km/Woche', group: 'Training', digits: 1 },
    avg_pace_s_per_km: { label: 'Ø Pace', field: 'avg_pace_s_per_km', unit: '/km', group: 'Training', pace: true, lowerUp: true },
    cadence_spm: { label: 'Kadenz', field: 'cadence_spm', unit: 'spm', group: 'Lauftechnik', digits: 0 },
    duration_hours: { label: 'Laufzeit', field: 'duration_hours', unit: 'h/Woche', group: 'Training', digits: 1 },
    run_count: { label: 'Läufe', field: 'run_count', unit: '/Woche', group: 'Training', digits: 1 },
    avg_run_km: { label: 'Ø Laufdistanz', field: 'avg_run_km', unit: 'km', group: 'Training', digits: 1 },
    longest_run_km: { label: 'Längster Lauf', field: 'longest_run_km', unit: 'km', group: 'Training', digits: 1 },
    avg_hr: { label: 'Ø Herzfrequenz', field: 'avg_hr', unit: 'bpm', group: 'Belastung', digits: 0 },
    avg_rpe: { label: 'Ø RPE', field: 'avg_rpe', unit: '', group: 'Belastung', digits: 1 },
    elevation_m: { label: 'Höhenmeter', field: 'elevation_m', unit: 'm/Woche', group: 'Training', digits: 0 },
    resting_hr: { label: 'Ruhepuls', field: 'resting_hr', unit: 'bpm', group: 'Recovery', digits: 0 },
    hrv_sdnn: { label: 'HRV (SDNN)', field: 'hrv_sdnn', unit: 'ms', group: 'Recovery', digits: 0 },
    sleep_hours: { label: 'Schlaf', field: 'sleep_hours', unit: 'h', group: 'Recovery', digits: 1 },
    body_mass: { label: 'Gewicht', field: 'body_mass', unit: 'kg', group: 'Körper', digits: 1 },
    vo2max: { label: 'VO₂max', field: 'vo2max', unit: 'ml/min/kg', group: 'Leistung', digits: 1 },
  };

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const niceDate = value => {
    const [y, m, d] = String(value || '').slice(0, 10).split('-').map(Number);
    if (!y || !m || !d) return '–';
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', timeZone: 'UTC' });
  };
  const mean = values => values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const finite = value => value !== null && value !== '' && Number.isFinite(Number(value));

  function apiUrl(path) {
    return new URL(path.replace(/^\//, ''), new URL('.', document.baseURI)).toString();
  }

  async function getJson(path) {
    const response = await fetch(apiUrl(path), { headers: { Accept: 'application/json' } });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || `Fehler ${response.status}`);
    return data;
  }

  function paceText(value) {
    if (!finite(value)) return '–';
    const seconds = Math.max(0, Math.round(Number(value)));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}/km`;
  }

  function valueText(value, metric = metrics[state.metric]) {
    if (!finite(value)) return '–';
    if (metric.pace) return paceText(value);
    const n = Number(value);
    return `${n.toLocaleString('de-DE', { minimumFractionDigits: metric.digits || 0, maximumFractionDigits: metric.digits || 0 })}${metric.unit ? ` ${metric.unit}` : ''}`;
  }

  function deltaText(value, metric) {
    if (!finite(value)) return '–';
    const n = Number(value);
    if (metric.pace) {
      const sign = n > 0 ? '+' : n < 0 ? '−' : '±';
      const s = Math.round(Math.abs(n));
      return `${sign}${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}/km`;
    }
    const sign = n > 0 ? '+' : n < 0 ? '−' : '±';
    return `${sign}${Math.abs(n).toLocaleString('de-DE', { maximumFractionDigits: metric.digits ?? 1 })}${metric.unit ? ` ${metric.unit.replace('/Woche', '')}` : ''}`;
  }

  function metricOptions() {
    const groups = [...new Set(Object.values(metrics).map(x => x.group))];
    return groups.map(group => `<optgroup label="${esc(group)}">${Object.entries(metrics).filter(([, m]) => m.group === group).map(([key, m]) => `<option value="${key}" ${state.metric === key ? 'selected' : ''}>${esc(m.label)}</option>`).join('')}</optgroup>`).join('');
  }

  function chartSvg(weeks, metric) {
    const values = weeks.map((point, index) => ({ index, value: finite(point[metric.field]) ? Number(point[metric.field]) : null }));
    const valid = values.filter(x => x.value !== null);
    if (!valid.length) return '<div class="trend-empty">Für diese Kennzahl liegen im gewählten Zeitraum noch keine Daten vor.</div>';

    const width = 720, height = 238, left = 62, right = 18, top = 18, bottom = 38;
    const plotW = width - left - right, plotH = height - top - bottom;
    let min = Math.min(...valid.map(x => x.value));
    let max = Math.max(...valid.map(x => x.value));
    if (min === max) {
      const pad = Math.max(Math.abs(min) * 0.05, 1);
      min -= pad; max += pad;
    } else {
      const pad = (max - min) * 0.08;
      min -= pad; max += pad;
    }
    const x = index => left + (weeks.length <= 1 ? plotW / 2 : index / (weeks.length - 1) * plotW);
    const y = value => {
      const ratio = (value - min) / (max - min);
      return metric.lowerUp ? top + ratio * plotH : top + (1 - ratio) * plotH;
    };

    const lines = [];
    let segment = [];
    values.forEach(point => {
      if (point.value === null) {
        if (segment.length) lines.push(segment);
        segment = [];
      } else {
        segment.push(`${x(point.index).toFixed(1)},${y(point.value).toFixed(1)}`);
      }
    });
    if (segment.length) lines.push(segment);

    const topValue = metric.lowerUp ? min : max;
    const bottomValue = metric.lowerUp ? max : min;
    const grid = [0, .25, .5, .75, 1].map(frac => {
      const gy = top + frac * plotH;
      const gv = topValue + (bottomValue - topValue) * frac;
      return `<line class="trend-gridline" x1="${left}" y1="${gy}" x2="${width - right}" y2="${gy}"></line><text class="trend-y-label" x="${left - 8}" y="${gy + 4}" text-anchor="end">${esc(valueText(gv, metric).replace(` ${metric.unit}`, ''))}</text>`;
    }).join('');
    const path = lines.map(points => points.length === 1
      ? `<circle class="trend-point" cx="${points[0].split(',')[0]}" cy="${points[0].split(',')[1]}" r="4"></circle>`
      : `<polyline class="trend-line" points="${points.join(' ')}"></polyline>`).join('');
    const last = valid[valid.length - 1];
    const xLabels = [...new Set([0, Math.floor((weeks.length - 1) / 2), weeks.length - 1])]
      .map(index => `<text class="trend-x-label" x="${x(index)}" y="${height - 10}" text-anchor="${index === 0 ? 'start' : index === weeks.length - 1 ? 'end' : 'middle'}">${esc(niceDate(weeks[index]?.week_start))}</text>`).join('');

    return `<svg class="trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Zeitverlauf ${esc(metric.label)}">${grid}${path}<circle class="trend-point latest" cx="${x(last.index)}" cy="${y(last.value)}" r="5"></circle>${xLabels}</svg>`;
  }

  function coverageNote(data, metricKey) {
    const c = data.coverage || {};
    if (metricKey === 'cadence_spm') return `Kadenz verfügbar bei ${c.cadence_runs || 0} von ${c.runs || 0} Läufen.`;
    if (metricKey === 'avg_hr') return `Herzfrequenz verfügbar bei ${c.heart_rate_runs || 0} von ${c.runs || 0} Läufen.`;
    if (metricKey === 'avg_rpe') return `RPE erfasst bei ${c.rpe_runs || 0} von ${c.runs || 0} Läufen.`;
    if (metricKey === 'elevation_m') return `Höhenmeter vorhanden bei ${c.elevation_runs || 0} von ${c.runs || 0} Läufen.`;
    const key = `${metricKey}_samples`;
    if (key in c) return `${c[key] || 0} Messwerte im Zeitraum.`;
    return `${c.runs || 0} Läufe im Zeitraum.`;
  }

  function renderData() {
    const section = document.getElementById('training-trends-v0213');
    if (!section || !state.data) return;
    const metric = metrics[state.metric];
    const weeks = state.data.weeks || [];
    const field = metric.field;
    const latestPoint = [...weeks].reverse().find(x => finite(x[field]));
    const last4 = weeks.slice(-4).map(x => x[field]).filter(finite).map(Number);
    const previous4 = weeks.slice(-8, -4).map(x => x[field]).filter(finite).map(Number);
    const current4 = mean(last4);
    const prior4 = mean(previous4);
    const delta = current4 !== null && prior4 !== null ? current4 - prior4 : null;

    section.innerHTML = `<div class="section-head trend-head"><div><h2>Trainingsentwicklung</h2><span class="small muted">Zeitachse aus deinen gespeicherten Lauf- und Health-Daten</span></div></div>
      <article class="card trend-card">
        <div class="trend-toolbar">
          <label class="field trend-field"><span>Kennzahl</span><select class="select" id="trend-metric">${metricOptions()}</select></label>
          <div class="period-selector trend-period" role="group" aria-label="Zeitraum Trainingsentwicklung">${[['3m','3 M'],['6m','6 M'],['12m','12 M'],['24m','24 M']].map(([value,label]) => `<button type="button" data-trend-period="${value}" aria-pressed="${state.period === value}">${label}</button>`).join('')}</div>
        </div>
        <div class="trend-stats">
          <div><span>Letzte Woche</span><strong>${valueText(latestPoint?.[field], metric)}</strong></div>
          <div><span>Ø letzte 4 Wochen</span><strong>${valueText(current4, metric)}</strong></div>
          <div><span>Δ vs. vorige 4 Wochen</span><strong>${deltaText(delta, metric)}</strong></div>
        </div>
        <div class="trend-chart">${chartSvg(weeks, metric)}</div>
        <p class="form-note trend-note">${esc(coverageNote(state.data, state.metric))} Pace und Herzfrequenz werden distanz- bzw. zeitgewichtet zusammengefasst; fehlende Wochenwerte werden nicht erfunden.</p>
      </article>`;

    section.querySelector('#trend-metric')?.addEventListener('change', event => {
      if (metrics[event.target.value]) {
        state.metric = event.target.value;
        renderData();
      }
    });
    section.querySelectorAll('[data-trend-period]').forEach(button => button.addEventListener('click', () => {
      if (button.dataset.trendPeriod !== state.period) {
        state.period = button.dataset.trendPeriod;
        loadData();
      }
    }));
  }

  async function loadData() {
    const section = document.getElementById('training-trends-v0213');
    if (!section) return;
    const request = ++state.request;
    section.innerHTML = '<div class="card trend-loading">Berechne Trainingsentwicklung …</div>';
    try {
      const data = await getJson(`api/progress/trends?period=${encodeURIComponent(state.period)}`);
      if (request !== state.request || !document.getElementById('training-trends-v0213')) return;
      state.data = data;
      renderData();
    } catch (error) {
      if (request !== state.request) return;
      section.innerHTML = `<div class="card empty"><h3>Trainingsentwicklung nicht verfügbar</h3><p>${esc(error.message || error)}</p></div>`;
    }
  }

  function cleanupLegacyTransferUi() {
    const button = document.getElementById('prepare-transfer');
    const row = button?.closest('.setting-row');
    if (row) row.remove();
  }

  function syncUi() {
    cleanupLegacyTransferUi();
    const title = screen.querySelector('.page-head h1');
    if (!title || title.textContent.trim() !== 'Fortschritt') return;
    if (document.getElementById('training-trends-v0213')) return;
    const section = document.createElement('section');
    section.className = 'section training-trends-v0213';
    section.id = 'training-trends-v0213';
    screen.appendChild(section);
    loadData();
  }

  const observer = new MutationObserver(syncUi);
  observer.observe(screen, { childList: true, subtree: true });
  syncUi();
})();
