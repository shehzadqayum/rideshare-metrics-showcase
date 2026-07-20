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
  const sc = { SUSTAINED: css('--st-sus'), ACCEL_REC: css('--st-acc'), DECEL: css('--st-dec'), STALLED: css('--st-stall') };
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
    Object.entries({ SUSTAINED: '--st-sus', 'ACCEL RECOVERY': '--st-acc', DECELERATING: '--st-dec', STALLED: '--st-stall' })
      .map(([k, v]) => `<span><span class="sw" style="background:var(${v})"></span>${k}</span>`).join('');
}

/* True drawn distance (miles) of a set of route features. The per-trip `mi`
   property rides on BOTH the en-route and the paid segment of each trip, so
   summing it double-counts — measure the geometry instead. */
function trackMiles(features) {
  const R = 3958.8, r = Math.PI / 180;
  let mi = 0;
  (features || []).forEach(f => {
    const c = f.geometry && f.geometry.coordinates;
    if (!c) return;
    for (let i = 1; i < c.length; i++) {
      const dLa = (c[i][1] - c[i - 1][1]) * r, dLo = (c[i][0] - c[i - 1][0]) * r;
      const s = Math.sin(dLa / 2) ** 2 + Math.cos(c[i - 1][1] * r) * Math.cos(c[i][1] * r) * Math.sin(dLo / 2) ** 2;
      mi += 2 * R * Math.asin(Math.sqrt(s));
    }
  });
  return mi;
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
  // Full screen has to contain focus. The pinned mode only PAINTS over the
  // page: everything behind stays laid out, focusable and in the accessibility
  // tree, so Tab walked out of the map into content the user cannot see (13
  // reachable elements on routes.html) with the focus ring apparently gone.
  // Native full screen renders nothing else at all, with the same result.
  const setOutsideInert = on => {
    for (let n = el; n && n.parentNode && n !== document.body; n = n.parentNode) {
      for (const sib of n.parentNode.children) if (sib !== n) sib.toggleAttribute('inert', on);
    }
  };

  // Announced so page controls can move into the map for the duration (see
  // mapOverlay). Both routes into full screen have to fire it.
  const fireFull = () => {
    const on = isFull();
    // Order matters: the controls must move INTO the map before anything left
    // outside is marked inert, or they would be inerted on their way past and
    // stay that way inside the overlay.
    map.fire('rs:full', { full: on });
    setOutsideInert(on);
    if (on) {
      if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
      el.setAttribute('role', 'dialog');
      el.setAttribute('aria-modal', 'true');
      el.setAttribute('aria-label', 'Map, full screen');
    } else {
      ['role', 'aria-modal', 'aria-label'].forEach(a => el.removeAttribute(a));
    }
    // If focus was left on something now inert or gone, bring it into the map.
    const a = document.activeElement;
    if (on && (!a || a === document.body || a.closest('[inert]'))) el.focus({ preventScroll: true });
  };

  // --- resize handling -------------------------------------------------------
  // Two invariants, learned the hard way:
  //  1. Nothing may touch the map while the button is down or a drag is live.
  //     Leaflet caches the pane position at mousedown, so any reposition
  //     before the first drag frame teleports the gesture.
  //  2. Nothing is remembered across time. Every settle derives its anchor
  //     from the map's current state, so a user gesture can never be undone
  //     by a stale record of where the map "should" be.
  // Leaflet's own window-resize handler violates (1) on machines whose
  // full-screen transition resizes in steps over seconds, so it is disarmed;
  // the settle below is the single owner of resize handling.
  if (map._onResize) {
    L.DomEvent.off(window, 'resize', map._onResize, map);
    L.DomEvent.off(window, 'resize', map._onResize);
    map.options.trackResize = false;
  }

  let held = false, rearm = false, dragged = false;
  map.on('dragend', () => { dragged = true; });

  let settleTimer = null;
  const settle = () => {
    clearTimeout(settleTimer);
    settleTimer = setTimeout(() => {
      if (held || (map.dragging && map.dragging.moving())) { rearm = true; return; }
      const z = map.getZoom();
      // Anchor before syncing. After a plain resize, getCenter() still
      // reflects the size the user last stably saw, so re-centring it
      // preserves their framing. After a drag, their framing is whatever
      // sits at the visual centre of the real box (computed independently
      // of the stale size cache), so a drag made mid-transition survives
      // instead of being snapped back.
      const keep = dragged
        ? map.containerPointToLatLng(L.point(el.clientWidth / 2, el.clientHeight / 2))
        : map.getCenter();
      dragged = false;
      map.invalidateSize({ pan: false, animate: false });
      map.setView(keep, z, { animate: false });
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
  // One settle per burst of size steps: each call re-arms the same timer.
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
  // The pinned map covers the viewport but the page behind it still scrolls, so
  // its scrollbars sit on top of the map - the horizontal one covered the
  // bottom of the player bar. Nothing behind a maximised map should scroll.
  const setMaxi = on => {
    el.classList.toggle('rs-maxi', on);
    document.body.classList.toggle('rs-maxi-lock', on);
    label(); fireFull(); onTransition();
  };

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
      // It presents as role="button", but an anchor fires click on Enter only,
      // so Space - the other key a button owes its user - did nothing here.
      L.DomEvent.on(a, 'keydown', e => {
        if (e.key === ' ' || e.key === 'Spacebar') { L.DomEvent.stop(e); a.click(); }
      });
      return wrap;
    },
  });
  map.addControl(new Ctl());

  const onChange = () => { label(); fireFull(); onTransition(); };
  document.addEventListener('fullscreenchange', onChange);
  document.addEventListener('webkitfullscreenchange', onChange);
  // Escape exits the pinned mode; the native mode handles its own.
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && maxiOn()) setMaxi(false); });
  return map;
}

