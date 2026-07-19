// Shared chrome + tiny chart helpers for the showcase pages.
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (n, dp = 0) => n == null ? '—' : n.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
const card = (v, l, d) => `<div class="card"><div class="v">${v}</div><div class="l">${l}</div>${d ? `<div class="d">${d}</div>` : ''}</div>`;

// ---- nav ----
// The quick-links toolbar now lives in assets/nav.js (shared by every page,
// including the dark generated dashboards). This file keeps the tooltip host.
(function tipHost(){
  if (document.getElementById('tip')) return;
  const tip = document.createElement('div');
  tip.id = 'tip';
  document.body.append(tip);
})();

// ---- tooltip ----
const tipEl = () => document.getElementById('tip');
function bindTips(root) {
  root.querySelectorAll('[data-tip]').forEach(p => {
    p.addEventListener('mousemove', e => {
      const t = tipEl();
      t.innerHTML = e.target.dataset.tip;
      t.style.opacity = 1;
      t.style.left = Math.min(e.clientX + 12, innerWidth - 180) + 'px';
      t.style.top = (e.clientY - 34) + 'px';
    });
    p.addEventListener('mouseleave', () => { tipEl().style.opacity = 0; });
  });
}

// ---- single-series bar chart ----
function barChart(el, rows, opts = {}) {
  const W = 470, H = 190, padL = 44, padB = 30, padT = 10, padR = 6;
  const max = Math.max(...rows.map(r => r.v)) * 1.08;
  const iw = (W - padL - padR) / rows.length;
  const bw = Math.max(3, iw - 2);
  let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:560px">`;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (H - padT - padB) * i / 4;
    s += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="${css('--grid')}" stroke-width="1"/>` +
         `<text x="${padL - 6}" y="${y + 3}" text-anchor="end" font-size="9" fill="${css('--muted')}">${fmt(max * (1 - i / 4))}</text>`;
  }
  rows.forEach((r, i) => {
    const h = (r.v / max) * (H - padT - padB);
    const x = padL + i * iw + 1, y = H - padB - h;
    s += `<path d="M${x},${H - padB} L${x},${y + 4} Q${x},${y} ${x + 4},${y} L${x + bw - 4},${y} Q${x + bw},${y} ${x + bw},${y + 4} L${x + bw},${H - padB} Z"
      fill="${css('--s1')}" data-tip="${r.label}: ${opts.pre || ''}${fmt(r.v, opts.dp || 0)}${opts.suf || ''}"/>`;
    if (i % Math.ceil(rows.length / 8) === 0)
      s += `<text x="${x + bw / 2}" y="${H - padB + 13}" text-anchor="middle" font-size="8.5" fill="${css('--muted')}">${r.short}</text>`;
  });
  s += `<line x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}" stroke="${css('--axis')}" stroke-width="1"/></svg>`;
  el.innerHTML = s;
  bindTips(el);
}

