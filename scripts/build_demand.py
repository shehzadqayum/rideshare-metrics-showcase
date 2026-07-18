# -*- coding: utf-8 -*-
"""Consolidate all Sentinel demand data into docs/data/demand.json.

Two things:
  1. session  - the continuous polling run logged to sentinel.db (7 Feb 2026,
                ~90 min, network-health sampled every ~5 min) => a time series.
  2. captures - every point-in-time snapshot JSON the daemon saved across days
                (7-16 Feb), each with the full multi-source metric set.
"""
import json, glob, os, re, sqlite3, shutil, tempfile, html
from datetime import datetime

BASE = '//R7000/bt2/Projects/uber/uber_surge/data'
REPORTS = BASE + '/reports'
OUT = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data', 'demand.json')

def clean(t):
    return html.unescape(re.sub(r'\s+', ' ', t or '')).strip()

# ---------------------------------------------------------------- surge forecast (the pipeline's product)
def read_forecast():
    hp = glob.glob(REPORTS + '/*_surge_report.html')
    mp = glob.glob(REPORTS + '/*_surge_dashboard.md')
    if not hp:
        return None
    s = open(hp[0], encoding='utf-8', errors='ignore').read()
    body = s[s.find('</style>'):]
    title = clean(re.search(r'<title>([^<]+)</title>', s).group(1)) if re.search(r'<title>([^<]+)</title>', s) else 'Surge Report'

    # heatmap: 6 category rows x 17 hours (06..22), levels 0..4, DOM order is row-major
    grid = body[body.find('heatmap-grid'):body.find('heatmap-legend')]
    cats = re.findall(r'heatmap-label"[^>]*>([^<]+)<', grid)
    levels = [int(m) for m in re.findall(r'heat-(\d)"', grid)]
    hours = re.findall(r'heatmap-hour"[^>]*>([^<]+)<', body)
    per = len(hours) or 17
    heatmap = [{'cat': clean(cats[i]), 'levels': levels[i * per:(i + 1) * per]} for i in range(len(cats))]

    # priority windows
    windows = []
    strip = lambda x: clean(re.sub(r'<[^>]+>', ' ', x))
    for chunk in body.split('class="surge-card"')[1:]:
        chunk = chunk[:2000]
        rank = re.search(r'rank-(\d)', chunk)
        tit = re.search(r'<h4>(.*?)</h4>', chunk, re.S)
        trig = re.search(r'trigger"[^>]*>(.*?)</div>', chunk, re.S)
        tags = [strip(x) for x in re.findall(r'meta-tag">(.*?)</div>', chunk, re.S)]
        mult = re.search(r'multiplier-value[^"]*"[^>]*>(.*?)</div>', chunk, re.S)
        mcol = re.search(r'mult-(\w+)', chunk)
        if not tit:
            continue
        windows.append({
            'rank': rank.group(1) if rank else '',
            'title': strip(tit.group(1)),
            'trigger': strip(trig.group(1)) if trig else '',
            'tags': [t for t in tags if t],
            'mult': strip(mult.group(1)) if mult else '',
            'mcolor': mcol.group(1) if mcol else 'orange',
        })

    # strategy + conditions from the markdown
    strategy, conditions = [], []
    if mp:
        md = open(mp[0], encoding='utf-8', errors='ignore').read()
        sec = re.search(r'Recommended Shift Plan.*?\n(\|.*?)\n\n', md, re.S)
        if sec:
            for row in re.findall(r'^\|(.+)\|$', sec.group(1), re.M)[2:]:
                c = [clean(x) for x in row.split('|')]
                if len(c) >= 4 and c[0]:
                    strategy.append({'time': c[0], 'location': c[1], 'target': c[2], 'mult': c[3]})
        sec = re.search(r'### Transport Status\s*\n(\|.*?)\n\n', md, re.S)
        if sec:
            for row in re.findall(r'^\|(.+)\|$', sec.group(1), re.M)[2:]:
                c = [clean(x) for x in row.split('|')]
                if len(c) >= 3 and c[0]:
                    conditions.append({'system': c[0], 'status': c[1], 'relevance': c[2]})

    return {'title': title, 'hours': [clean(h) for h in hours], 'heatmap': heatmap,
            'windows': windows, 'strategy': strategy, 'conditions': conditions,
            'report_file': os.path.basename(hp[0])}

