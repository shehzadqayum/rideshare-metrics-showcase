# -*- coding: utf-8 -*-
"""Authoritative route extraction from raw GPX, replacing the daily-map approach.

For every trip in the metrics week_*.json files, slice the merged GPX trackpoints
into an enroute (accept->pickup) and trip (pickup->dropoff) segment, simplify with
Ramer-Douglas-Peucker, and emit:
  docs/data/routes.json   - per-day GeoJSON for routes.html (+ coverage summary)
and inject the tracks into docs/dashboards/cnhr_dashboard.html by verified
positional trip_id join (GPS weeks align 1:1 with the dashboard's var W).

Trips whose GPX window has no points are flagged no_gps.
"""
import json, glob, re, os, bisect, math, hashlib
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

BASE = '//R7000/bt2/Projects/uber'
DOCS = os.path.join(os.path.dirname(__file__), '..', 'docs')
NS = {'g': 'http://www.topografix.com/GPX/1/1'}

# ---------------------------------------------------------------- GPX load
def load_gpx():
    pts = []
    for f in glob.glob(BASE + '/GPX Tracker/*.gpx'):
        try:
            root = ET.parse(f).getroot()
        except Exception:
            continue
        for tp in root.iterfind('.//g:trkpt', NS):
            t = tp.find('g:time', NS)
            if t is None or not t.text:
                continue
            try:
                ep = datetime.fromisoformat(t.text.strip().replace('Z', '+00:00')).timestamp()
            except Exception:
                continue
            pts.append((ep, round(float(tp.get('lat')), 5), round(float(tp.get('lon')), 5)))
    pts.sort()
    return pts, [p[0] for p in pts]

def ttime(s):
    s = re.sub(r'[^0-9]', '', s or '')
    if len(s) < 14:
        return None
    # London is UTC (GMT) across all GPS-covered dates (Dec-early Mar, pre 29-Mar DST)
    return datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]), int(s[10:12]), int(s[12:14]),
                    tzinfo=timezone.utc).timestamp()

def slice_track(pts, keys, t0, t1):
    """Return (lat, lon, epoch) triples for the trip window, collapsing each
    stationary run to its first + last point so a stop keeps its real duration
    (needed for true-time playback) without bloating the track."""
    if not t0 or not t1 or t1 < t0:
        return []
    lo = bisect.bisect_left(keys, t0 - 20)
    hi = bisect.bisect_right(keys, t1 + 20)
    seg = [(pts[i][1], pts[i][2], pts[i][0]) for i in range(lo, hi)]   # (lat, lon, ep)
    out = []
    for p in seg:
        if out and out[-1][0] == p[0] and out[-1][1] == p[1]:
            if len(out) >= 2 and out[-2][0] == p[0] and out[-2][1] == p[1]:
                out[-1] = p            # extend the dwell: keep entry + latest ep
            else:
                out.append(p)          # second point of a new stationary run
        else:
            out.append(p)
    return out

# ---------------------------------------------------------------- RDP (time-aware)
def rdp_t(points, eps=0.00008, gap=20):   # ~9 m; points are (lat, lon, ep)
    """Ramer-Douglas-Peucker on position, but force-keep points that bound a
    time gap > `gap`s (a stop or sparse sample) so the pacing survives."""
    n = len(points)
    if n < 3:
        return points
    keep = [False] * n
    keep[0] = keep[-1] = True
    for i in range(1, n):
        if points[i][2] - points[i - 1][2] > gap:
            keep[i - 1] = True; keep[i] = True
    anchors = [i for i in range(n) if keep[i]]
    for a, b in zip(anchors, anchors[1:]):
        if b - a < 2:
            continue
        stack = [(a, b)]
        while stack:
            i0, i1 = stack.pop()
            ax, ay = points[i0][0], points[i0][1]
            bx, by = points[i1][0], points[i1][1]
            dx, dy = bx - ax, by - ay
            norm = math.hypot(dx, dy) or 1e-12
            dmax, idx = 0.0, -1
            for i in range(i0 + 1, i1):
                px, py = points[i][0], points[i][1]
                d = abs((px - ax) * dy - (py - ay) * dx) / norm
                if d > dmax:
                    dmax, idx = d, i
            if dmax > eps and idx != -1:
                keep[idx] = True
                stack.append((i0, idx)); stack.append((idx, i1))
    return [points[i] for i in range(n) if keep[i]]