/* Controls authored outside the map are unusable in full screen: the native
   Fullscreen API renders nothing but the map element, and even the pinned
   fallback covers the page (hit-testing confirmed every control returning the
   map itself). That left the playback bar, legend and stats unreachable in the
   one mode where you most want to watch a shift replay.

   The fix is to relocate the REAL control nodes into hosts that sit inside the
   map container, and put them back on exit. Because the same nodes move, every
   event handler and every update path (pbEls.read, the seek sync, the legend
   rebuild) keeps working with nothing rewired.

   spec.bottom -> player bar across the foot; spec.drawer -> panel that folds up
   out of that bar behind a toggle; spec.tr -> panel at top right, collapsible
   where the screen is small (spec.trLabel names its toggle). Nodes are adopted
   in the order given. Pages with no bottom bar (week, demand) use tr alone. */
function mapOverlay(map, spec) {
  const el = map.getContainer();
  const hosts = {}, home = new Map();
  let setDrawer = () => {};
  ['bottom', 'tr'].forEach(k => {
    const nodes = (spec[k] || []).filter(Boolean);
    const drawerNodes = k === 'bottom' ? (spec.drawer || []).filter(Boolean) : [];
    if (!nodes.length && !drawerNodes.length) return;
    const h = L.DomUtil.create('div', 'rs-ov rs-ov-' + k, el);
    let body = h;
    if (k === 'tr') {                      // collapsible header for small screens
      const tog = L.DomUtil.create('button', 'rs-ov-tog', h);
      tog.type = 'button';
      tog.textContent = spec.trLabel || '⚙ Layers & legend';
      tog.setAttribute('aria-expanded', 'false');
      body = L.DomUtil.create('div', 'rs-ov-body', h);
      L.DomEvent.on(tog, 'click', () => {
        const on = !h.classList.contains('open');
        h.classList.toggle('open', on);
        tog.setAttribute('aria-expanded', String(on));
      });
    }
    if (drawerNodes.length) {
      const wrap = L.DomUtil.create('div', 'rs-ov-drawerwrap', h);
      const draw = L.DomUtil.create('div', 'rs-ov-drawer', wrap);
      const tog = L.DomUtil.create('button', 'rs-ov-drawtog', h);
      tog.type = 'button';
      // innerHTML so a label can carry a .lg span that drops on narrow screens
      tog.innerHTML = spec.drawerLabel || '⚙ Layers';
      tog.setAttribute('aria-expanded', 'false');
      // Clipped-but-present content stays focusable, so the drawer is inert
      // while closed rather than merely out of sight.
      draw.inert = true;
      setDrawer = on => {
        h.classList.toggle('draw-open', on);
        tog.setAttribute('aria-expanded', String(on));
        draw.inert = !on;
      };
      L.DomEvent.on(tog, 'click', () => setDrawer(!h.classList.contains('draw-open')));
      // Escape cannot be used to close this: on desktop the map is in NATIVE
      // full screen, where the browser consumes Escape to exit and no handler
      // can prevent it. Closing on a map gesture is the reliable equivalent.
      // dragstart, NOT movestart: movestart also fires for programmatic moves,
      // so a day change (which refits) or a resize settle would shut the panel
      // under the viewer's hand.
      map.on('click dragstart', () => setDrawer(false));
      hosts.drawer = { body: draw, nodes: drawerNodes };
    }
    // Without this, dragging the scrubber pans the map underneath and a click
    // on any button also registers as a map click (which clears the isolation).
    L.DomEvent.disableClickPropagation(h);
    L.DomEvent.disableScrollPropagation(h);
    if (nodes.length) hosts[k] = { body, nodes };
  });

  // Leaflet puts the tile attribution bottom-right, exactly where the player
  // bar goes. The licences have to stay legible, so lift that corner clear.
  const lift = () => el.style.setProperty('--rsov-b',
    (hosts.bottom ? hosts.bottom.body.offsetHeight : 0) + 'px');

  function adopt(on) {
    if (on === el.classList.contains('rs-ov-on')) return;
    // Moving a subtree that contains the focused element blurs it, so pressing
    // Escape from the Play button dropped focus to <body>.
    const active = document.activeElement;
    if (on) {
      Object.values(hosts).forEach(h => h.nodes.forEach(n => {
        const mark = document.createComment('rs-ov');   // the exact spot to restore to
        n.parentNode.insertBefore(mark, n);
        home.set(n, mark);
        h.body.append(n);
      }));
    } else {
      setDrawer(false);            // never reopen full screen with it left hanging
      home.forEach((mark, n) => { mark.parentNode.insertBefore(n, mark); mark.remove(); });
      home.clear();
    }
    el.classList.toggle('rs-ov-on', on);
    if (active && active.isConnected && active !== document.body) active.focus({ preventScroll: true });
    requestAnimationFrame(lift);
  }

  map.on('rs:full', e => adopt(e.full));
  if (window.ResizeObserver && hosts.bottom) new ResizeObserver(lift).observe(hosts.bottom.body);
  return { adopt, setDrawer };
}