# ---------------------------------------------------------------- DB session
def read_session():
    # sqlite over UNC is flaky; copy to a local temp first
    tmp = os.path.join(tempfile.gettempdir(), 'sentinel_ro.db')
    shutil.copy(BASE + '/sentinel.db', tmp)
    con = sqlite3.connect(tmp); cur = con.cursor()
    rows = cur.execute('SELECT observed_at,health_percentage,total_lines,disrupted_lines '
                       'FROM network_health ORDER BY observed_at').fetchall()
    series = [{'t': r[0][11:16], 'health': round(r[1], 1), 'total': r[2], 'disrupted': r[3]} for r in rows]
    agg = {
        'date': rows[0][0][:10],
        'window': [rows[0][0][11:16], rows[-1][0][11:16]],
        'cycles': len(rows),
        'road_locations': cur.execute('SELECT COUNT(DISTINCT location) FROM road_disruptions').fetchone()[0],
        'arrival_stations': cur.execute('SELECT COUNT(DISTINCT naptan_id) FROM arrivals').fetchone()[0],
        'arrival_events': cur.execute('SELECT SUM(arrival_count) FROM arrivals').fetchone()[0],
        'lines_monitored': cur.execute('SELECT COUNT(DISTINCT line_id) FROM line_status').fetchone()[0],
        'series': series,
    }
    con.close()
    return agg

# ---------------------------------------------------------------- snapshots
def data(x):
    return x.get('data') if isinstance(x, dict) else None

def near_term(cap_date, fx_date, days=3):
    """True if the fixture date is within `days` on/after the capture date."""
    if not cap_date or not fx_date:
        return False
    try:
        c = datetime.strptime(cap_date[:10], '%Y-%m-%d')
        f = datetime.strptime(fx_date[:10], '%Y-%m-%d')
    except Exception:
        return False
    return 0 <= (f - c).days <= days

def dedupe_fixtures(matches):
    seen, out = set(), []
    for m in sorted(matches, key=lambda x: (x.get('date') or '', x.get('kickoff') or '')):
        key = (m.get('home_team'), m.get('away_team'), m.get('date'))
        if key in seen:
            continue
        seen.add(key)
        out.append({'home': m.get('home_team'), 'away': m.get('away_team'), 'comp': m.get('competition'),
                    'venue': m.get('venue'), 'date': m.get('date'), 'kickoff': m.get('kickoff')})
    return out[:10]

def dedupe_events(events):
    seen, out = set(), []
    for e in events:
        key = (e.get('name'), e.get('venue'))
        if key in seen:
            continue
        seen.add(key)
        out.append({'name': e.get('name'), 'venue': e.get('venue'), 'cap': e.get('capacity'), 'start': e.get('start')})
    return out[:8]