def time_props(seg3):
    """Per-point relative seconds + the segment's start (seconds since midnight,
    London = UTC for all GPS-covered dates). Feeds true-time playback."""
    t0 = seg3[0][2]
    return {'s0': int(t0 % 86400), 't': [int(round(p[2] - t0)) for p in seg3]}

# ---------------------------------------------------------------- helpers
# Published tracks must never begin at a habitual origin: the first en-route
# point of a shift is wherever the driver accepted the job, which for the first
# trip of the day is home. Clip the leading HEAD_TRIM_M of every en-route leg so
# no start point survives; legs shorter than that are dropped outright.
HEAD_TRIM_M = 500.0

# The per-leg clip above is necessary but NOT sufficient, which a review of the
# published data proved rather than predicted. Two ways it leaked:
#
#  1. It only ever ran on the EN-ROUTE leg. When the first pickup of a day was
#     inside the clip radius, trim_head returned [] and the leg was dropped —
#     but the paired TRIP leg was published untouched, starting at that pickup.
#     Seven days published a first point 129-410 m from one common centre.
#
#  2. A CONSTANT radius leaves a ring, not a scatter. Fourteen more days put
#     their first point 292-1124 m from a second centre; a circle fitted to a
#     ring recovers its centre far better than the radius suggests.
#
# So: exclude a disc around every habitual origin from ALL published geometry,
# with a radius that varies per day so the residual is an annulus. The radius is
# derived from the date, not random, so a rebuild reproduces byte-identical
# output instead of silently reshuffling what is published.
TRIM_MIN_M, TRIM_MAX_M = 500.0, 1500.0
ORIGIN_CLUSTER_M = 1500.0        # day-origins closer than this are the same place

def day_radius(day):
    h = int(hashlib.sha256(day.encode()).hexdigest()[:8], 16)
    return TRIM_MIN_M + (h % 10007) / 10007.0 * (TRIM_MAX_M - TRIM_MIN_M)

def habitual_origins(day_origin):
    """Greedy-cluster the raw first position of each day; return cluster centres."""
    clusters = []
    for day in sorted(day_origin):
        p = day_origin[day]
        for cl in clusters:
            if metres(cl['c'], p) < ORIGIN_CLUSTER_M:
                cl['pts'].append(p)
                cl['c'] = (sum(q[0] for q in cl['pts']) / len(cl['pts']),
                           sum(q[1] for q in cl['pts']) / len(cl['pts']))
                break
        else:
            clusters.append({'c': (p[0], p[1]), 'pts': [p]})
    return [cl['c'] for cl in clusters]

def scrub_track(seg3, origins, radius):
    """Drop points inside `radius` of any origin, keeping the longest surviving
    contiguous run — dropping from the middle would otherwise splice two distant
    stretches into one straight line across the excluded area."""
    if not seg3:
        return []
    ok = [all(metres((p[0], p[1]), o) >= radius for o in origins) for p in seg3]
    best_i = best_n = cur_i = cur_n = 0
    for i, good in enumerate(ok):
        if good:
            if cur_n == 0:
                cur_i = i
            cur_n += 1
            if cur_n > best_n:
                best_i, best_n = cur_i, cur_n
        else:
            cur_n = 0
    return seg3[best_i:best_i + best_n] if best_n >= 2 else []

