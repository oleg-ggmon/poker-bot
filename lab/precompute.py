"""Offline precompute of preflop tables (run once on a laptop, results get embedded in bot.py).

Outputs tables.json:
  pct[169]      strength percentile of each hand class (0 = best), combo-weighted
  eqr[169][NB]  all-in equity of each class against one opponent holding the top X of hands
"""
import json
import random
import sys
from multiprocessing import Pool

from evalcore import cls, ev

BUCKETS = [0.02, 0.04, 0.07, 0.11, 0.16, 0.23, 0.32, 0.45, 0.65, 1.0]
N_A = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
N_B = int(sys.argv[2]) if len(sys.argv) > 2 else 6000


def rep(c):
    hi, lo = divmod(c, 13)
    if hi == lo:
        return hi * 4, hi * 4 + 1
    if hi > lo:
        return hi * 4, lo * 4
    return lo * 4, hi * 4 + 1


def eq_random(args):
    c, nopp, n, seed = args
    rng = random.Random(seed)
    h = rep(c)
    deck = [x for x in range(52) if x not in h]
    w = 0.0
    for _ in range(n):
        d = rng.sample(deck, 5 + 2 * nopp)
        board = d[:5]
        me = ev([h[0], h[1]] + board)
        best = 0
        ties = 1
        lose = False
        for i in range(nopp):
            o = ev(d[5 + 2 * i:7 + 2 * i] + board)
            if o > me:
                lose = True
                break
            if o == me:
                ties += 1
        if not lose:
            w += 1.0 / ties
    return c, nopp, w / n


def eq_range(args):
    c, combos, n, seed = args
    rng = random.Random(seed)
    h = rep(c)
    deck = [x for x in range(52) if x not in h]
    out = []
    for b in BUCKETS:
        k = max(6, int(round(b * len(combos))))
        pre = [x for x in combos[:k] if x[0] not in h and x[1] not in h]
        w = 0.0
        for _ in range(n):
            o = pre[int(rng.random() * len(pre))]
            d = rng.sample(deck, 7)
            board = [x for x in d if x != o[0] and x != o[1]][:5]
            me = ev([h[0], h[1]] + board)
            ov = ev([o[0], o[1]] + board)
            if me > ov:
                w += 1
            elif me == ov:
                w += 0.5
        out.append(w / n)
    return c, out


if __name__ == "__main__":
    with Pool(2) as p:
        res = p.map(eq_random, [(c, k, N_A, c * 7 + k) for c in range(169) for k in (1, 3)], chunksize=8)
        eq1 = [0.0] * 169
        eq3 = [0.0] * 169
        for c, k, v in res:
            (eq1 if k == 1 else eq3)[c] = v
        score = []
        for c in range(169):
            hi, lo = divmod(c, 13)
            s = eq3[c]
            if hi != lo:
                suited = hi > lo
                a, b = (hi, lo) if suited else (lo, hi)
                gap = a - b - 1
                if suited:
                    s += 0.020
                if gap == 0 and b >= 3:
                    s += 0.012
                elif gap == 1 and b >= 3:
                    s += 0.006
                if not suited and gap >= 4 and a < 12:
                    s -= 0.015
                if not suited and gap >= 4 and a == 12:
                    s -= 0.006
            score.append(s)
        order = sorted(range(169), key=lambda c: -score[c])
        ncomb = [6 if c // 13 == c % 13 else (4 if c // 13 > c % 13 else 12) for c in range(169)]
        pct = [0.0] * 169
        acc = 0
        for c in order:
            pct[c] = (acc + ncomb[c] / 2) / 1326
            acc += ncomb[c]
        combos = []
        allc = {}
        for a in range(52):
            for b in range(a + 1, 52):
                allc.setdefault(cls(a, b), []).append((a, b))
        for c in order:
            combos.extend(allc[c])
        res = p.map(eq_range, [(c, combos, N_B, 1000 + c) for c in range(169)], chunksize=4)
        eqr = [None] * 169
        for c, v in res:
            eqr[c] = v
    json.dump({"buckets": BUCKETS, "pct": pct, "eqr": eqr, "eq1": eq1, "eq3": eq3, "order": order}, open("tables.json", "w"))
    R = "23456789TJQKA"

    def name(c):
        hi, lo = divmod(c, 13)
        if hi == lo:
            return R[hi] * 2
        return R[hi] + R[lo] + "s" if hi > lo else R[lo] + R[hi] + "o"

    print("top 40:", " ".join(name(c) for c in order[:40]))
    print("AA vs top2%%: %.2f  AKs vs 100%%: %.2f  72o vs 100%%: %.2f" % (eqr[12 * 14][0], eqr[12 * 13 + 11][-1], eqr[0 * 13 + 5][-1]))