def read_capture(path):
    d = json.load(open(path, encoding='utf-8'))
    ts = d.get('timestamp', '')
    src = d.get('sources', {}); tfl = src.get('tfl', {})
    def t(ep): return data(tfl.get(ep, {})) or {}
    ls = t('line_status')
    lines = []
    for l in ls.get('lines', []):
        sts = l.get('lineStatuses') or []
        lines.append({'name': l.get('name'), 'mode': l.get('modeName'),
                      'status': sts[0].get('statusSeverityDescription', 'Good Service') if sts else 'Good Service',
                      'reason': ((sts[0].get('reason') or '')[:200]) if sts else ''})
    rd, sd, ma = t('road_disruptions'), t('station_disruptions'), t('mode_arrivals')
    ld, bo, ev, aq, cp = t('line_disruptions'), t('bike_occupancy'), t('charge_connectors'), t('air_quality'), t('car_parks')

    # aviation (airlabs)
    al = src.get('airlabs') or {}
    sa = data(al.get('schedules_arrivals', {})) or {}
    dl = data(al.get('delays', {})) or {}
    sf = sa.get('surge_forecast') or {}
    aviation = None
    if sa or dl:
        aviation = {
            'arrivals': (sa.get('summary') or {}).get('total_arrivals'),
            'international': (sa.get('summary') or {}).get('international'),
            'domestic': (sa.get('summary') or {}).get('domestic'),
            'surge_rating': sf.get('overall_rating'),
            'peaks': [{'hour': p.get('hour'), 'total': p.get('total'), 'rating': p.get('rating')}
                      for p in (sf.get('upcoming_peaks') or [])[:4]],
            'delays': (dl.get('summary') or {}).get('total_delays'),
            'cancellations': (dl.get('summary') or {}).get('total_cancellations'),
        }

    # national rail
    nr = src.get('national_rail') or {}
    db = (data(nr.get('departure_board', {})) or {}).get('summary') or {}
    inc = (data(nr.get('kb_incidents', {})) or {}).get('summary') or {}
    rail = None
    if db or inc:
        rail = {'services': db.get('total_services'), 'on_time': db.get('on_time'),
                'delayed': db.get('delayed'), 'cancelled': db.get('cancelled'),
                'avg_delay': db.get('avg_delay_mins'), 'incidents': inc.get('total_active')}

    fb = data((src.get('football') or {}).get('fixtures', {})) or {}
    tm = data((src.get('ticketmaster') or {}).get('events', {})) or {}
    cur = (data((src.get('metoffice') or {}).get('hourly', {})) or {}).get('current') or {}
    weather = None
    if cur:
        weather = {k: cur.get(k) for k in ('temperature', 'feels_like', 'humidity', 'wind_speed',
                                           'precipitation_prob', 'uv_index', 'visibility')}
        weather['desc'] = cur.get('weather_code') or cur.get('description')

    # road-disruption points (real coords) for this capture's heatmap
    road = []
    for x in (rd.get('disruptions') or []):
        pt = x.get('point')
        if isinstance(pt, str):
            m = re.findall(r'-?\d+\.\d+', pt)
            pt = [float(m[0]), float(m[1])] if len(m) >= 2 else None
        if isinstance(pt, list) and len(pt) == 2:
            road.append([round(pt[1], 4), round(pt[0], 4), SEV_W.get(x.get('severity'), 0.28)])

    # demand-hotspot markers for this capture: football venues (near-term only) + (if aviation) airports
    cap_date = ts[:10]
    hotspots, fseen = [], set()
    for m in (fb.get('london_matches') or []):
        a = m.get('area')
        if a not in GEO or not near_term(cap_date, m.get('date')):
            continue
        key = (m.get('venue'), m.get('date'))
        if key in fseen:
            continue
        fseen.add(key)
        when = (m.get('date') or '') + (' ' + m.get('kickoff') if m.get('kickoff') else '')
        hotspots.append({'name': m.get('venue') or m.get('home_team'), 'lat': GEO[a][0], 'lon': GEO[a][1],
                         'weight': 0.7, 'type': 'fixture',
                         'detail': f"{m.get('home_team')} v {m.get('away_team')} · {when.strip()}"})
    if aviation:
        for ap in ('LHR', 'LGW', 'LCY', 'STN', 'LTN'):
            hotspots.append({'name': AIRPORT_NAME[ap] + ' Airport', 'lat': GEO[ap][0], 'lon': GEO[ap][1],
                             'weight': 0.85 if ap in ('LHR', 'LGW') else 0.55, 'type': 'airport',
                             'detail': 'International arrivals'})

    # national rail termini markers — per-station live punctuality + advisory
    rail_stations = []
    nr_st = (data((src.get('national_rail') or {}).get('departure_board', {})) or {}).get('stations') or {}
    for crs, info in (nr_st.items() if isinstance(nr_st, dict) else []):
        if crs not in RAIL_GEO:
            continue
        svcs = info.get('services') or []
        cancelled = sum(1 for s in svcs if s.get('is_cancelled') or s.get('etd') == 'Cancelled')
        ontime = sum(1 for s in svcs if s.get('etd') == 'On time')
        delayed = len(svcs) - ontime - cancelled
        nxt = svcs[0] if svcs else None
        msgs = [clean(re.sub(r'<[^>]+>', ' ', m)) for m in (info.get('nrcc_messages') or []) if m.strip()]
        rail_stations.append({'name': RAIL_GEO[crs][2], 'lat': RAIL_GEO[crs][0], 'lon': RAIL_GEO[crs][1],
                              'total': len(svcs), 'ontime': ontime, 'delayed': delayed, 'cancelled': cancelled,
                              'next': (f"{nxt.get('std','')} → {nxt.get('destination','')}" if nxt else ''),
                              'msg': (msgs[0][:150] if msgs else '')})

    # road-disruption markers (Serious + Moderate only, to stay legible) with hover detail
    road_markers = []
    for x in (rd.get('disruptions') or []):
        if x.get('severity') not in ('Serious', 'Severe', 'Moderate'):
            continue
        pt = x.get('point')
        if isinstance(pt, str):
            mm = re.findall(r'-?\d+\.\d+', pt)
            pt = [float(mm[0]), float(mm[1])] if len(mm) >= 2 else None
        if isinstance(pt, list) and len(pt) == 2:
            road_markers.append({'lat': round(pt[1], 4), 'lon': round(pt[0], 4),
                                 'sev': x.get('severity'), 'cat': x.get('category') or 'Disruption',
                                 'loc': (x.get('location') or '')[:80], 'note': (x.get('comments') or '')[:160]})

    return {
        'ts': ts, 'date': ts[:10], 'time': ts[11:16], 'sources': list(src.keys()),
        'road_points': road, 'hotspots': hotspots, 'rail_stations': rail_stations, 'road_markers': road_markers,
        # headline (kept for the demand overview)
        'health': ls.get('network_health_pct'), 'disrupted': ls.get('disrupted_lines'), 'total': ls.get('total_lines'),
        'road': rd.get('total'), 'station': sd.get('total'), 'closures': sd.get('closure_count'),
        'arrivals': ma.get('total_arrivals'), 'arrival_stations': ma.get('total_stations'),
        'football_total': fb.get('total_matches'), 'football_london': len(fb.get('london_matches') or []),
        'events': tm.get('total'), 'temp': cur.get('temperature'), 'lines': lines,
        # full detail (for the per-day snapshots page)
        'road_by_severity': {k: (len(v) if isinstance(v, list) else v) for k, v in (rd.get('by_severity') or {}).items()},
        'line_disruptions': [{'line': v.get('line_name'), 'status': v.get('status'), 'reason': (v.get('reason') or '')[:200]}
                             for v in (ld.get('by_line') or {}).values()],
        'bikes': {'bikes': bo.get('total_bikes'), 'docks': bo.get('total_docks'), 'pct': bo.get('availability_pct')} if bo else None,
        'ev': {'total': ev.get('total'), 'available': ev.get('available'), 'pct': ev.get('availability_pct')} if ev and not ev.get('is_outage') else None,
        'air': {'index': aq.get('index'), 'summary': aq.get('summary')} if aq and not aq.get('is_outage') else None,
        'car_parks_outage': bool(cp.get('is_outage')),
        'aviation': aviation, 'rail': rail, 'weather': weather,
        'football_list': dedupe_fixtures([m for m in (fb.get('london_matches') or []) if near_term(ts[:10], m.get('date'))]),
        'events_next6': dedupe_events(tm.get('next_6_hours') or []),
        'events_by_type': {k: (len(v) if isinstance(v, list) else v) for k, v in (tm.get('by_type') or {}).items()},
        'road_serious': [{'location': x.get('location'), 'category': x.get('category'),
                          'comments': (x.get('comments') or '')[:150]}
                         for x in ((rd.get('by_severity', {}) or {}).get('Serious') or [])[:5]],
    }

