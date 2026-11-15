"""Train and test the fold-probability net against v5's fold-rate table.

    python3 train.py            # held-out test: train r002-r041, test r042-r051
    python3 train.py --final    # retrain on every round and write weights.json
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
d = np.load(os.path.join(HERE, "data.npz"))
X, Y, M = d["X"].astype(np.float64), d["y"], d["meta"]
y = (Y == 0).astype(np.float64)
rnd = M[:, 0]


def ll(p, t):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-(t * np.log(p) + (1 - t) * np.log(1 - p)).mean())


def fit(Xa, ya, hidden, epochs, seed, wd=1e-3, lr=3e-3, Xv=None, yv=None):
    rng = np.random.default_rng(seed)
    mu, sd = Xa.mean(0), Xa.std(0) + 1e-6
    A = (Xa - mu) / sd
    dims = [A.shape[1]] + list(hidden) + [1]
    W = [rng.normal(0, np.sqrt(2.0 / a), (a, b)) for a, b in zip(dims, dims[1:])]
    B = [np.zeros(b) for b in dims[1:]]
    mW = [np.zeros_like(w) for w in W]; vW = [np.zeros_like(w) for w in W]
    mB = [np.zeros_like(b) for b in B]; vB = [np.zeros_like(b) for b in B]
    t = 0; best = (9, None, 0); hist = []
    for ep in range(epochs):
        idx = rng.permutation(len(A))
        for i in range(0, len(A), 256):
            b = idx[i:i + 256]
            hs = [A[b]]
            for k in range(len(W)):
                z = hs[-1] @ W[k] + B[k]
                hs.append(np.maximum(z, 0) if k < len(W) - 1 else z)
            p = 1 / (1 + np.exp(-hs[-1][:, 0]))
            g = ((p - ya[b]) / len(b))[:, None]
            t += 1
            for k in range(len(W) - 1, -1, -1):
                gw = hs[k].T @ g + wd * W[k]; gb = g.sum(0)
                if k:
                    g = (g @ W[k].T) * (hs[k] > 0)
                for P_, G, m, v in ((W, gw, mW, vW), (B, gb, mB, vB)):
                    m[k] = 0.9 * m[k] + 0.1 * G; v[k] = 0.999 * v[k] + 0.001 * G * G
                    P_[k] -= lr * (m[k] / (1 - 0.9 ** t)) / (np.sqrt(v[k] / (1 - 0.999 ** t)) + 1e-8)
        if Xv is not None:
            l = ll(predict((mu, sd, W, B), Xv), yv); hist.append(l)
            if l < best[0]:
                best = (l, ([w.copy() for w in W], [b.copy() for b in B]), ep + 1)
    if Xv is not None:
        return (mu, sd, best[1][0], best[1][1]), best[2]
    return (mu, sd, W, B), epochs


def predict(model, Xa):
    mu, sd, W, B = model
    h = (Xa - mu) / sd
    for k in range(len(W)):
        h = h @ W[k] + B[k]
        if k < len(W) - 1:
            h = np.maximum(h, 0)
    return 1 / (1 + np.exp(-h[:, 0]))


def v5_used(M):
    """v5's number as it is used when betting: table estimate x 0.72 when the bettor is first to act on flop/turn."""
    f = M[:, 5].copy()
    f[(M[:, 8] == 1) & (M[:, 9] < 2)] *= 0.72
    return f


def report(name, p, t, mask):
    out = []
    for label, m in mask:
        out.append("%s %.4f" % (label, ll(p[m], t[m])))
    print("%-28s" % name, "  ".join(out))


if "--final" in sys.argv:
    hidden = json.loads(sys.argv[sys.argv.index("--final") + 1])
    ep = int(sys.argv[sys.argv.index("--final") + 2])
    models = [fit(X, y, hidden, ep, s)[0] for s in range(1)]
    mu, sd, W, B = models[0]
    json.dump({"mu": mu.tolist(), "sd": sd.tolist(), "W": [w.tolist() for w in W], "B": [b.tolist() for b in B],
               "hidden": hidden, "epochs": ep, "rows": int(len(y))}, open(os.path.join(HERE, "weights.json"), "w"))
    print("wrote weights.json", "params", sum(w.size for w in W) + sum(b.size for b in B), "train logloss", ll(predict(models[0], X), y))
    sys.exit()

tr = rnd <= 36; va = (rnd > 36) & (rnd <= 41); te = rnd > 41
print("rows train/val/test", tr.sum(), va.sum(), te.sum(), " fold rate test %.3f" % y[te].mean())
used = M[:, 6] == 1
masks = [("all", te), ("heads-up first bet", te & used), ("...bettor first to act", te & used & (M[:, 8] == 1) & (M[:, 9] < 2)), ("...vs our bets", te & used & (M[:, 7] == 1))]
print("test rows:", "  ".join("%s %d" % (l, m.sum()) for l, m in masks))
print("log loss on r042-r051 (lower is better)")
report("constant (train fold rate)", np.full(len(y), y[tr | va].mean()), y, masks)
report("v5 table (fold_at)", M[:, 5], y, masks)
report("v5 as used (x0.72 oop)", v5_used(M), y, masks)
res = {}
for hidden in ([], [8], [16, 8], [32, 16]):
    ps = []; eps = []
    for seed in range(5):
        m, ep = fit(X[tr], y[tr], hidden, 40, seed, Xv=X[va], yv=y[va])
        eps.append(ep)
        m2, _ = fit(X[tr | va], y[tr | va], hidden, max(3, int(np.median(eps))), seed)
        ps.append(predict(m2, X))
    one = ps[0]; avg = np.mean(ps, 0)
    npar = sum(a * b + b for a, b in zip([X.shape[1]] + hidden, hidden + [1]))
    report("net %s %dp (1 seed)" % (hidden, npar), one, y, masks)
    report("net %s (5-seed avg)" % hidden, avg, y, masks)
    print("   seeds logloss all:", " ".join("%.4f" % ll(p[te], y[te]) for p in ps), " epochs", eps)
    res[str(hidden)] = one
np.save(os.path.join(HERE, "test_pred.npy"), res["[16, 8]"])
# calibration of v5-as-used vs net on the subset the bot uses
m = te & used
for name, p in (("v5 as used", v5_used(M)), ("net [16, 8]", res["[16, 8]"])):
    print("calibration,", name, "(heads-up first bet): predicted -> actual (n)")
    qs = np.quantile(p[m], [0, .2, .4, .6, .8, 1])
    for a, b in zip(qs, qs[1:]):
        k = m & (p >= a) & (p <= b)
        print("   %.2f-%.2f  pred %.3f  actual %.3f  (%d)" % (a, b, p[k].mean(), y[k].mean(), k.sum()))
for kb in range(4):
    k = m & (M[:, 3] == kb)
    print("size bucket %d: n %d actual %.3f  v5 %.3f  net %.3f" % (kb, k.sum(), y[k].mean(), v5_used(M)[k].mean(), res["[16, 8]"][k].mean()))
