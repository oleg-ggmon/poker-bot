"""Your AlgoSoc Pokerbot.

Rename nothing: the platform imports `Agent` from this file. A fresh Agent()
is created for every table in every round, so anything you store on `self`
lasts one round (1,000 hands, same opponents) and is then thrown away.

Upload this one file. Only the Python standard library is available.

act(state) must return within 10 ms, and your thinking time across a round
must stay under the 10 s time bank. If it raises an error or times out,
you check when you can and fold otherwise. README.md lists what happens
for each kind of illegal action.
"""
import random


class Agent:
    def __init__(self):
        self.rng = random.Random()

    def on_table_start(self, info):
        """Optional. info: seat, num_players, hands, starting_stack, big_blind, ..."""
        self.seat = info["seat"]

    def act(self, state):
        """Return {"action": "fold" | "check" | "call" | "raise" | "all_in"}.

        For "raise", also give "amount": the total you want your bet to be
        this street ("raise to"), between state["min_raise_to"] and
        state["max_raise_to"]. Every state field is listed in README.md.
        """
        legal = state["legal_actions"]
        hole = state["hole_cards"]          # e.g. ["As", "Kd"]
        ranks = sorted("23456789TJQKA".index(c[0]) for c in hole)
        strong = ranks[0] == ranks[1] or ranks[1] >= 11  # pair or J+ high

        if strong and "raise" in legal:
            target = state["min_raise_to"] + state["pot"] // 2
            return {"action": "raise", "amount": min(target, state["max_raise_to"])}
        if "check" in legal:
            return {"action": "check"}
        if state["to_call"] <= state["big_blind"] * 2 or strong:
            return {"action": "call"}
        return {"action": "fold"}

    def on_hand_end(self, summary):
        """Optional. summary: board, shown cards, winners, stacks, full history."""
        pass
