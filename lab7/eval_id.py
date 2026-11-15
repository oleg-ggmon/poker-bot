"""Seat identification on real rounds, with profiles built WITHOUT the round being tested."""
import os, pickle, sys
from common import *
import build7
recs = pickle.load(open('recs.pkl', 'rb'))
CK = [20, 50, 100, 200, 400, 1000]
mode = sys.argv[1] if len(sys.argv) > 1 else 'table'   # table: only the teams actually seated are allowed; open: any Sunday team
tot = {c: [0, 0, 0] for c in CK}   # right, wrong, none
perteam = {}
last_regime = {}
for r in recs: last_regime.setdefault(r['team'], set())
for rn, d in rounds():
    if rn < 26: continue
    T = build7.teams(recs, exclude_round=rn, names=SUNDAY)
    build7.inject('tpl.py', '/tmp/cv.py', T, TABLE_D)
    mod = load('/tmp/cv.py', 'cv%d' % rn)
    P = d['players']; n = len(P); me = d['seat']
    ag = mod.Agent(); ag.on_table_start({'seat': me, 'num_players': n, 'hands': 1000})
    names = [t[0] for t in mod.TEAMS]
    ag.allowed = set(i for i, t in enumerate(names) if t in P) if mode == 'table' else None
    for kind, x, ev, h, _ in hand_iter(d):
        if kind != 'end': continue
        ag.on_hand_end(x)
        if x['hand_number'] in CK:
            for s in range(n):
                if s == me or P[s] not in names: continue
                tid = ag.opp[s].tid
                k = 0 if (tid > 0 and names[tid] == P[s]) else (1 if tid > 0 else 2)
                tot[x['hand_number']][k] += 1
                if x['hand_number'] in (100, 1000):
                    perteam.setdefault(P[s], {}).setdefault(x['hand_number'], [0, 0, 0])[k] += 1
print('mode', mode, ' rounds 26+ (profiles exclude the tested round)')
for c in CK:
    r, w, z = tot[c]; print('  after %4d hands: right %3d  wrong %3d  unidentified %3d   (%.0f%% right, %.1f%% wrong)' % (c, r, w, z, 100.0 * r / (r + w + z), 100.0 * w / (r + w + z)))
for tm in TABLE_D + ['Attention Is All In', 'Gherkers', 'The Market Makers', 'FisherMen', 'Equity Engine', 'Kojack']:
    print('  %-24s @100 %s  @1000 %s' % (tm, perteam.get(tm, {}).get(100), perteam.get(tm, {}).get(1000)))
