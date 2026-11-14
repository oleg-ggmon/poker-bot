"""Test opponents that shove preflop: always, or with the top share of hands."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from evalcore import cls  # noqa: E402
RANKS = "23456789TJQKA"; SUITS = "cdhs"
CARD = {r + s: RANKS.index(r) * 4 + SUITS.index(s) for r in RANKS for s in SUITS}
PCT = json.load(open(os.path.join(os.path.dirname(HERE), "tables.json")))["pct"]


def make(top):
    class Shover:
        def act(self, st):
            h = [CARD[c] for c in st["hole_cards"]]
            if PCT[cls(h[0], h[1])] <= top:
                return {"action": "all_in"}
            return {"action": "check"} if st["to_call"] == 0 else {"action": "fold"}
    return Shover


Agent = make(1.0)
Top30 = make(0.30)
Top10 = make(0.10)