SNAPS = ['20260207T0512-tfl.json', '20260207T0820-tfl.json', '20260208T0656-tfl.json',
         'full_report_20260209_184034.json', 'full_report.json', 'live.json']

# approximate centroids (lat, lon) for the London postcode districts / airports in the data
GEO = {
    'TW6': (51.470, -0.453), 'TW8': (51.494, -0.297), 'SW6': (51.475, -0.196), 'E16': (51.508, 0.021),
    'E20': (51.539, -0.016), 'SE25': (51.398, -0.078), 'SE16': (51.494, -0.052), 'N17': (51.603, -0.066),
    'HA9': (51.556, -0.279), 'WC2': (51.513, -0.122), 'W1': (51.515, -0.141), 'SE10': (51.483, 0.005),
    'SE1': (51.501, -0.090), 'N1': (51.538, -0.103), 'NW1': (51.535, -0.143), 'EC2': (51.518, -0.083),
    'LHR': (51.470, -0.454), 'LGW': (51.154, -0.182), 'STN': (51.885, 0.235), 'LCY': (51.505, 0.055),
    'LTN': (51.875, -0.368),
}
AIRPORT_NAME = {'LHR': 'Heathrow', 'LGW': 'Gatwick', 'STN': 'Stansted', 'LCY': 'London City', 'LTN': 'Luton'}
SEV_W = {'Serious': 1.0, 'Severe': 1.0, 'Moderate': 0.55, 'Minimal': 0.28}
# major London rail termini (CRS -> lat, lon) — the 10 stations the daemon polls
RAIL_GEO = {
    'LST': (51.5178, -0.0823, 'Liverpool Street'), 'KGX': (51.5308, -0.1238, "King's Cross"),
    'STP': (51.5299, -0.1263, 'St Pancras'), 'WAT': (51.5033, -0.1132, 'Waterloo'),
    'VIC': (51.4952, -0.1441, 'Victoria'), 'PAD': (51.5154, -0.1755, 'Paddington'),
    'EUS': (51.5282, -0.1337, 'Euston'), 'LBG': (51.5049, -0.0865, 'London Bridge'),
    'SRA': (51.5416, -0.0042, 'Stratford'), 'FST': (51.5203, -0.1053, 'Farringdon'),
}

