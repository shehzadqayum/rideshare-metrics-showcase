# -*- coding: utf-8 -*-
"""Re-apply the showcase's post-hoc patches to the two generated dashboards.

The dashboards are pipeline artifacts kept close to what the pipeline emits, so
every change the showcase needs is applied here rather than by hand-editing the
generated file. Each patch is delimited by an HTML marker comment and is
idempotent: running this repeatedly is a no-op, and running it after the
pipeline regenerates a dashboard restores the showcase's fixes.

Existing marker blocks (GLOSSARY, MAPFX, TIDY) were applied by earlier ad-hoc
scripts; this file adds the SHELL block and is where any future patch belongs.
"""
import io, os, re

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs')
DASHBOARDS = ['cnhr_dashboard.html', 'surge_report.html']

FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%9A%97%3C/text%3E%3C/svg%3E\">")

# The dashboards are hard-coded dark and declare no custom properties, so the
# patched-in blocks that use var(--surface) etc. rendered unstyled. Scope
# fallbacks to those blocks only, using the dashboards' own palette.
SHELL = """<!--SHELL-->
<style>
  #glossary{--surface:#0a0f1a;--border:#1e293b;--text:#e2e8f0;--text-muted:#94a3b8;--accent:#f59e0b}
  #map-legend{--text-muted:#94a3b8;--accent:#f59e0b}
  /* Leaflet controls sit at z-index 1000 and tie with the injected toolbar;
     the later DOM node would win, putting zoom buttons over the nav. */
  .leaflet-top,.leaflet-bottom{z-index:900}
  /* The generated stat grid holds 3 columns down to 0px; a 22px bold figure
     plus padding will not fit a third of a phone, forcing the page sideways. */
  @media(max-width:460px){.stats{grid-template-columns:repeat(2,1fr)}}
  /* Wide generated tables should scroll in place, not drag the page. */
  @media(max-width:700px){.table-wrap,.trips-table-wrap{overflow-x:auto}}
  /* Rows for trips with no GPS track must not advertise themselves as clickable. */
  tr.map-clickable.no-track{cursor:default}
  tr.map-clickable.no-track td:first-child{opacity:.55}
  /* Full-screen map, matching the handwritten pages. */
  .leaflet-container:fullscreen,.leaflet-container:-webkit-full-screen{width:100%!important;height:100%!important;border-radius:0}
  .leaflet-container.rs-maxi{position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;z-index:2000!important;border-radius:0}
  .rs-fs a{font-size:15px;line-height:26px;text-align:center;font-weight:600;cursor:pointer}
</style>
<script>
// 406 of 762 trips have no GPS track, but every row is click-wired to
// mapShowTrip, which calls mapClearAll() *before* discovering there is no layer
// to draw - blanking the map with no explanation. Guard it, and mark the rows.
window.addEventListener('load', function () {
  if (typeof window.mapShowTrip !== 'function' || window.__trackGuard) return;
  window.__trackGuard = true;
  var inner = window.mapShowTrip;
  window.mapShowTrip = function (num) {
    var w = (typeof W !== 'undefined' && typeof selIdx !== 'undefined') ? W[selIdx] : null;
    var t = w && w.trips && w.trips.filter(function (x) { return x.n === num; })[0];
    if (t && t.has_gps_track === false) return;   // leave the map as it is
    return inner.apply(this, arguments);
  };
  function markRows() {
    var w = (typeof W !== 'undefined' && typeof selIdx !== 'undefined') ? W[selIdx] : null;
    if (!w || !w.trips) return;
    var noTrack = {};
    w.trips.forEach(function (t) { if (t.has_gps_track === false) noTrack[t.n] = 1; });
    Array.prototype.forEach.call(document.querySelectorAll('tr.map-clickable'), function (r) {
      var c = r.querySelector('td');
      var n = c && parseInt(c.textContent, 10);
      var off = n && noTrack[n];
      r.classList.toggle('no-track', !!off);
      if (off) r.title = 'No GPS track recorded for this trip';
    });
  }
  markRows();
  document.addEventListener('click', function () { setTimeout(markRows, 60); }, true);
});

// The dashboard map is built lazily when the panel is expanded, and this page
// does not load site.js, so poll briefly for it and add the same wheel-zoom +
// full-screen behaviour the handwritten maps get from mapExtras().
window.addEventListener('load', function () {
  var tries = 0;
  var t = setInterval(function () {
    if (++tries > 120) return clearInterval(t);
    var map = window.weekMap;
    if (!map || map.__extras) return;
    clearInterval(t);
    map.__extras = true;
    map.scrollWheelZoom.enable();
    // Uncapped by default, so a flick flings a full-screen map across the
    // country. Coast is v*v/1360 px, so 600 px/s bounds it to ~a quarter screen.
    map.options.inertiaMaxSpeed = 600;
    var el = map.getContainer();
    var native = el.requestFullscreen || el.webkitRequestFullscreen;
    var nativeOn = function () { return (document.fullscreenElement || document.webkitFullscreenElement) === el; };
    var maxiOn = function () { return el.classList.contains('rs-maxi'); };
    var isFull = function () { return nativeOn() || maxiOn(); };
    var label = function () {};
    // A resize must never move the geographic view, but the size can arrive in
    // one step (pinned mode) or several (native full screen animates). Anything
    // that compensates one step, or restores a remembered view exactly once,
    // shifts the view on the steps it misses. Track the intended view
    // continuously, freeze tracking while a resize is in flight, and re-assert
    // the view after every settlement.
    var view = { c: map.getCenter(), z: map.getZoom() };
    var frozen = false;
    map.on('moveend zoomend', function () {
      if (!frozen) view = { c: map.getCenter(), z: map.getZoom() };
    });
    var settleTimer = null;
    var settle = function () {
      frozen = true;
      clearTimeout(settleTimer);
      settleTimer = setTimeout(function () {
        map.invalidateSize({ pan: false, animate: false });
        map.setView(view.c, view.z, { animate: false });
        frozen = false;
      }, 120);
    };
    var RO = window.ResizeObserver;
    if (RO) new RO(settle).observe(el);
    // A click landing mid-transition re-syncs and re-asserts in the same
    // breath - never one without the other.
    map.on('mousedown', function () {
      var r = el.getBoundingClientRect();
      if (Math.abs(map.getSize().x - r.width) > 2 || Math.abs(map.getSize().y - r.height) > 2) {
        var v = view;         // invalidateSize fires moveend synchronously
        frozen = true;
        map.invalidateSize({ pan: false, animate: false });
        map.setView(v.c, v.z, { animate: false });
        frozen = false;
      }
    });
    var onTransition = RO ? settle : function () {
      [0, 150, 400, 800].forEach(function (ms) { setTimeout(settle, ms); });
    };
    var setMaxi = function (on) { el.classList.toggle('rs-maxi', on); label(); onTransition(); };
    var Ctl = L.Control.extend({
      options: { position: 'topleft' },
      onAdd: function () {
        var wrap = L.DomUtil.create('div', 'leaflet-bar leaflet-control rs-fs');
        var a = L.DomUtil.create('a', '', wrap);
        a.href = '#'; a.setAttribute('role', 'button');
        label = function () {
          a.title = isFull() ? 'Exit full screen' : 'View full screen';
          a.setAttribute('aria-label', a.title);
          a.textContent = isFull() ? '✕' : '⛶';
        };
        label();
        L.DomEvent.on(a, 'click', function (e) {
          L.DomEvent.stop(e);
          if (isFull()) {
            if (nativeOn()) (document.exitFullscreen || document.webkitExitFullscreen).call(document);
            else setMaxi(false);
            return;
          }
          if (!native) return setMaxi(true);
          var p = native.call(el);
          if (p && p.catch) p.catch(function () { setMaxi(true); });
        });
        return wrap;
      }
    });
    map.addControl(new Ctl());
    var onChange = function () { label(); onTransition(); };
    document.addEventListener('fullscreenchange', onChange);
    document.addEventListener('webkitfullscreenchange', onChange);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && maxiOn()) setMaxi(false); });
  }, 250);
});
</script>
<!--/SHELL-->"""


def patch(path):
    s = io.open(path, encoding='utf-8', errors='ignore').read()
    orig, log = s, []

    if 'rel="icon"' not in s:
        s = re.sub(r'(<meta name="viewport"[^>]*>)', r'\1\n' + FAVICON, s, count=1)
        log.append('favicon')

    if '<!--SHELL-->' in s:
        s = re.sub(r'<!--SHELL-->.*?<!--/SHELL-->', SHELL, s, flags=re.S)
        log.append('shell (refreshed)')
    else:
        s = s.replace('</head>', SHELL + '\n</head>', 1)
        log.append('shell')

    if s != orig:
        io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    return log


for fn in DASHBOARDS:
    p = os.path.join(DOCS, 'dashboards', fn)
    if not os.path.exists(p):
        print('%-24s missing, skipped' % fn)
        continue
    log = patch(p)
    print('%-24s %s' % (fn, ', '.join(log) if log else '(already current)'))
