# -*- coding: utf-8 -*-
"""Extract per-week trip data (metrics + GPS tracks) for the generic week page.

Source of truth is the enhanced CNHR dashboard's `var W` blob, which already
carries every trip's metrics, the GPS tracks injected from the GPX logs, and
area-reduced pickup/dropoff labels.
"""
import json, math, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASH = os.path.join(REPO, 'docs', 'dashboards', 'cnhr_dashboard.html')
OUT = os.path.join(REPO, 'docs', 'data', 'weeks.json')

def parse_W(path):
    s = open(path, encoding='utf-8', errors='ignore').read()
    a = s.find('var W=') + 6
    depth = 0; instr = False; esc = False
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
            if depth == 0:
                return json.loads(s[a:k + 1])
    raise SystemExit('could not parse var W')

def hav(a, b):
    R = 3958.8
    dla, dlo = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    x = math.sin(dla / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlo / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))

def track_miles(tr):
    return sum(hav(tr[i], tr[i + 1]) for i in range(len(tr) - 1)) if tr and len(tr) > 1 else 0.0

W = parse_W(DASH)
weeks = []
for w in W:
    gps = [t for t in w.get('trips', []) if t.get('has_gps_track')]
    if not gps:
        continue                      # only weeks that actually have routes
    trips = []
    for t in w['trips']:
        trk = t.get('trip_track') or []
        enr = t.get('enroute_track') or []
        mi = track_miles(trk)
        hrs = float(t.get('t_dur') or 0)
        earn = float(t.get('t_earn') or 0)
        trips.append({
            'n': t.get('n'), 'day': t.get('day'), 'time': t.get('time'),
            'svc': t.get('service'), 'earn': round(earn, 2),
            'mins': round(hrs * 60, 1), 'mi': round(mi, 2),
            'util': round(float(t.get('util') or 0), 3),
            'rho': t.get('rho_paid'), 'rho_true': t.get('rho_true'),
            'mnhr': t.get('mnhr_true'),
            # The four-state test is mnhr_true_ema > r_n (uber_screen engine.py),
            # so the smoothed *true* series has to travel with the state.
            'mnhr_ema': t.get('mnhr_true_ema'),
            'rn': t.get('r_n'),
            'cum_e': t.get('cum_e'), 'cum_h': t.get('cum_h'),
            'rec': t.get('recovery_pct'), 'state': t.get('four_state'),
            'from': t.get('pickup'), 'to': t.get('dropoff'),
            'per_hr': round(earn / hrs, 2) if hrs > 0 else None,
            'per_mi': round(earn / mi, 2) if mi > 0 else None,
            'trip': trk, 'enroute': enr,
            'pu': t.get('pickup_pos'), 'do': t.get('dropoff_pos'),
        })
    # The dashboard's final_mnhr_ema is the *paid* EMA, but final_state is decided
    # by the *true* EMA, so publishing the former next to the state produced weeks
    # that appeared to contradict the framework's own rule. Carry the value the
    # state is actually derived from.
    last = w['trips'][-1] if w.get('trips') else {}
    weeks.append({
        'key': w.get('key'), 'label': w.get('label'),
        'n': w.get('total_n'), 'gps': len(gps),
        'earnings': w.get('total_e'), 'hours': w.get('total_h'),
        'rn': w.get('final_r_n'), 'rho': w.get('final_rho'),
        'mnhr': last.get('mnhr_true_ema'),
        'mnhr_paid_ema': w.get('final_mnhr_ema'),
        'state': w.get('final_state'),
        'be_trip': w.get('be_trip'), 'target_trip': w.get('target_trip'),
        'trips': trips,
    })

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({'weeks': weeks}, open(OUT, 'w'), separators=(',', ':'))
print(f'weeks.json: {os.path.getsize(OUT)/1024:.0f} KB, {len(weeks)} weeks with routes')
for w in weeks:
    print(f"  {w['label']:20s} {w['gps']:>3d}/{w['n']} trips with GPS · £{w['earnings']:.0f} · CNHR £{w['rn']:.2f}")
