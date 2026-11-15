"""Run the bot's own learning code over every real round with all seats visible; save per (round, team) counters."""
import os, pickle, sys
from common import *
mod = load(os.path.join(HERE, 'tpl.py'), 'tpl')
recs = []
for rn, d in rounds():
    P = d['players']; n = len(P)
    ag = mod.Agent(); ag.on_table_start({'seat': 0, 'num_players': n, 'hands': 1000}); ag.me = -1
    for kind, x, ev, h, _ in hand_iter(d):
        if kind == 'end': ag._learn(x)
    for s in range(n):
        o = ag.opp[s]
        recs.append({'round': rn, 'team': P[s], 'vec': o.vec(), 'so': dict(o.so), 'sb': dict(o.sb), 's3': dict(o.s3), 'hn': o.hn,
                     'res': sum(h['results'][s] for h in d['hands'])})
pickle.dump(recs, open(os.path.join(HERE, 'recs.pkl'), 'wb'))
print(len(recs), 'records')
