"""Replay every real round through a bot and record what it knew at each of OUR real decision points."""
import os, pickle, sys
from common import *
bot = sys.argv[1]; out = sys.argv[2]
FAST = '--calib' in sys.argv
mod = load(os.path.abspath(bot), 'dump_bot')
import json
PAR = json.loads(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].startswith('{') else None
rows = []
for rn, d in rounds():
    P = d['players']; n = len(P); me = d['seat']
    ag = mod.Agent(params=PAR); ag.on_table_start({'seat': me, 'num_players': n, 'hands': 1000})
    cap = {}
    oe = ag._equity
    def eq(hole, board, od, deadline, oe=oe, cap=cap):
        v = oe(hole, board, od, deadline + (0.006 if FAST else 0.0)); cap['e'] = v; cap['od'] = list(od); return v
    ag._equity = eq
    ort = ag._range_t
    def rt(s, role, ort=ort, cap=cap):
        v = ort(s, role); cap.setdefault('t', {})[s] = v; return v
    ag._range_t = rt
    seen = {}
    for kind, x, ev, h, inn in hand_iter(d):
        if kind == 'end':
            ag.on_hand_end(x); continue
        st = x; cap.clear()
        if FAST and not (st['street'] != 'preflop' and st['to_call'] > 0 and ev[1] == 'call'): continue
        dec = ag.act(st) or {}
        s, a, amt = ev
        hist = st['history']
        # who made the bet we face / last aggressor this street
        bettor = -1; Lp = 0; lastr_pre = -1
        for e in hist:
            if e['action'] == 'raise':
                if e['street'] == 'preflop': Lp += 1; lastr_pre = e['seat']
                if e['street'] == st['street']: bettor = e['seat']
        live = [j for j in range(n) if j != me and not st['folded'][j]]
        k = seen.get(h['n'], 0); seen[h['n']] = k + 1
        c = mod.cls(mod.CARD[st['hole_cards'][0]], mod.CARD[st['hole_cards'][1]])
        tc = st['to_call']; pot = st['pot']
        rows.append({'round': rn, 'ver': d['round']['version'], 'n': h['n'], 'k': k, 'street': st['street'], 'L': Lp,
                     'pos': (me - st['button']) % n, 'np': n, 'actual': a, 'amt': amt, 'bot': dec.get('action'), 'bot_amt': dec.get('amount'),
                     'tc': tc, 'pot': pot, 'in': inn, 'result': h['results'][me], 'e': cap.get('e'), 'od': cap.get('od'),
                     't': (cap.get('t') or {}).get(bettor), 'p': mod.PCT[c], 'cls': c,
                     'frac': tc / float(pot - tc) if pot > tc and tc > 0 else 0.0, 'nlive': len(live),
                     'bettor': P[bettor] if bettor >= 0 else None, 'live': [P[j] for j in live],
                     'stack': st['stacks'][me], 'mybet': st['bets'][me], 'ip': (len(live) == 1 and ((me - st['button'] - 1) % n) > ((live[0] - st['button'] - 1) % n)), 'lastr_me': (lastr_pre == me), 'hole': ''.join(st['hole_cards']), 'board': ''.join(st['board']),
                     'sd': str(me) in (h.get('showdown') or {}),
                     'btid': ag.opp[bettor].tid if bettor >= 0 else -1,
                     'baf': ag.opp[bettor].af() if bettor >= 0 else None})
pickle.dump(rows, open(out, 'wb'))
print(len(rows), 'decisions')
