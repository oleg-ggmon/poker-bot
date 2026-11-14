"""Replica opponents: simple bots that reproduce a measured profile (from analyse.py -> replicas.json).

A profile is {"vpip","pfr","tb","jam","ftb","bet","size","open"}. Replicas play stronger hands first,
so their frequencies AND the meaning of their bets roughly match the real opponent.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
from evalcore import cls, ev  # noqa: E402

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: RANKS.index(r) * 4 + SUITS.index(s) for r in RANKS for s in SUITS}
PCT = json.load(open(os.path.join(HERE, "tables.json")))["pct"]


def strength(hole, board, rng, sims=24):
    used = set(hole) | set(board)
    deck = [c for c in range(52) if c not in used]
    need = 5 - len(board)
    w = 0.0
    for _ in range(sims):
        d = rng.sample(deck, 2 + need)
        full = board + d[2:]
        a = ev(hole + full)
        b = ev(d[:2] + full)
        w += 1.0 if a > b else (0.5 if a == b else 0.0)
    return w / sims


def make(prof):
    class Replica:
        def __init__(self):
            self.rng = random.Random()
            self.p = prof

        def act(self, st):
            P = self.p
            legal = st["legal_actions"]
            tc = st["to_call"]
            pot = st["pot"]
            bb = st["big_blind"]
            hi = st["max_raise_to"]
            hole = [CARD[c] for c in st["hole_cards"]]
            can_raise = "raise" in legal
            passive = {"action": "check"} if tc == 0 else {"action": "fold"}
            call = {"action": "call"} if tc > 0 else {"action": "check"}
            if st["street"] == "preflop":
                p = PCT[cls(hole[0], hole[1])]
                if st["raises_this_street"] == 0:
                    if p <= P["jam"] and can_raise:
                        return {"action": "raise", "amount": hi}
                    if p <= P["pfr"] and can_raise:
                        return {"action": "raise", "amount": int((P.get("open") or 3) * bb)}
                    return call if p <= P["vpip"] else passive
                if tc >= 600:
                    return call if (P["vpip"] > 0.9 or p <= max(0.03, P["jam"] * 1.5)) else passive
                if st["bets"][st["seat"]] > bb and "f3" in P:
                    # We raised earlier this hand and got re-raised.
                    keep = max(0.01, P["pfr"] * (1.0 - P["f3"]))
                    if p <= keep * 0.3 and can_raise:
                        return {"action": "raise", "amount": int(2.5 * (tc + st["bets"][st["seat"]]))}
                    return call if p <= keep else passive
                if p <= P["tb"] and can_raise:
                    return {"action": "raise", "amount": int(3 * (tc + st["bets"][st["seat"]]))}
                return call if p <= min(1.0, P["vpip"] * 0.8) else passive
            board = [CARD[c] for c in st["board"]]
            s = strength(hole, board, self.rng)
            if tc == 0:
                bet = P["bet"]
                if can_raise and (s >= 1.0 - 0.8 * bet or self.rng.random() < 0.2 * bet):
                    return {"action": "raise", "amount": st["bets"][st["seat"]] + int(max(bb, (P.get("size") or 0.6) * pot))}
                return call
            if P["ftb"] < 0.03:
                return call
            if s >= 0.88 and can_raise and self.rng.random() < min(0.8, 2 * P["bet"]):
                return {"action": "raise", "amount": st["bets"][st["seat"]] + tc + int(0.8 * (pot + tc))}
            return call if s >= 0.15 + 0.7 * P["ftb"] else passive

    return Replica
