/* Shared quick-links toolbar — identical on every page.
   The generated dashboards are hard-coded dark and define no CSS variables, so
   the palette is chosen at runtime from the page's own background luminance. */
(function () {
  var PAGES = [
    ['index.html', 'Overview'],
    ['framework.html', 'Framework'],
    ['routes.html', 'Routes'],
    ['week.html', 'Week deep dive'],
    ['metrics.html', 'Trip metrics'],
    ['trips.html', 'Earnings'],
    ['demand.html', 'Demand'],
    ['charging.html', 'EV costs'],
  ];
  // Genuine pipeline output only — week.html is handwritten and lives in PAGES.
  var REPORTS = [
    ['dashboards/cnhr_dashboard.html', 'CNHR–MNHR dashboard', '17 weeks · 762 trips'],
    ['dashboards/surge_report.html', 'Surge intelligence report', 'hourly forecast'],
  ];

  if (document.querySelector('.rsnav')) return;
  var here = location.pathname.split('/').pop() || 'index.html';
  var up = /\/dashboards\//.test(location.pathname) ? '../' : '';
  var onReport = REPORTS.some(function (r) { return r[0].split('/').pop() === here; });

  // ---- pick a palette from the page's real background ----------------------
  function lum(col) {
    var m = /rgba?\(([^)]+)\)/.exec(col || '');
    if (!m) return null;
    var p = m[1].split(',').map(parseFloat);
    if (p.length > 3 && p[3] === 0) return null;                 // transparent
    return (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]) / 255;
  }
  var L = lum(getComputedStyle(document.body).backgroundColor);
  if (L === null) L = lum(getComputedStyle(document.documentElement).backgroundColor);
  if (L === null) L = 1;                                          // assume light
  var dark = L < 0.4;
  var P = dark
    ? { bg: '#111823', fg: '#e8edf4', mut: '#94a3b8', bd: 'rgba(255,255,255,.14)',
        hov: 'rgba(255,255,255,.09)', sel: 'rgba(255,255,255,.13)', acc: '#4da6ff', sh: 'rgba(0,0,0,.55)' }
    : { bg: '#fcfcfb', fg: '#0b0b0b', mut: '#5a5a5a', bd: 'rgba(11,11,11,.12)',
        hov: 'rgba(11,11,11,.06)', sel: 'rgba(11,11,11,.08)', acc: '#2a78d6', sh: 'rgba(0,0,0,.18)' };

  var CSS = [
    '.rsnav{position:sticky;top:0;z-index:1000;background:var(--n-bg);border-bottom:1px solid var(--n-bd);',
    '  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.3}',
    '.rsnav .in{max-width:1120px;margin:0 auto;padding:9px 20px;display:flex;align-items:center;gap:2px}',
    '.rsnav a{color:var(--n-mut);text-decoration:none;font-size:.85rem;padding:6px 10px;',
    '  border-radius:7px;white-space:nowrap}',
    '.rsnav a:hover{color:var(--n-fg);background:var(--n-hov)}',
    '.rsnav a.on{color:var(--n-fg);background:var(--n-sel);font-weight:600}',
    '.rsnav a.rsbrand{color:var(--n-fg);font-weight:650;font-size:.95rem;margin-right:12px}',
    '.rsnav a.rsbrand:hover{background:transparent}',
    '.rsnav .sp{flex:1}',
    '.rsdd{position:relative}',
    '.rsdd button{font:inherit;font-size:.85rem;cursor:pointer;display:inline-flex;align-items:center;gap:6px;',
    '  color:var(--n-mut);background:transparent;border:1px solid var(--n-bd);border-radius:8px;',
    '  padding:6px 11px;white-space:nowrap}',
    '.rsdd button:hover,.rsdd button.on{color:var(--n-fg);border-color:var(--n-acc)}',
    '.rsdd button .cv{font-size:.7rem;opacity:.7}',
    '.rsdd .menu{position:absolute;right:0;top:calc(100% + 7px);min-width:264px;display:none;',
    '  background:var(--n-bg);border:1px solid var(--n-bd);border-radius:11px;padding:6px;',
    '  box-shadow:0 12px 30px var(--n-sh);z-index:1001}',
    '.rsdd .menu.open{display:block}',
    '.rsdd .menu a{display:block;padding:8px 11px;border-radius:8px;white-space:normal}',
    '.rsdd .menu a b{display:block;color:var(--n-fg);font-size:.85rem;font-weight:600}',
    '.rsdd .menu a i{display:block;font-style:normal;color:var(--n-mut);font-size:.74rem;margin-top:1px}',
    '@media(max-width:820px){.rsnav .in{flex-wrap:wrap;gap:1px}.rsnav a{padding:5px 7px;font-size:.8rem}',
    '  .rsnav .sp{flex-basis:100%;height:0}.rsdd .menu{right:auto;left:0}}',
    /* Touch targets (WCAG 2.5.5). The toolbar links are ~30px tall - type plus
       6px of padding - and the 820px rule takes them to ~27px, which is the
       phone case. Raised on a coarse pointer only, so a mouse keeps the dense
       bar. inline-flex because min-height alone would leave the label sitting
       at the top of the taller box; the row gives back its own vertical
       padding so this sticky bar does not grow by the full 14px. These rules
       must live here rather than in style.css: the generated dashboards load
       nav.js and not style.css. */
    '@media(pointer:coarse),(max-width:760px){',
    '  .rsnav .in{padding-top:2px;padding-bottom:2px}',
    '  .rsnav .in > a{min-height:44px;display:inline-flex;align-items:center}',
    '  .rsdd button{min-height:44px}',
    '  .rsdd .menu a{min-height:44px}}',
    /* The skip link's hiding styles must live HERE, not in style.css: the
       generated dashboards load nav.js but not style.css, and an unstyled
       skip link renders as visible text above the toolbar. */
    '.rsskip{position:absolute;left:-9999px;top:0;z-index:1002;background:var(--n-bg);color:var(--n-fg);',
    '  border:1px solid var(--n-acc);border-radius:0 0 8px 0;padding:9px 14px;font-size:.85rem;text-decoration:none}',
    '.rsskip:focus{left:0}'
  ].join('');

  var st = document.createElement('style');
  st.setAttribute('data-rsnav', '');
  st.textContent = CSS;
  document.head.appendChild(st);

  function link(h, t, cls) {
    return '<a href="' + up + h + '"' + (cls ? ' class="' + cls + '"' : '') + '>' + t + '</a>';
  }
  // The toolbar is a wall of links before the content, so give keyboard and
  // screen-reader users a way past it — but only where the page HAS a main
  // region to land on. The generated dashboards have neither <main> nor
  // .wrap, and a skip link with no target is just clutter.
  var main = document.querySelector('main, .wrap');
  var skip = null;
  if (main) {
    if (!main.id) main.id = 'rsmain';
    if (!main.hasAttribute('tabindex')) main.setAttribute('tabindex', '-1');
    skip = document.createElement('a');
    skip.className = 'rsskip';
    skip.href = '#' + main.id;
    skip.textContent = 'Skip to main content';
  }

  var nav = document.createElement('nav');
  nav.className = 'rsnav';
  nav.setAttribute('aria-label', 'Site sections');
  Object.keys(P).forEach(function (k) { nav.style.setProperty('--n-' + k, P[k]); });
  nav.innerHTML = '<div class="in">'
    + link('index.html', 'Ride-share metrics', 'rsbrand')
    + PAGES.map(function (p) { return link(p[0], p[1], p[0] === here ? 'on' : ''); }).join('')
    + '<span class="sp"></span>'
    + '<div class="rsdd"><button type="button" id="rsddbtn" aria-haspopup="true" aria-expanded="false"'
    + (onReport ? ' class="on"' : '') + '>Generated reports <span class="cv">▾</span></button>'
    + '<div class="menu" id="rsddmenu" style="display:none">'
    + REPORTS.map(function (r) {
        return '<a href="' + up + r[0] + '"' + (r[0].split('/').pop() === here ? ' class="on"' : '') + '>'
             + '<b>' + r[1] + '</b><i>' + r[2] + '</i></a>';
      }).join('')
    + '</div></div></div>';
  document.body.insertBefore(nav, document.body.firstChild);

  // A padded <body> insets its children: the generated dashboard has
  // body{padding:16px}, which dropped the toolbar ~16px down and in compared
  // with every other page. Cancel the padding with negative margins so the
  // bar is always flush with the viewport, and return the vertical space
  // below it so the page's own content spacing is unchanged.
  var bp = getComputedStyle(document.body);
  if (parseFloat(bp.paddingTop)) {
    nav.style.marginTop = '-' + bp.paddingTop;
    nav.style.marginBottom = bp.paddingTop;
  }
  if (parseFloat(bp.paddingLeft)) nav.style.marginLeft = '-' + bp.paddingLeft;
  if (parseFloat(bp.paddingRight)) nav.style.marginRight = '-' + bp.paddingRight;

  if (skip) {
    document.body.insertBefore(skip, nav);
    // The skip link sits outside the nav element, so it needs the palette too.
    Object.keys(P).forEach(function (k) { skip.style.setProperty('--n-' + k, P[k]); });
  }

  // Pages pin their own sticky bars below this one, so publish the real height
  // rather than let them guess: the toolbar wraps to two rows under 820px.
  function publishHeight() {
    document.documentElement.style.setProperty('--rsnav-h', nav.offsetHeight + 'px');
  }
  publishHeight();
  window.addEventListener('resize', publishHeight);
  if (window.ResizeObserver) new ResizeObserver(publishHeight).observe(nav);

  var btn = nav.querySelector('#rsddbtn'), menu = nav.querySelector('#rsddmenu');
  function close() { menu.style.display = 'none'; menu.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    var open = menu.style.display !== 'block';
    menu.style.display = open ? 'block' : 'none';
    menu.classList.toggle('open', open);
    btn.setAttribute('aria-expanded', String(open));
  });
  menu.addEventListener('click', function (e) { e.stopPropagation(); });
  document.addEventListener('click', close);

  // Keyboard: Escape closes and returns focus to the button; Down opens and
  // steps into the menu; Up/Down cycle within it.
  var items = function () { return [].slice.call(menu.querySelectorAll('a')); };
  btn.addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowDown' && e.key !== 'Enter' && e.key !== ' ') return;
    if (menu.style.display !== 'block') { e.preventDefault(); btn.click(); }
    if (e.key === 'ArrowDown') { e.preventDefault(); var f = items()[0]; if (f) f.focus(); }
  });
  menu.addEventListener('keydown', function (e) {
    var list = items(), i = list.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); (list[i + 1] || list[0]).focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); (list[i - 1] || list[list.length - 1]).focus(); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || menu.style.display !== 'block') return;
    close(); btn.focus();
  });
})();