// ---- CNHR line chart with state-coloured markers ----
function stateChart(el, rows, legendEl) {
  const W = 940, H = 230, padL = 46, padB = 30, padT = 12, padR = 14;
  const vals = rows.map(r => r.cnhr);
  const min = Math.min(0, ...vals) - 4, max = Math.max(15, ...vals) + 4;
  const X = i => padL + (W - padL - padR) * i / (rows.length - 1);
  const Y = v => padT + (H - padT - padB) * (1 - (v - min) / (max - min));
  const sc = { SUSTAINED: css('--good'), ACCEL_REC: css('--s1'), DECEL: css('--serious'), STALLED: css('--critical') };
  let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%">`;
  [0, 15].forEach(gl => {
    s += `<line x1="${padL}" y1="${Y(gl)}" x2="${W - padR}" y2="${Y(gl)}" stroke="${gl === 15 ? css('--axis') : css('--grid')}" stroke-width="1" ${gl === 15 ? 'stroke-dasharray="4 4"' : ''}/>` +
         `<text x="${padL - 6}" y="${Y(gl) + 3}" text-anchor="end" font-size="9" fill="${css('--muted')}">£${gl}</text>`;
  });
  s += `<text x="${W - padR}" y="${Y(15) - 5}" text-anchor="end" font-size="9" fill="${css('--muted')}">target £15/h</text>`;
  s += `<polyline points="${rows.map((r, i) => X(i) + ',' + Y(r.cnhr)).join(' ')}" fill="none" stroke="${css('--s1')}" stroke-width="2"/>`;
  rows.forEach((r, i) => {
    s += `<circle cx="${X(i)}" cy="${Y(r.cnhr)}" r="4.5" fill="${sc[r.state] || css('--muted')}" stroke="${css('--surface')}" stroke-width="2"
      data-tip="${r.label} — £${r.cnhr}/h · ${r.state} · ${r.trips} trips"/>`;
    if (i % 2 === 0) s += `<text x="${X(i)}" y="${H - padB + 14}" text-anchor="middle" font-size="8.5" fill="${css('--muted')}">${r.week.slice(5)}</text>`;
  });
  el.innerHTML = s + '</svg>';
  bindTips(el);
  if (legendEl) legendEl.innerHTML =
    Object.entries({ SUSTAINED: '--good', 'ACCEL RECOVERY': '--s1', DECELERATING: '--serious', STALLED: '--critical' })
      .map(([k, v]) => `<span><span class="sw" style="background:var(${v})"></span>${k}</span>`).join('');
}

const getJSON = p => fetch(p).then(r => {
  if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
  return r.json();
});

/* Every page builds its content inside a getJSON .then, so an unhandled
   rejection leaves empty cards and a blank map box with nothing to explain it.
   Pages pass the selector of their main container. */
function dataFail(file) {
  return err => {
    const host = document.querySelector('header.page') || document.querySelector('main, .wrap');
    if (host) host.insertAdjacentHTML('afterend',
      '<div class="explain" role="alert" style="border-left-color:var(--critical)">'
      + '<b>Could not load ' + (file || 'the data for this page') + '.</b> '
      + 'The request failed (' + err.message + '), so the figures, tables and maps below are empty. '
      + 'If you opened this file directly from disk, your browser blocks the data files — '
      + 'serve the <code>docs/</code> folder over HTTP instead. Otherwise reload the page.</div>');
    console.error('[showcase] data load failed:', file, err);
  };
}

/* Shared map behaviour, so every map on the site works the same way.
   Called after Leaflet has loaded (site.js is deliberately loaded before it),
   hence the late reference to the global L. */
