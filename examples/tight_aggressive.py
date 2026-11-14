"""A simple tight-aggressive bot: plays strong starting hands hard,
continues post-flop with a pair or better, and shoves short stacks."""

RANKS = "23456789TJQKA"


def preflop_strength(hole):
    a, b = sorted((RANKS.index(c[0]) for c in hole), reverse=True)
    suited = hole[0][1] == hole[1][1]
    if a == b:
        return 0.5 + a / 24
    score = (a + b) / 24 + (0.06 if suited else 0) - (0.04 if a - b > 4 else 0)
    return score


def made_pair_or_better(hole, board):
    ranks = [c[0] for c in hole + board]
    return any(ranks.count(r) >= 2 for r in set(c[0] for c in hole))


class Agent:
    def act(self, state):
        legal = state["legal_actions"]
        hole, board = state["hole_cards"], state["board"]
        me = state["seat"]
        stack = state["stacks"][me]
        bb = state["big_blind"]

        if state["street"] == "preflop":
            s = preflop_strength(hole)
            if stack <= 10 * bb and s >= 0.62 and "raise" in legal:
                return {"action": "raise", "amount": state["max_raise_to"]}
            if s >= 0.8 and "raise" in legal:
                return {"action": "raise", "amount": min(state["max_raise_to"], state["min_raise_to"] + 2 * bb)}
            if s >= 0.62 and state["to_call"] <= 3 * bb:
                return {"action": "call" if "call" in legal else "check"}
        else:
            if made_pair_or_better(hole, board):
                if "raise" in legal and state["to_call"] == 0:
                    return {"action": "raise", "amount": min(state["max_raise_to"], state["min_raise_to"] + state["pot"] // 2)}
                return {"action": "call" if "call" in legal else "check"}
        return {"action": "check" if "check" in legal else "fold"}
