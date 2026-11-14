"""Test opponent: the design most teams end up with. Preflop chart, then Monte Carlo equity against
random hands compared with pot odds. Variants differ only in thresholds."""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from evalcore import cls, ev  # noqa: E402

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: RANKS.index(r) * 4 + SUITS.index(s) for r in RANKS for s in SUITS}
PCT = json.load(open(os.path.join(os.path.dirname(HERE), "tables.json")))["pct"]


def equity(hole, board, nopp, rng, sims):
    used = set(hole) | set(board)
    deck = [c for c in range(52) if c not in used]
    need = 5 - len(board)
    w = 0.0
    for _ in range(sims):
        d = rng.sample(deck, 2 * nopp + need)
        full = board + d[2 * nopp:]
        me = ev(hole + full)
        ok = 1.0
        for i in range(nopp):
            o = ev(d[2 * i:2 * i + 2] + full)
            if o > me:
                ok = 0.0
                break
            if o == me:
                ok = 0.5
        w += ok
    return w / sims


def make(raise_pct=0.05, open_pct=0.18, limp_pct=0.40, bet_hi=0.75, bet_lo=0.55, call_edge=0.05,
         raise_eq=0.85, bluff=0.10, sims=40, big=0.75, small=0.5):
    class EquityBot:
        def __init__(self):
            self.rng = random.Random()

        def act(self, st):
            legal = st["legal_actions"]
            tc = st["to_call"]
            pot = st["pot"]
            bb = st["big_blind"]
            me = st["seat"]
            hole = [CARD[c] for c in st["hole_cards"]]
            can_raise = "raise" in legal
            passive = {"action": "check"} if tc == 0 else {"action": "fold"}
            call = {"action": "call"} if tc > 0 else {"action": "check"}
            cur = st["bets"][me] + tc
            if st["street"] == "preflop":
                p = PCT[cls(hole[0], hole[1])]
                if p <= raise_pct:
                    if can_raise:
                        return {"action": "raise", "amount": max(3 * bb, 3 * cur)}
                    return call
                if p <= open_pct:
                    if st["raises_this_street"] == 0 and can_raise:
                        return {"action": "raise", "amount": 3 * bb}
                    return call if tc <= 6 * bb else passive
                if p <= limp_pct:
                    return call if tc <= 2 * bb else passive
                return passive
            board = [CARD[c] for c in st["board"]]
            nopp = max(1, sum(1 for i, f in enumerate(st["folded"]) if not f and i != me))
            eq = equity(hole, board, nopp, self.rng, sims)
            if tc == 0:
                if not can_raise:
                    return call
                if eq > bet_hi:
                    return {"action": "raise", "amount": st["bets"][me] + int(big * pot)}
                if eq > bet_lo or self.rng.random() < bluff:
                    return {"action": "raise", "amount": st["bets"][me] + int(small * pot)}
                return call
            odds = tc / float(pot + tc)
            if eq > raise_eq and can_raise:
                return {"action": "raise", "amount": int(2.5 * cur)}
            return call if eq > odds + call_edge else passive

    return EquityBot


Agent = make()
Loose = make(open_pct=0.28, limp_pct=0.6, bet_lo=0.5, call_edge=0.0, bluff=0.2)
Tight = make(raise_pct=0.04, open_pct=0.12, limp_pct=0.2, bet_hi=0.8, bet_lo=0.65, call_edge=0.12, bluff=0.03)
Aggro = make(raise_pct=0.08, open_pct=0.30, limp_pct=0.35, bet_hi=0.7, bet_lo=0.45, call_edge=0.03, raise_eq=0.75, bluff=0.35, big=1.0, small=0.7)
