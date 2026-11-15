"""v5 bot + weights.json -> a bot whose heads-up bet chooser gets its fold chance from the net.

    python3 build_nn.py ../../bot.py ../versions/bot_12_nn.py

The only behaviour change is the fold probability used when we bet first into one opponent.
PARAMS["nn"] = 0 switches the net off and gives v5's numbers back (for A/B runs).
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(sys.argv[1]).read()
w = json.load(open(os.path.join(HERE, "weights.json")))
mu, sd = np.array(w["mu"]), np.array(w["sd"])
W = [np.array(x) for x in w["W"]]
B = [np.array(x) for x in w["B"]]
# fold the input scaling into the first layer so the bot feeds raw features
B[0] = B[0] - (mu / sd) @ W[0]
W[0] = W[0] / sd[:, None]
layers = [[[round(float(v), 4) for v in W[k][:, j]] for j in range(W[k].shape[1])] for k in range(len(W))]
biases = [[round(float(v), 4) for v in b] for b in B]

head = '''
#@NN_START@  fold-probability net, trained by lab/nn (inputs listed in lab/nn/extract.py FEATS)
NN_W = %s
NN_B = %s
#@NN_END@


def nn_fold(x):
    """P(fold) for one opponent facing a bet, from the %d-input feature list x."""
    h = x
    last = len(NN_W) - 1
    for k in range(last):
        h = [v if v > 0.0 else 0.0 for v in [sum(map(_mul, r, h)) + c for r, c in zip(NN_W[k], NN_B[k])]]
    z = sum(map(_mul, NN_W[last][0], h)) + NN_B[last][0]
    if z > 30.0:
        z = 30.0
    elif z < -30.0:
        z = -30.0
    return 1.0 / (1.0 + _exp(-z))


def _lgt(p):
    p = 0.02 if p < 0.02 else (0.98 if p > 0.98 else p)
    return _log(p / (1.0 - p))

''' % (json.dumps(layers), json.dumps(biases), len(mu))

methods = '''
    # ------------------------------------------------------------------ fold net inputs
    def _nnctx(self, st, s1, L, lastr):
        """Inputs of the fold net that do not depend on the bet size, for a first bet into seat s1.

        Mirrors situation() in lab/nn/extract.py, in the same order. Slots 3-7 and 31 are filled per size."""
        me = self.me
        street = st["street"]
        inpost = faced = acted = 0
        mine = set()
        cur = 0
        bets = {}
        strt = "preflop"
        for h in st["history"]:
            hs = h["street"]
            if hs == "preflop":
                continue
            if hs != strt:
                strt = hs
                cur = 0
                bets = {}
            s = h["seat"]
            a = h["action"]
            if s == s1:
                if cur - bets.get(s, 0) > 0:
                    faced += 1
                if hs == street:
                    acted = 1
                if a == "raise" or a == "call":
                    inpost = 1
            if a == "raise":
                if s == me:
                    mine.add(hs)
                bets[s] = cur = h.get("amount") or 0
            elif a == "call":
                bets[s] = bets.get(s, 0) + (h.get("amount") or 0)
        bd = st["board"]
        rs = [RANKS.index(c[0]) for c in bd]
        ss = [c[1] for c in bd]
        fl = max(ss.count(q) for q in SUITS)
        u = set(rs)
        if 12 in u:
            u.add(-1)
        sy = 0
        for lo_ in range(-1, 9):
            k = 0
            for r in range(lo_, lo_ + 5):
                if r in u:
                    k += 1
            if k > sy:
                sy = k
        o = self.opp[s1]
        tb = self.tfb[inpost]
        td = self.tfd[inpost]
        trate = (td[0] + td[1] + td[2] + td[3] + 0.45 * 8.0) / (tb[0] + tb[1] + tb[2] + tb[3] + 8.0)
        nb = len(mine) + 1
        x = [1.0 if street == "flop" else 0.0, 1.0 if street == "turn" else 0.0, 1.0 if street == "river" else 0.0,
             0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, float(inpost), float(faced if faced < 3 else 3),
             1.0 if s1 == lastr else 0.0, 1.0 if me == lastr else 0.0, 0.0, 0.0,
             0.0 if acted else 1.0, float(nb if nb < 3 else 3), float(L if L < 3 else 3),
             1.0 if len(set(rs)) < len(rs) else 0.0, (fl - 1) / 3.0 if fl < 4 else 1.0, max(rs) / 12.0, (sy - 1) / 4.0,
             o.vp(), o.pf(), o.af(), o.ftb(), o.cbig(), o.fr(), o.f3(), _log(o.n + 1.0), 0.0, _lgt(trate)]
        return x, inpost

    def _nnfold(self, nnx, o, b, pot0, stack1):
        """P(seat folds) to a bet of b chips into a pot of pot0, with stack1 chips behind."""
        x, stg = nnx
        fr_ = b / float(pot0) if pot0 > 0 else 1.0
        kb = 0 if fr_ < 0.5 else (1 if fr_ < 0.95 else (2 if fr_ < 1.6 else 3))
        fc = fr_ if fr_ < 3.0 else 3.0
        pot = pot0 + b
        spr = (stack1 - b) / float(pot) if stack1 > b else 0.0
        x[3] = _log(fc + 0.05)
        x[4] = fc
        x[5] = _log(pot / 20.0 + 1.0)
        x[6] = _log(spr + 0.1)
        x[7] = 1.0 if b >= stack1 else 0.0
        x[31] = _lgt(o.fold_at(kb, stg, self.tfb, self.tfd))
        f = nn_fold(x)
        return 0.02 if f < 0.02 else (0.95 if f > 0.95 else f)

    def _range_t(self, s, role):'''


def sub(s, old, new, count=1):
    assert s.count(old) == count, (old, s.count(old))
    return s.replace(old, new)


src = sub(src, "import gc\nimport random\nimport time\n", "import gc\nimport random\nimport time\nfrom math import exp as _exp, log as _log\nfrom operator import mul as _mul\n")
src = sub(src, "#@CONFIG_END@\n", "#@CONFIG_END@\n" + head)
src = sub(src, "\n    def _range_t(self, s, role):", methods)
src = sub(src, '"commit_mult": 1.0}', '"commit_mult": 1.0, "nn": 1}')
src = sub(src, "            best = 0.0\n            bfrac = 0.0\n            for frac, kb in cands:\n",
          "            best = 0.0\n            bfrac = 0.0\n            nnx = self._nnctx(st, s1, L, lastr) if P.get(\"nn\") else None\n            stk1 = st[\"stacks\"][s1]\n            for frac, kb in cands:\n")
old = ("                f = o.fold_at(kb, stg, tfb, tfd) * fm[kb] * fcm\n"
       "                if frac > 3.0 and f > 0.15:\n"
       "                    f = f + 0.10 if f < 0.85 else 0.95\n"
       "                wc = (e - f) / (1.0 - f) if e > f else 0.0\n                if si < 3:\n")
new = ("                if nnx is not None:\n"
       "                    f = self._nnfold(nnx, o, frac * pot, pot, stk1)\n"
       "                else:\n"
       "                    f = o.fold_at(kb, stg, tfb, tfd) * fm[kb] * fcm\n"
       "                    if frac > 3.0 and f > 0.15:\n"
       "                        f = f + 0.10 if f < 0.85 else 0.95\n"
       "                wc = (e - f) / (1.0 - f) if e > f else 0.0\n                if si < 3:\n")
src = sub(src, old, new)
open(sys.argv[2], "w").write(src)
print("wrote", sys.argv[2], len(src), "bytes;", sum(len(r) for l in layers for r in l) + sum(len(b) for b in biases), "net parameters")
