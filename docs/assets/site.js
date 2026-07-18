// Shared chrome + tiny chart helpers for the showcase pages.
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (n, dp = 0) => n == null ? '—' : n.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
const card = (v, l, d) => `<div class="card"><div class="v">${v}</div><div class="l">${l}</div>${d ? `<div class="d">${d}</div>` : ''}</div>`;

// ---- nav ----
// site sections, shown inline
const PAGES = [
  ['index.html', 'Overview'],
  ['framework.html', 'Framework'],
  ['routes.html', 'Routes'],
  ['metrics.html', 'Trip metrics'],
  ['trips.html', 'Earnings'],
  ['demand.html', 'Demand'],
  ['charging.html', 'EV costs'],
];
// pipeline-generated artifacts, grouped in a dropdown
const REPORTS = [
  ['dashboards/cnhr_dashboard.html', 'CNHR–MNHR dashboard', '17 weeks · 762 trips'],
  ['dashboards/cnhr_week_20260209.html', 'Single-week deep dive', 'week of 9 Feb 2026'],
  ['dashboards/surge_report.html', 'Surge intelligence report', 'hourly forecast'],
];
(function nav() {
  const here = location.pathname.split('/').pop() || 'index.html';
  // pages inside /dashboards must climb a level to reach the site pages
  const up = /\/dashboards\//.test(location.pathname) ? '../' : '';
  const isReport = REPORTS.some(([h]) => h.split('/').pop() === here);
  const el = document.createElement('nav');
  el.className = 'site';
  el.innerHTML = `<div class="wrap">` +
    `<a class="brand" href="${up}index.html">Ride-share metrics</a>` +
    PAGES.map(([h, t]) => `<a href="${up}${h}" class="${h === here ? 'on' : ''}">${t}</a>`).join('') +
    `<span style="flex:1"></span>` +
    `<div class="navdd">` +
      `<button class="ddbtn${isReport ? ' on' : ''}" id="ddbtn" aria-haspopup="true" aria-expanded="false">Generated reports <span class="chev">▾</span></button>` +
      `<div class="ddmenu" id="ddmenu" style="display:none">` +
        REPORTS.map(([h, t, s]) =>
          `<a href="${up}${h}" class="${h.split('/').pop() === here ? 'on' : ''}"><b>${t}</b><span>${s}</span></a>`).join('') +
      `</div></div></div>`;
  document.body.prepend(el);
  const btn = el.querySelector('#ddbtn'), menu = el.querySelector('#ddmenu');
  // drive visibility inline so the menu still works if a stale stylesheet is cached
  const close = () => { menu.style.display = 'none'; menu.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); };
  btn.addEventListener('click', e => {
    e.stopPropagation();
    const open = menu.style.display !== 'block';
    menu.style.display = open ? 'block' : 'none';
    menu.classList.toggle('open', open);
    btn.setAttribute('aria-expanded', String(open));
  });
  menu.addEventListener('click', e => e.stopPropagation());
  document.addEventListener('click', close);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
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

const getJSON = p => fetch(p).then(r => r.json());
