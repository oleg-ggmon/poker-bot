"""Out-of-fold check: 5 folds by round, so every row is predicted by a net that never saw its round."""
import numpy as np, sys
sys.argv = sys.argv[:1]
import importlib.util, os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "train.py")).read().split('if "--final"')[0]
exec(src)
rounds = np.unique(rnd)
oof = np.zeros(len(y)); oof_me = np.zeros(len(y))
Xm = np.hstack([X, M[:, 7:8]])           # extra input: the bettor is our bot
for k in range(5):
    te_r = rounds[k::5]
    te = np.isin(rnd, te_r)
    oof[te] = predict(fit(X[~te], y[~te], [16, 8], 14, 0)[0], X[te])
    oof_me[te] = predict(fit(Xm[~te], y[~te], [16, 8], 14, 0)[0], Xm[te])
np.save("oof.npy", np.vstack([oof, oof_me]))
used = M[:, 6] == 1; mine = used & (M[:, 7] == 1)
v5 = v5_used(M)
print("out-of-fold log loss, all 50 rounds")
for label, m in (("all rows", np.ones(len(y), bool)), ("heads-up first bet", used), ("heads-up first bet by others", used & ~mine), ("heads-up first bet by us", mine)):
    print("  %-30s n %5d  v5 as used %.4f  net %.4f  net+ours flag %.4f" % (label, m.sum(), ll(v5[m], y[m]), ll(oof[m], y[m]), ll(oof_me[m], y[m])))
print("our bets by size bucket: n, actual fold, v5, net, net+flag")
for kb in range(4):
    k = mine & (M[:, 3] == kb)
    print("  %d  n %4d  actual %.3f  v5 %.3f  net %.3f  net+flag %.3f" % (kb, k.sum(), y[k].mean(), v5[k].mean(), oof[k].mean(), oof_me[k].mean()))
print("others' bets by size bucket")
for kb in range(4):
    k = used & ~mine & (M[:, 3] == kb)
    print("  %d  n %4d  actual %.3f  v5 %.3f  net %.3f" % (kb, k.sum(), y[k].mean(), v5[k].mean(), oof[k].mean()))
print("our bets by version era (rounds): n, actual, v5, net, net+flag")
for a, b in ((2, 23), (24, 48), (49, 51)):
    k = mine & (rnd >= a) & (rnd <= b)
    print("  r%03d-r%03d n %4d actual %.3f v5 %.3f net %.3f flag %.3f" % (a, b, k.sum(), y[k].mean(), v5[k].mean(), oof[k].mean(), oof_me[k].mean()))
for name, p in (("net", oof), ("net+flag", oof_me), ("v5", v5)):
    qs = np.quantile(p[mine], [0, .25, .5, .75, 1])
    print("calibration on our bets,", name, ":", "  ".join("%.2f->%.2f(%d)" % (p[mine & (p >= a) & (p <= b)].mean(), y[mine & (p >= a) & (p <= b)].mean(), (mine & (p >= a) & (p <= b)).sum()) for a, b in zip(qs, qs[1:])))