/* ---- sharing metadata + authorship -------------------------------------
   This URL gets pasted into application forms, LinkedIn messages and recruiter
   chat. Without og: tags it previewed as a bare string of characters in every
   client that reads them exclusively (WhatsApp, Signal, iMessage), which is a
   poor first impression of a portfolio about presenting data well.

   And the site never said whose portfolio it was: a hiring manager forwarded
   the link with no CV attached had no name, no contact and no way to connect it
   to an application. Injected here because nav.js already runs on every page,
   so it is one edit rather than eight that can drift apart. */
(function meta() {
  var AUTHOR = 'Shehzad Qayum';
  var SITE = 'https://shehzadqayum.github.io/rideshare-metrics-showcase/';
  var head = document.head;
  var page = (location.pathname.split('/').pop() || 'index.html');
  var title = (document.title || 'Ride-share metrics').replace(/\s*—.*$/, '');
  var desc = (document.querySelector('meta[name=description]') || {}).content || '';

  var add = function (attr, key, val) {
    if (!val || head.querySelector('meta[' + attr + '="' + key + '"]')) return;
    var m = document.createElement('meta');
    m.setAttribute(attr, key); m.content = val; head.appendChild(m);
  };
  add('name', 'author', AUTHOR);
  add('property', 'og:type', 'website');
  add('property', 'og:site_name', 'Ride-share metrics — a working showcase');
  add('property', 'og:title', document.title || title);
  add('property', 'og:description', desc);
  add('property', 'og:url', SITE + (page === 'index.html' ? '' : page));
  add('name', 'twitter:card', 'summary_large_image');
  add('name', 'twitter:title', document.title || title);
  add('name', 'twitter:description', desc);
  // Canonical, so the with- and without-index.html forms do not compete.
  if (!head.querySelector('link[rel=canonical]')) {
    var c = document.createElement('link');
    c.rel = 'canonical'; c.href = SITE + (page === 'index.html' ? '' : page);
    head.appendChild(c);
  }
  // A byline, once, at the foot of whichever container the page uses.
  var host = document.querySelector('footer.site') || document.querySelector('main, .wrap');
  if (host && !document.getElementById('rsby')) {
    var b = document.createElement('div');
    b.id = 'rsby';
    b.style.cssText = 'margin-top:14px;font-size:.74rem;color:var(--muted)';
    b.innerHTML = 'Built by <b style="color:var(--ink2)">' + AUTHOR + '</b> · ' +
      '<a href="https://github.com/shehzadqayum">github.com/shehzadqayum</a>';
    host.appendChild(b);
  }
})();