def build_geo(fc, caps):
    hotspots = []
    # priority surge windows (weight by multiplier)
    for w in (fc or {}).get('windows', []):
        area = None
        for t in w.get('tags', []):
            m = re.match(r'\s*([A-Z]{1,2}\d{1,2})\b', t)
            if m and m.group(1) in GEO:
                area = m.group(1); loc = t; break
        else:
            loc = ''
        if area:
            mult = 0
            mm = re.search(r'([\d.]+)', w.get('mult', ''))
            if mm:
                mult = float(mm.group(1))
            hotspots.append({'name': w['title'], 'lat': GEO[area][0], 'lon': GEO[area][1],
                             'weight': round(min(1.0, mult / 2.5), 2), 'type': 'surge',
                             'detail': f"{loc} · {w.get('mult','')} surge"})
    # airports (from the aviation surge_forecast if present, else all five)
    airports = set()
    for c in caps:
        if c.get('aviation'):
            airports |= {'LHR', 'LGW', 'STN', 'LCY', 'LTN'}
    for a in (airports or {'LHR', 'LGW', 'LCY'}):
        hotspots.append({'name': AIRPORT_NAME[a] + ' Airport', 'lat': GEO[a][0], 'lon': GEO[a][1],
                         'weight': 0.7 if a in ('LHR', 'LGW') else 0.5, 'type': 'airport',
                         'detail': 'International arrivals'})
    # football fixtures from the richest capture (venue + area)
    rich = max(caps, key=lambda c: len(c.get('football_list', [])), default=None)
    seen = set()
    if rich:
        for f in rich.get('football_list', []):
            # area comes from the source; look it up in the fixture text isn't available here, so map by known venue postcodes
            pass
    # fixtures need area codes -> pull from live snapshot football venues
    for f in (fc_fixtures() or []):
        if f['area'] in GEO and f['venue'] not in seen:
            seen.add(f['venue'])
            hotspots.append({'name': f['venue'], 'lat': GEO[f['area']][0], 'lon': GEO[f['area']][1],
                             'weight': 0.6, 'type': 'fixture', 'detail': f"{f['home']} — football egress"})
    # road-disruption points (real coords) from the richest capture that has them
    road = []
    src = None
    for fn in ('live.json', 'full_report.json', 'full_report_20260209_184034.json'):
        p = BASE + '/' + fn
        if os.path.exists(p):
            src = fn
            d = json.load(open(p, encoding='utf-8'))
            for x in (data((d.get('sources', {}).get('tfl') or {}).get('road_disruptions', {})) or {}).get('disruptions', []):
                pt = x.get('point')
                if isinstance(pt, str):
                    m = re.findall(r'-?\d+\.\d+', pt)   # "[lon,lat]" as a string
                    pt = [float(m[0]), float(m[1])] if len(m) >= 2 else None
                if isinstance(pt, list) and len(pt) == 2:
                    road.append([round(pt[1], 4), round(pt[0], 4), SEV_W.get(x.get('severity'), 0.28)])
            break
    return {'hotspots': hotspots, 'road': road, 'road_src': src}

def fc_fixtures():
    """London football fixtures with venue + area, from the richest live snapshot."""
    for fn in ('live.json', 'full_report.json', 'full_report_20260209_184034.json'):
        p = BASE + '/' + fn
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding='utf-8'))
        fb = data((d.get('sources', {}).get('football') or {}).get('fixtures', {})) or {}
        out = [{'venue': m.get('venue'), 'area': m.get('area'), 'home': m.get('home_team')}
               for m in (fb.get('london_matches') or []) if m.get('area')]
        if out:
            return out
    return []

def main():
    caps = []
    for fn in SNAPS:
        p = BASE + '/' + fn
        if os.path.exists(p):
            try:
                caps.append(read_capture(p))
            except Exception as e:
                print('skip', fn, e)
    caps.sort(key=lambda c: c['ts'])
    fc = read_forecast()
    out = {'forecast': fc, 'session': read_session(), 'captures': caps}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print(f'demand.json: {os.path.getsize(OUT)/1024:.0f} KB')
    if fc:
        print(f"  forecast: {len(fc['heatmap'])} cats x {len(fc['hours'])} hrs, "
              f"{len(fc['windows'])} windows, {len(fc['strategy'])} strategy rows, {len(fc['conditions'])} conditions")
    print(f"  session: {out['session']['date']} {out['session']['window']} "
          f"{out['session']['cycles']} cycles, {len(out['session']['series'])} points")
    print(f"  captures: {len(caps)} across days {sorted(set(c['date'] for c in caps))}")

main()