function mapExtras(map) {
  map.scrollWheelZoom.enable();

  // Leaflet leaves inertiaMaxSpeed uncapped, so a quick flick coasts as far as
  // the release velocity says — on a full-screen map that throws the view
  // hundreds of miles and reads as the map jumping on its own. Coast distance
  // is v²/(2·deceleration·easeLinearity) = v²/1360 px, so 600 px/s bounds it to
  // ~265 px, about a quarter-screen: still fluid, never disorienting.
  map.options.inertiaMaxSpeed = 600;

  const el = map.getContainer();
  const native = el.requestFullscreen || el.webkitRequestFullscreen;

  // Two ways to fill the screen. The native Fullscreen API is preferred, but it
  // is refused without user activation and inside an iframe that lacks
  // allowfullscreen, so fall back to pinning the map over the viewport — that
  // always works, and the button must never be a no-op.
  const nativeOn = () => (document.fullscreenElement || document.webkitFullscreenElement) === el;
  const maxiOn = () => el.classList.contains('rs-maxi');
  const isFull = () => nativeOn() || maxiOn();

  // A resize must never move the geographic view — but the container's size
  // can arrive in one step (pinned mode) or several (native full screen's
  // animated transition, which also races Leaflet's own window-resize
  // handler). Any scheme that compensates a single step, or restores a
  // remembered view exactly once, shifts the view on the steps it misses —
  // which is precisely how full screen kept relocating London to France.
  // The only ordering-independent approach: track the intended view
  // continuously, freeze tracking the moment a resize begins, and re-assert
  // the view after every settlement.
  let view = { c: map.getCenter(), z: map.getZoom() };
  let frozen = false;
  map.on('moveend zoomend', () => {
    if (!frozen) view = { c: map.getCenter(), z: map.getZoom() };
  });

  // Leaflet's own window-resize handler repositions the map pane the moment
  // the window resizes — but its drag handler caches the pane position at
  // mousedown, so a pane moved between mousedown and the first drag frame
  // makes the drag teleport back to the stale position. On machines where the
  // full-screen transition grows the window in steps over several seconds
  // (observed in the field: 563px to 2499px across ~10s), real gestures land
  // inside that window and every drag snapped ~350km. All resizing is handled
  // by the settle below instead, which waits for the hand to lift.
  if (map._onResize) {
    L.DomEvent.off(window, 'resize', map._onResize, map);
    L.DomEvent.off(window, 'resize', map._onResize);
    map.options.trackResize = false;
  }

  let held = false, rearm = false;
  let settleTimer = null;
  const settle = () => {
    frozen = true;                    // resize in flight: stop trusting moveend
    clearTimeout(settleTimer);
    settleTimer = setTimeout(() => {
      // Nothing may touch the map while a button is down or a drag is live —
      // that is exactly what teleports the gesture. Finish after release.
      if (held || (map.dragging && map.dragging.moving())) {
        rearm = true;
        return;
      }
      map.invalidateSize({ pan: false, animate: false });
      map.setView(view.c, view.z, { animate: false });
      frozen = false;
    }, 120);
  };
  const release = () => {
    held = false;
    if (rearm) { rearm = false; settle(); }
  };
  el.addEventListener('pointerdown', () => { held = true; }, true);
  window.addEventListener('pointerup', release, true);
  window.addEventListener('pointercancel', release, true);
  window.addEventListener('blur', release);
  const RO = window.ResizeObserver;
  // ResizeObserver fires per size step, after layout and before user events,
  // so `frozen` is set before any interaction can record a shifted view.
  if (RO) new RO(settle).observe(el);

  // Deliberately NO mousedown "guard" here. An earlier version re-synced the
  // map inside mousedown when the cached size looked drifted — but fractional
  // CSS sizes (full screen at OS display scaling) keep that comparison
  // permanently tripped, so it fired on EVERY click, mutating the map exactly
  // between Leaflet's drag handler caching its start position and the first
  // drag movement. Result: a flicker on click and the view snapping away the
  // moment a drag began, in full screen only. Any map mutation inside
  // mousedown corrupts the drag gesture; resizes are the ResizeObserver's job.

  // Without ResizeObserver, re-check across the span a transition might take.
  const onTransition = RO ? settle : () => [0, 150, 400, 800].forEach(ms => setTimeout(settle, ms));
  const setMaxi = on => { el.classList.toggle('rs-maxi', on); label(); onTransition(); };

  let label = () => {};
  const Ctl = L.Control.extend({
    options: { position: 'topleft' },
    onAdd: function () {
      const wrap = L.DomUtil.create('div', 'leaflet-bar leaflet-control rs-fs');
      const a = L.DomUtil.create('a', '', wrap);
      a.href = '#';
      a.setAttribute('role', 'button');
      label = () => {
        const on = isFull();
        a.title = on ? 'Exit full screen' : 'View full screen';
        a.setAttribute('aria-label', a.title);
        a.textContent = on ? '✕' : '⛶';
      };
      label();
      L.DomEvent.on(a, 'click', e => {
        L.DomEvent.stop(e);
        if (isFull()) {
          if (nativeOn()) (document.exitFullscreen || document.webkitExitFullscreen).call(document);
          else setMaxi(false);
          return;
        }
        if (!native) return setMaxi(true);
        const p = native.call(el);
        if (p && p.catch) p.catch(() => setMaxi(true));   // refused — pin instead
      });
      return wrap;
    },
  });
  map.addControl(new Ctl());

  const onChange = () => { label(); onTransition(); };
  document.addEventListener('fullscreenchange', onChange);
  document.addEventListener('webkitfullscreenchange', onChange);
  // Escape exits the pinned mode; the native mode handles its own.
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && maxiOn()) setMaxi(false); });
  return map;
}
