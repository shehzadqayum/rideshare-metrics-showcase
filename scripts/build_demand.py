# -*- coding: utf-8 -*-
"""Consolidate all Sentinel demand data into docs/data/demand.json.

Two things:
  1. session  - the continuous polling run logged to sentinel.db (7 Feb 2026,
                ~90 min, network-health sampled every ~5 min) => a time series.
  2. captures - every point-in-time snapshot JSON the daemon saved across days
                (7-16 Feb), each with the full multi-source metric set.
"""
import json, glob, os, re, sqlite3, shutil, tempfile

BASE = '//R7000/bt2/Projects/uber/uber_surge/data'
OUT = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data', 'demand.json')

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

def read_capture(path):
    d = json.load(open(path, encoding='utf-8'))
    src = d.get('sources', {}); tfl = src.get('tfl', {})
    ls = data(tfl.get('line_status', {})) or {}
    lines = []
    for l in ls.get('lines', []):
        sts = l.get('lineStatuses') or []
        lines.append({'name': l.get('name'), 'mode': l.get('modeName'),
                      'status': sts[0].get('statusSeverityDescription', 'Good Service') if sts else 'Good Service',
                      'reason': ((sts[0].get('reason') or '')[:200]) if sts else ''})
    rd = data(tfl.get('road_disruptions', {})) or {}
    sd = data(tfl.get('station_disruptions', {})) or {}
    ma = data(tfl.get('mode_arrivals', {})) or {}
    fb = data((src.get('football') or {}).get('fixtures', {})) or {}
    tm = data((src.get('ticketmaster') or {}).get('events', {})) or {}
    cur = (data((src.get('metoffice') or {}).get('hourly', {})) or {}).get('current') or {}
    ts = d.get('timestamp', '')
    return {
        'ts': ts, 'date': ts[:10], 'time': ts[11:16],
        'sources': list(src.keys()),
        'health': ls.get('network_health_pct'),
        'disrupted': ls.get('disrupted_lines'), 'total': ls.get('total_lines'),
        'road': rd.get('total'),
        'station': sd.get('total'), 'closures': sd.get('closure_count'),
        'arrivals': ma.get('total_arrivals'), 'arrival_stations': ma.get('total_stations'),
        'football_total': fb.get('total_matches'),
        'football_london': len(fb.get('london_matches') or []),
        'events': tm.get('total'),
        'temp': cur.get('temperature'),
        'lines': lines,
        'football_list': [{'home': m.get('home_team'), 'away': m.get('away_team'), 'comp': m.get('competition')}
                          for m in (fb.get('london_matches') or [])[:8]],
        'road_serious': [{'location': x.get('location'), 'category': x.get('category'),
                          'comments': (x.get('comments') or '')[:150]}
                         for x in ((rd.get('by_severity', {}) or {}).get('Serious') or [])[:5]],
    }

SNAPS = ['20260207T0512-tfl.json', '20260207T0820-tfl.json', '20260208T0656-tfl.json',
         'full_report_20260209_184034.json', 'full_report.json', 'live.json']

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
    out = {'session': read_session(), 'captures': caps}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print(f'demand.json: {os.path.getsize(OUT)/1024:.0f} KB')
    print(f"  session: {out['session']['date']} {out['session']['window']} "
          f"{out['session']['cycles']} cycles, {len(out['session']['series'])} points")
    print(f"  captures: {len(caps)} across days {sorted(set(c['date'] for c in caps))}")

main()