def metres(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    x = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return 2 * 6371000.0 * math.asin(math.sqrt(x))

def trim_head(track, dist=HEAD_TRIM_M):
    """Drop leading points until `dist` from the raw origin; [] if too short."""
    if not track:
        return []
    for i, p in enumerate(track):
        if metres(track[0], p) >= dist:
            return track[i:]
    return []

# Doorstep suppression. The habitual-origin discs above protect places the
# driver returns to, but every leg also *ends* at a passenger's door, and those
# endpoints were published to five decimals (~1 m) next to a date and a clock
# time while the stated policy is area-level only. Rounding the published
# coordinate alone would be cosmetic, because the endpoint is simply the track's
# own last point. So clip a per-trip distance off both ends of every leg: the
# geometry then starts and stops on a road near the address instead of at it.
# The distance comes from the trip id, so a rebuild reproduces the same output
# rather than silently reshuffling what is published.
END_MIN_M, END_MAX_M = 200.0, 400.0
COORD_DP = 4                     # ~11 m — finer than that is not honest here

def endpoint_trim(track, tid):
    """Clip both ends of a leg by a per-trip distance; [] if too little is left."""
    if len(track) < 2:
        return []
    h = int(hashlib.sha256(('end' + tid).encode()).hexdigest()[:8], 16)
    d = END_MIN_M + (h % 10007) / 10007.0 * (END_MAX_M - END_MIN_M)
    cut = trim_head(trim_head(track, d)[::-1], d)[::-1]
    return cut if len(cut) >= 2 else []

# Area labels must stay at locality/outcode granularity. The comma-split
# fallback below can surface a street or a building entrance when the source
# address has no locality in the expected position, so anything that still
# looks like a street, venue or pick-up bay is demoted to plain "London".
# Abbreviated suffixes matter as much as the spelled-out ones: "Oxeye Wy" is a
# residential street and it walked straight through a filter that only knew
# "way". A review found two such labels published, one attached to a
# metre-precision dropoff carrying a date and a clock time.
# Built from a word list rather than one long pattern, because the abbreviated
# suffixes are the ones that leak: "Oxeye Wy" is a residential street and it
# walked straight through a filter that only knew "way". A review found two such
# labels published, one attached to a metre-precision dropoff carrying a date
# and a clock time. A list is also far easier to extend than an escaped blob.
STREET_WORDS = [
    'street', 'st', 'road', 'rd', 'lane', 'ln', 'avenue', 'ave', 'av',
    'close', 'cl', 'drive', 'dr', 'gardens', 'gdns', 'gdn', 'court', 'ct',
    'way', 'wy', 'crescent', 'cres', 'terrace', 'ter', 'place', 'pl',
    'square', 'sq', 'mews', 'walk', 'row', 'grove', 'rise', 'vale', 'mead',
    'wharf', 'entrance', 'exit', 'house', 'flat', 'apartment',
    'parking', 'level', 'station', 'platform',
]
STREETY = re.compile(
    r'\b(?:' + '|'.join(STREET_WORDS) + r')\b'      # any street-ish suffix
    r'|pick-?up|--|\['                              # bay / pickup / junk markers
    r'|^\s*\d+\s',                                  # leading house number
    re.I)

AREA_RE = re.compile(r'([A-Z]{1,2}[0-9][0-9A-Z]?)\s*[0-9][A-Z]{2}$')
def area(addr):
    if not addr:
        return ''
    m = AREA_RE.search(addr.strip())
    out = m.group(1) if m else ''
    parts = [p.strip() for p in addr.split(',')]
    loc = parts[-2] if len(parts) >= 2 else (parts[0] if parts else '')
    loc = re.sub(r'\b[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9]?[A-Z]{0,2}\b', '', loc).strip() or 'London'
    if STREETY.search(loc):
        loc = 'London'
    return f'{loc} {out}'.strip()

def earn_val(t):
    e = t.get('earnings_final')
    if isinstance(e, dict):
        e = e.get('total')
    if e is None:
        e = (t.get('earnings') or {}).get('total')
    if e is None:
        e = t.get('earnings_portal') or t.get('earnings_screenshot')
    return e

def main():
    pts, keys = load_gpx()
    print(f'GPX points: {len(pts)}')

    mfiles = {re.search(r'week_(\d{8})', f).group(1): f
              for f in glob.glob(BASE + '/uber_screen/reports/metrics/week_*.json')}

    day_origin = {}              # day -> raw (lat,lon,epoch) of that day's first fix
    pending = []                 # trips held until the origins are known
    days = {}                    # day -> list of GeoJSON features
    tracks_by_id = {}            # trip_id -> {'enroute':[[lat,lon]...],'trip':[...]}
    week_cov = {}                # weekkey -> {label, trips, gps}
    total = gps = 0

    # addresses live in the daily trips_*.json (not the metrics files) — index by trip_id
    daily_info = {}              # trip_id -> {'from','to','trip_min'}
    for tf in glob.glob(BASE + '/uber_screen/reports/trips_*.json'):
        try:
            dd = json.load(open(tf, encoding='utf-8'))
        except Exception:
            continue
        for t in dd.get('trips', []):
            tid = t.get('trip_id')
            if not tid:
                continue
            seg = (t.get('segments') or {}).get('trip') or {}
            dur = (seg.get('actual') or {}).get('duration_minutes')
            daily_info[tid] = {
                'from': area((t.get('pickup') or {}).get('address')),
                'to': area((t.get('dropoff') or {}).get('address')),
                'trip_min': dur,
            }

    # need week labels from the dashboard var W? use metrics week_label
    for wk, mf in sorted(mfiles.items()):
        m = json.load(open(mf, encoding='utf-8'))
        label = m.get('week_label', wk)
        wtrips = m.get('trips', [])
        wg = 0
        for t in wtrips:
            total += 1
            tid = t.get('trip_id')
            ts = t.get('timestamps') or {}
            acc, pick, drop = ttime(ts.get('accept')), ttime(ts.get('pickup')), ttime(ts.get('dropoff'))
            enr_raw = rdp_t(slice_track(pts, keys, acc, pick))          # (lat,lon,ep) triples
            trp = rdp_t(slice_track(pts, keys, pick, drop))
            # The day's true first position, recorded BEFORE any clipping —
            # this is what the exclusion discs are centred on later.
            first_raw = enr_raw[0] if enr_raw else (trp[0] if trp else None)
            if first_raw and tid:
                d0 = tid[:8]
                if d0 not in day_origin or first_raw[2] < day_origin[d0][2]:
                    day_origin[d0] = first_raw
            enr = trim_head(enr_raw)
            has = len(trp) >= 2 or len(enr) >= 2
            met = t.get('metrics') or {}
            svc = (t.get('service') or '').upper() or None
            info = daily_info.get(tid, {})
            mi = met.get('trip_miles') or t.get('trip_miles')
            if not mi and len(trp) >= 2:   # fall back to measuring the GPS track itself
                tot = 0.0
                for j in range(len(trp) - 1):
                    la1, lo1 = trp[j][0], trp[j][1]; la2, lo2 = trp[j + 1][0], trp[j + 1][1]
                    dla = math.radians(la2 - la1); dlo = math.radians(lo2 - lo1)
                    aa = math.sin(dla / 2) ** 2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dlo / 2) ** 2
                    tot += 2 * 3958.8 * math.asin(math.sqrt(aa))
                mi = round(tot, 2)
            mins = (info.get('trip_min')
                    or met.get('trip_duration_minutes')
                    or (round((drop - pick) / 60.0, 1) if (pick and drop and drop > pick) else None)
                    or ((t.get('gps_tracks') or {}).get('summary') or {}).get('total_duration_minutes'))
            mph = round(mi / (mins / 60.0), 1) if (mi and mins and mins > 0) else None
            props_common = {
                'trip': tid, 'service': svc,
                'mi': round(mi, 2) if mi else mi,
                'min': round(mins, 1) if mins else mins,
                'mph': mph,
                'gbp': earn_val(t),
                'from': info.get('from', ''),
                'to': info.get('to', ''),
            }
            if has:
                # Held, not emitted. The exclusion discs are centred on habitual
                # origins, which are only known once EVERY day has been read, so
                # nothing can be published until the whole pass is done.
                pending.append({'wk': wk, 'tid': tid, 'props': props_common,
                                'enr': enr, 'trp': trp})
        week_cov[wk] = {'label': label, 'trips': len(wtrips), 'gps': 0}

    # ---- privacy pass: exclude a varying disc around every habitual origin ----
    origins = habitual_origins(day_origin)
    print(f'habitual origins: {len(origins)} from {len(day_origin)} tracked days')
    dropped_legs = 0
    for it in pending:
        day = it['tid'][:8]
        r = day_radius(day)
        enr = endpoint_trim(scrub_track(it['enr'], origins, r), it['tid'] + 'e')
        trp = endpoint_trim(scrub_track(it['trp'], origins, r), it['tid'] + 't')
        dropped_legs += (len(it['enr']) >= 2 and len(enr) < 2) + (len(it['trp']) >= 2 and len(trp) < 2)
        if len(enr) < 2 and len(trp) < 2:
            continue
        gps += 1
        week_cov[it['wk']]['gps'] += 1
        # dashboard keeps position-only [lat,lon] (no per-point time — it
        # doesn't animate); routes.json carries the timing for playback.
        tracks_by_id[it['tid']] = {'enroute': [[round(a, COORD_DP), round(b, COORD_DP)] for a, b, _ in enr],
                                   'trip': [[round(a, COORD_DP), round(b, COORD_DP)] for a, b, _ in trp]}
        fc = days.setdefault(day, [])
        if len(enr) >= 2:
            fc.append({'type': 'Feature',
                       'geometry': {'type': 'LineString', 'coordinates': [[round(b, COORD_DP), round(a, COORD_DP)] for a, b, _ in enr]},
                       'properties': dict(it['props'], seg='enroute', **time_props(enr))})
        if len(trp) >= 2:
            fc.append({'type': 'Feature',
                       'geometry': {'type': 'LineString', 'coordinates': [[round(b, COORD_DP), round(a, COORD_DP)] for a, b, _ in trp]},
                       'properties': dict(it['props'], seg='trip', **time_props(trp))})
    print(f'privacy pass: {dropped_legs} legs clipped away entirely')

    # Self-check, printed as distances only — never coordinates. The guarantee is
    # that no published point survives inside its day's exclusion radius of any
    # habitual origin. This is the assertion the earlier per-leg trim could not
    # make, and the one a review found it silently breaking.
    worst = None
    for day, fc in days.items():
        r = day_radius(day)
        for f in fc:
            for lon, lat in f['geometry']['coordinates']:
                d = min(metres((lat, lon), o) for o in origins)
                if worst is None or d - r < worst[0]:
                    worst = (d - r, d, r)
    if worst:
        slack, d, r = worst
        ok = 'OK' if slack >= -1.0 else 'BREACH'
        print(f'privacy check: {ok} - closest published point sits {d:.0f} m from the '
              f'nearest habitual origin, against a {r:.0f} m exclusion for that day '
              f'(margin {slack:+.0f} m)')
        print(f'exclusion radii range {TRIM_MIN_M:.0f}-{TRIM_MAX_M:.0f} m, varying by day')

    # routes.json for routes.html
    routes = {
        'days': {d: {'type': 'FeatureCollection', 'features': fc} for d, fc in sorted(days.items())},
        'coverage': {
            'total_trips': total, 'gps_trips': gps,
            'weeks': [{'week': wk, 'label': c['label'], 'trips': c['trips'], 'gps': c['gps']}
                      for wk, c in sorted(week_cov.items())],
        },
    }
    outp = os.path.join(DOCS, 'data', 'routes.json')
    json.dump(routes, open(outp, 'w'), separators=(',', ':'))
    print(f'routes.json: {os.path.getsize(outp)/1024:.0f} KB, {len(days)} days, {gps}/{total} trips with routes')

    # ---- inject into combined dashboard by positional join (GPS weeks only) ----
    p = os.path.join(DOCS, 'dashboards', 'cnhr_dashboard.html')
    s = open(p, encoding='utf-8', errors='ignore').read()
    a = s.find('var W=') + 6
    depth = 0; instr = False; esc = False; end = None
    for k in range(a, len(s)):
        c = s[k]
        if instr:
            if esc: esc = False
            elif c == chr(92): esc = True
            elif c == '"': instr = False
            continue
        if c == '"': instr = True
        elif c == '[': depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0: end = k + 1; break
    W = json.loads(s[a:end])
    assigned = flagged = relabelled = 0
    for w in W:
        wk = w['key'].replace('-', '')
        mf = mfiles.get(wk)
        mt = json.load(open(mf, encoding='utf-8'))['trips'] if mf else []
        aligned = len(mt) == len(w['trips'])
        for i, dt in enumerate(w['trips']):
            tid = mt[i]['trip_id'] if (aligned and i < len(mt)) else None
            # The generator truncates addresses mid-word, so area() cannot re-parse
            # them; take the already-reduced label where the join gives us one and
            # demote anything street- or venue-shaped otherwise.
            info = daily_info.get(tid) if tid else None
            for fld, src in (('pickup', 'from'), ('dropoff', 'to')):
                if info and info.get(src):
                    if dt.get(fld) != info[src]:
                        dt[fld] = info[src]; relabelled += 1
                elif STREETY.search(dt.get(fld) or ''):
                    dt[fld] = 'London'; relabelled += 1
            tr = tracks_by_id.get(tid) if tid else None
            if tr and (len(tr['trip']) >= 2 or len(tr['enroute']) >= 2):
                dt['trip_track'] = tr['trip']
                dt['enroute_track'] = tr['enroute']
                dt['has_gps_track'] = True
                dt['pickup_pos'] = (tr['trip'] or tr['enroute'])[0]
                dt['dropoff_pos'] = (tr['trip'] or tr['enroute'])[-1]
                assigned += 1
            else:
                dt['trip_track'] = []; dt['enroute_track'] = []
                dt['has_gps_track'] = False
                dt['pickup_pos'] = None; dt['dropoff_pos'] = None
                flagged += 1
    blob = json.dumps(W, separators=(',', ':'))
    s = s[:a] + blob + s[end:]
    open(p, 'w', encoding='utf-8').write(s)
    print(f'dashboard: {assigned} trips with tracks, {flagged} flagged no_gps, '
          f'{relabelled} labels reduced; {os.path.getsize(p)/1024:.0f} KB')

main()
