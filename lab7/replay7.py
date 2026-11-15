"""Replay real rounds through a candidate with held-out team profiles and only the seated teams allowed.
Exact effect of the candidate's extra folds (it forfeits what was in; the live bot got the real result)."""
import json, os, pickle, sys
from collections import defaultdict
from common import *
import build7
tpl = sys.argv[1]; par = json.loads(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].startswith('{') else None
lo = int(sys.argv[sys.argv.index('--from') + 1]) if '--from' in sys.argv else 0
noteams = '--noteams' in sys.argv
recs = pickle.load(open(os.path.join(HERE, 'recs.pkl'), 'rb'))
dec = pickle.load(open(os.path.join(HERE, 'decisions.pkl'), 'rb'))
cat = defaultdict(lambda: [0, 0.0]); tot = 0.0; nr = 0; cont = defaultdict(int); other = defaultdict(int); errs = 0; halves = [0.0, 0.0]
for rn, d in rounds():
    if rn < lo: continue
    P = d['players']; n = len(P); me = d['seat']
    if noteams:
        mod = load(tpl, 'rp_nt')
    else:
        T = build7.teams(recs, exclude_round=rn, names=SUNDAY, dec=[r for r in dec if r['round'] != rn])
        build7.inject(tpl, '/tmp/rp.py', T, TABLE_D)
        mod = load('/tmp/rp.py', 'rp%d' % rn)
    ag = mod.Agent(params=par); ag.on_table_start({'seat': me, 'num_players': n, 'hands': 1000})
    if not noteams:
        names = [t[0] for t in mod.TEAMS]; ag.allowed = set(i for i, t in enumerate(names) if t in P)
    seen = set(); nr += 1
    for kind, x, ev, h, inn in hand_iter(d):
        if kind == 'end': ag.on_hand_end(x); continue
        if h['n'] in seen: continue
        dd = ag.act(x) or {}
        b = dd.get('action'); b = 'raise' if b == 'all_in' else b
        a = ev[1]
        if a == b or (a in ('call', 'check') and b in ('call', 'check')): continue
        seen.add(h['n'])
        st = x['street']; tc = x['to_call']; pot = x['pot']
        fr = tc / float(pot - tc) if pot > tc and tc > 0 else 0
        sz = 'small' if fr < 0.45 else ('mid' if fr < 0.75 else ('big' if fr < 1.6 else 'over'))
        if b == 'fold' and a != 'fold':
            eff = -inn - h['results'][me]
            key = (st, a, sz if st != 'preflop' else ('bb' if (me - x['button']) % n == 2 else 'nonbb'))
            cat[key][0] += 1; cat[key][1] += eff; tot += eff; halves[rn % 2] += eff
        elif a == 'fold':
            cont[(st, b, sz if st != 'preflop' else '')] += 1
        else:
            other[(st, a + '->' + str(b))] += 1
    errs += ag.errs
print('rounds %d | errors %d | exact effect of extra folds: %+.0f chips = %+.2f bb/100 (even rounds %+.0f, odd %+.0f)' % (nr, errs, tot, tot / 20.0 / nr / 10.0, halves[0], halves[1]))
for k in sorted(cat, key=lambda k: -abs(cat[k][1])):
    print('   live %-5s -> cand fold  %-8s %-6s n=%4d effect %+8.0f (%+.0f each)' % (k[1], k[0], k[2], cat[k][0], cat[k][1], cat[k][1] / cat[k][0]))
print(' candidate continues where live folded:', dict(sorted(cont.items(), key=lambda kv: -kv[1])[:12]))
print(' other disagreements:', dict(sorted(other.items(), key=lambda kv: -kv[1])[:14]))
