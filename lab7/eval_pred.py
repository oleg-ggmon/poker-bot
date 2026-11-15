"""Does knowing the team make the bot's opponent predictions better? Real rounds, held-out profiles.
Log-loss of the predictions the bot uses (lower is better), by how far into the round we are."""
import math, os, pickle, sys
from common import *
import build7
recs = pickle.load(open('recs.pkl', 'rb'))
WS = [0.0, 0.2, 0.4, 0.8, 1.5]
tabfilter = sys.argv[1] if len(sys.argv) > 1 else 'all'
L = {}   # (metric, phase, w) -> [sumloss, n, sum_pred, sum_y]
def note(metric, hn, w, p, y):
    p = min(0.98, max(0.02, p))
    ph = 'h1-150' if hn <= 150 else ('h151-400' if hn <= 400 else 'h401+')
    for key in ((metric, ph, w), (metric, 'all', w)):
        a = L.setdefault(key, [0.0, 0, 0.0, 0.0])
        a[0] += -(math.log(p) if y else math.log(1 - p)); a[1] += 1; a[2] += p; a[3] += y
for rn, d in rounds():
    if rn < 26: continue
    P = d['players']; n = len(P); me = d['seat']
    if tabfilter == 'D' and not any(t in TABLE_D for t in P): continue
    T = build7.teams(recs, exclude_round=rn, names=SUNDAY)
    build7.inject('tpl.py', '/tmp/cv.py', T, TABLE_D)
    mod = load('/tmp/cv.py', 'cvp%d' % rn)
    names = [t[0] for t in mod.TEAMS]
    ags = []
    for w in WS:
        ag = mod.Agent(params={'tp_w': w}); ag.on_table_start({'seat': me, 'num_players': n, 'hands': 1000})
        ag.allowed = set(i for i, t in enumerate(names) if t in P)
        ags.append(ag)
    ok = [P[s] in names and s != me and (tabfilter != 'D' or P[s] in TABLE_D) for s in range(n)]
    for kind, x, ev, h, _ in hand_iter(d):
        if kind != 'end': continue
        hn = x['hand_number']
        bets = [0] * n; pot = 0; cur = 0; street = 'preflop'; Lv = 0; opener = -1; od = False; inpost = set(); bbs = -1
        for e in x['history']:
            s = e['seat']; a = e['action']; amt = e.get('amount') or 0
            if e['street'] != street: street = e['street']; bets = [0] * n; cur = 0
            if a in ('small_blind', 'big_blind'):
                bets[s] = amt; pot += amt; cur = max(cur, amt)
                if a == 'big_blind': bbs = s
                continue
            tc = cur - bets[s]
            if ok[s]:
                for w, ag in zip(WS, ags):
                    o = ag.opp[s]
                    if street == 'preflop':
                        if Lv == 1 and s != opener:
                            note('fold to open (bb)' if s == bbs else 'fold to open', hn, w, o.bbfold() if s == bbs else o.fr(), a == 'fold')
                            note('3bet an open', hn, w, o.t3c(0), a == 'raise')
                        elif Lv == 2 and s == opener and not od:
                            note('fold to 3bet', hn, w, o.f3(), a == 'fold')
                        elif Lv == 0 and tc > 0:
                            pass
                    elif tc > 0:
                        before = pot - tc; fr_ = tc / float(before) if before > 0 else 1.0
                        kb = 0 if fr_ < 0.5 else (1 if fr_ < 0.95 else (2 if fr_ < 1.6 else 3))
                        stg = 1 if s in inpost else 0
                        note('fold to bet', hn, w, o.fold_at(kb, stg, ag.tfb, ag.tfd), a == 'fold')
                        if kb >= 2: note('fold to big bet', hn, w, o.fold_at(kb, stg, ag.tfb, ag.tfd), a == 'fold')
            if street == 'preflop':
                if Lv == 2 and s == opener: od = True
                if a == 'raise':
                    Lv += 1
                    if Lv == 1: opener = s
            elif a in ('raise', 'call'): inpost.add(s)
            if a == 'raise': pot += amt - bets[s]; bets[s] = amt; cur = amt
            elif a == 'call': pot += amt; bets[s] += amt
        for ag in ags: ag.on_hand_end(x)
print('filter', tabfilter, '| log-loss by virtual-history weight (0 = v6 behaviour); n; actual rate')
for metric in ['fold to bet', 'fold to big bet', 'fold to open', 'fold to open (bb)', 'fold to 3bet', '3bet an open']:
    for ph in ['h1-150', 'h151-400', 'h401+', 'all']:
        row = [L.get((metric, ph, w)) for w in WS]
        if not row[0]: continue
        print('  %-18s %-8s n=%6d rate %.2f | ' % (metric, ph, row[0][1], row[0][3] / row[0][1]) + '  '.join('w%.1f %.4f' % (w, r[0] / r[1]) for w, r in zip(WS, row)))
