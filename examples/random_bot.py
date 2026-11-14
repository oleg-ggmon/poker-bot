"""Picks a random legal action."""
import random


class Agent:
    def __init__(self):
        self.rng = random.Random()

    def act(self, state):
        action = self.rng.choice(state["legal_actions"])
        if action == "raise":
            lo, hi = state["min_raise_to"], state["max_raise_to"]
            return {"action": "raise", "amount": self.rng.randint(lo, min(hi, lo * 3))}
        return {"action": action}
