# -*- coding: utf-8 -*-
"""Consolidate real data from the five ride-share tool projects into docs/data/.

Sources (read-only, from the project share):
  uber/            portal sync      -> weekly trips + earnings
  uber_screen/     metrics pipeline -> CNHR weekly metrics + route GeoJSON (from generated maps)
  uber_surge/      Sentinel daemon  -> one captured live snapshot
  uber_charging/   invoice parser   -> charging session aggregates

Privacy: passenger names are removed and street addresses truncated to
area level before anything is written to docs/.
"""
import json, glob, os, re, sys

BASE = '//R7000/bt2/Projects/uber'
OUT = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
os.makedirs(OUT, exist_ok=True)

def write(name, obj):
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, separators=(',', ':'))
    print(f'{name:18s} {os.path.getsize(path)/1024:8.1f} KB')

# ---------------------------------------------------------------- trips
weeks = []
for f in sorted(glob.glob(BASE + '/uber/report/trips/week_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    weeks.append({'week': d.get('weekStartISO'), 'label': d.get('weekLabel'),
                  'trips': d.get('totalActivities', 0),
                  'earnings': round(d.get('totalEarnings', 0) or 0, 2)})
write('trips.json', {'weekly': weeks,
                     'total_activities': sum(w['trips'] for w in weeks),
                     'total_earnings': round(sum(w['earnings'] for w in weeks), 2)})

# ---------------------------------------------------------------- CNHR metrics
mets, constants = [], {}
for f in sorted(glob.glob(BASE + '/uber_screen/reports/metrics/week_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    constants = d.get('constants', constants)
    w = d.get('weekly', {})
    mets.append({'week': d.get('week_start'), 'label': d.get('week_label'),
                 'trips': w.get('total_trips'), 'earnings': round(w.get('total_e', 0), 2),
                 'hours': round(w.get('total_h', 0), 1),
                 'cnhr': round(w.get('final_r_n', 0), 2), 'state': w.get('final_state')})
write('metrics.json', {'weekly': mets, 'constants': constants})

# ---------------------------------------------------------------- routes
# The uber_screen pipeline generates one Leaflet map per driving day with an
# embedded GeoJSON FeatureCollection (segments with distance / duration /
# speed / earnings). Extract, sanitise, thin, and merge them.
def extract_geojson(path):
    src = open(path, encoding='utf-8', errors='ignore').read()
    i = src.find('"features"')
    if i < 0:
        return None
    j = src.rfind('{', 0, i)
    depth = 0
    for k in range(j, len(src)):
        c = src[k]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return json.loads(src[j:k + 1])
    return None

AREA_RE = re.compile(r'([A-Z]{1,2}[0-9][0-9A-Z]?)\s*[0-9][A-Z]{2}$')  # outward code of a UK postcode
def area(addr):
    """Reduce a full address to 'Locality OUTCODE' — enough to see coverage, not a doorstep."""
    if not addr:
        return ''
    m = AREA_RE.search(addr.strip())
    out = m.group(1) if m else ''
    parts = [p.strip() for p in addr.split(',')]
    loc = parts[-2] if len(parts) >= 2 else (parts[0] if parts else '')
    loc = re.sub(r'\b[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9]?[A-Z]{0,2}\b', '', loc).strip() or 'London'
    return f'{loc} {out}'.strip()

# NOTE: routes.json is NOT built here anymore. The daily-map GeoJSON is incomplete
# (it misses whole GPS weeks and the 11/13 Feb polyline-format days). routes.json is
# now produced by scripts/build_routes_from_gpx.py, which re-extracts every trip's
# route directly from the raw GPX tracker logs. Run that script for routes; this one
# only builds trips/metrics/charging. The extract_geojson/area helpers above
# are retained for reference.

# ---------------------------------------------------------------- charging
d = json.load(open(BASE + '/uber_charging/report/charging_report.json', encoding='utf-8'))
gt = d['grand_totals']
write('charging.json', {
    'period': [d['report_metadata']['period_start'], d['report_metadata']['period_end']],
    'sessions': gt['total_sessions'], 'kwh': round(gt['total_energy_kwh'], 1),
    'cost': gt['total_charging_cost'], 'avg_cost_kwh': gt['avg_cost_per_kwh_incl_vat'],
    'per_week_cost': gt['avg_cost_per_week'],
    'providers': {k: {'sessions': v['sessions'], 'kwh': round(v['total_kwh'], 1),
                      'cost': round(v['total_charging_cost'], 2)}
                  for k, v in d['by_provider'].items()},
    'by_week': {k: {'kwh': round(v['total_kwh'], 1), 'cost': round(v['total_cost'], 2)}
                for k, v in d['by_week'].items()},
    'by_time': {k: {'sessions': v['sessions'], 'kwh': round(v['total_kwh'], 1)}
                for k, v in d['by_time_of_day'].items()}})

print('done.')
