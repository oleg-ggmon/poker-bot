"""Never folds, never raises."""


class Agent:
    def act(self, state):
        return {"action": "check" if "check" in state["legal_actions"] else "call"}
