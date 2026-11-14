"""Hold'em table engine.

Two table formats share one hand engine:
  FixedHandsTable  the tournament format: a fixed number of hands, every hand
                   starts everyone on the same stack, fixed blinds, scored on
                   chips won. Every table deals exactly the same number of hands.
  SitAndGo         the older format: rising blinds until one player has every chip.


A table seats up to 8 players. Each starts with the same stack; blinds rise
on a fixed schedule; the table ends when one player holds every chip or the
hand cap is reached. Eliminated players are paid points for their finishing
place; survivors at the cap split the remaining places by ICM.

Players are any objects with:
    start_table(seat, info)   called once before the first hand
    act(state) -> dict|None   {"action": "fold|check|call|raise", "amount": int}
    hand_end(summary)         called after every hand
"""
import random

from .cards import evaluate, full_deck, hand_name, to_str
from .icm import icm

DEFAULT_CONFIG = {
    "starting_stack": 2000,
    "hands_per_level": 25,
    "max_hands": 200,
    "blinds": [[10, 20], [20, 40], [30, 60], [50, 100], [75, 150],
               [100, 200], [150, 300], [200, 400]],
    "points": [100, 60, 40, 25, 15, 10, 5, 0],
    # "no_limit", "pot_limit" or "fixed_limit"
    "betting": "no_limit",
    # Max voluntary bets/raises per street (blinds don't count). 0 = no cap;
    # fixed-limit defaults to 4.
    "raise_cap": 0,
}

BETTING_NAMES = {"no_limit": "No-Limit", "pot_limit": "Pot-Limit", "fixed_limit": "Fixed-Limit"}


def effective_raise_cap(cfg):
    cap = int(cfg.get("raise_cap") or 0)
    if cfg.get("betting") == "fixed_limit" and not cap:
        cap = 4
    return cap

STREETS = ["preflop", "flop", "turn", "river"]


def blinds_for(config, hand_no):
    level = (hand_no - 1) // config["hands_per_level"]
    sched = config["blinds"]
    if level < len(sched):
        return sched[level][0], sched[level][1], level
    sb, bb = sched[-1]
    k = 2 ** (level - len(sched) + 1)
    return sb * k, bb * k, level


class SitAndGo:
    def __init__(self, players, config=None, seed=None, record=False, rng=None):
        """rng: pass random.SystemRandom() for shuffles nobody can predict
        (the tournament does); otherwise `seed` makes runs repeatable."""
        self.players = players
        self.n = len(players)
        self.cfg = dict(DEFAULT_CONFIG, **(config or {}))
        self.rng = rng or random.Random(seed)
        self.record = record
        self.log = []
        self.stacks = [self.cfg["starting_stack"]] * self.n
        self.finish = [None] * self.n  # finishing place, 1 = winner
        self.hands_played = 0

    # ---------------------------------------------------------------- table
    def play(self):
        for seat, p in enumerate(self.players):
            p.start_table(seat, {
                "seat": seat,
                "num_players": self.n,
                "starting_stack": self.cfg["starting_stack"],
                "hands_per_level": self.cfg["hands_per_level"],
                "max_hands": self.cfg["max_hands"],
                "blinds": self.cfg["blinds"],
                "points": self.cfg["points"],
                "betting": self.cfg["betting"],
                "raise_cap": effective_raise_cap(self.cfg) or None,
            })
        button = self.rng.randrange(self.n)
        for hand_no in range(1, self.cfg["max_hands"] + 1):
            alive = [i for i in range(self.n) if self.stacks[i] > 0]
            if len(alive) <= 1:
                break
            button = self._next_alive(button)
            start = list(self.stacks)
            self._play_hand(hand_no, button)
            self.hands_played = hand_no
            self._eliminate(start)

        alive = [i for i in range(self.n) if self.stacks[i] > 0]
        pts = self.cfg["points"]
        points = [0.0] * self.n
        for i in range(self.n):
            if self.finish[i] is not None:
                points[i] = float(pts[self.finish[i] - 1]) if self.finish[i] <= len(pts) else 0.0
        if len(alive) == 1:
            self.finish[alive[0]] = 1
            points[alive[0]] = float(pts[0])
        elif alive:
            ev = icm([self.stacks[i] for i in alive], pts[:len(alive)])
            order = sorted(alive, key=lambda i: -self.stacks[i])
            for place, i in enumerate(order, 1):
                self.finish[i] = place
            for i, e in zip(alive, ev):
                points[i] = e
        return {
            "points": points,
            "places": self.finish,
            "stacks": self.stacks,
            "hands": self.hands_played,
            "survivors": len(alive),
        }

    def _next_alive(self, seat):
        for k in range(1, self.n + 1):
            s = (seat + k) % self.n
            if self.stacks[s] > 0:
                return s
        return seat

    def _eliminate(self, start):
        busted = [i for i in range(self.n) if self.stacks[i] == 0 and self.finish[i] is None]
        if not busted:
            return
        remaining = sum(1 for i in range(self.n) if self.stacks[i] > 0)
        # Bigger stack at the start of the hand finishes higher.
        self.rng.shuffle(busted)
        busted.sort(key=lambda i: -start[i])
        for k, i in enumerate(busted):
            self.finish[i] = remaining + k + 1

    # ----------------------------------------------------------------- hand
    def _play_hand(self, hand_no, button):
        sb_amt, bb_amt, level = blinds_for(self.cfg, hand_no)
        n = self.n
        in_hand = [self.stacks[i] > 0 for i in range(n)]
        seats = [i for i in range(n) if in_hand[i]]
        deck = full_deck()
        self.rng.shuffle(deck)
        hole = {}
        for i in seats:
            hole[i] = [deck.pop(), deck.pop()]
        board = []
        folded = [not x for x in in_hand]
        contrib = [0] * n
        bets = [0] * n
        history = []
        rec = {
            "n": hand_no, "sb": sb_amt, "bb": bb_amt, "button": button,
            "stacks": list(self.stacks),
            "hole": {str(i): [to_str(c) for c in hole[i]] for i in seats},
            "events": [],
        }

        def put(i, amt):
            amt = min(amt, self.stacks[i])
            self.stacks[i] -= amt
            bets[i] += amt
            contrib[i] += amt
            return amt

        if len(seats) == 2:
            sb_seat = button
        else:
            sb_seat = self._next_alive(button)
        bb_seat = self._next_alive(sb_seat)
        rec["events"].append(["post", sb_seat, put(sb_seat, sb_amt)])
        rec["events"].append(["post", bb_seat, put(bb_seat, bb_amt)])
        history.append({"seat": sb_seat, "street": "preflop", "action": "small_blind", "amount": bets[sb_seat]})
        history.append({"seat": bb_seat, "street": "preflop", "action": "big_blind", "amount": bets[bb_seat]})

        def live():
            return [i for i in range(n) if not folded[i]]

        def can_act(i):
            return not folded[i] and self.stacks[i] > 0

        for street_idx, street in enumerate(STREETS):
            if street_idx == 1:
                board += [deck.pop(), deck.pop(), deck.pop()]
            elif street_idx > 1:
                board.append(deck.pop())
            if street_idx:
                rec["events"].append(["board", street, [to_str(c) for c in board]])
                bets = [0] * n

            actors = [i for i in range(n) if can_act(i)]
            if len(live()) > 1 and (len(actors) > 1 or any(bets[i] < max(bets) for i in actors)):
                first = self._next_alive(bb_seat) if street == "preflop" else self._next_alive(button)
                self._betting_round(street, first, hole, board, bets, contrib, folded,
                                    history, rec, hand_no, button, sb_amt, bb_amt, level, put)
            # Return any uncalled part of the top bet.
            ordered = sorted(range(n), key=lambda i: -bets[i])
            top, second = ordered[0], ordered[1]
            if bets[top] > bets[second]:
                refund = bets[top] - bets[second]
                self.stacks[top] += refund
                contrib[top] -= refund
                bets[top] -= refund
                rec["events"].append(["refund", top, refund])
            if len(live()) == 1:
                break

        # Showdown / award.
        winners_log = []
        lv = live()
        shown = {}
        if len(lv) == 1:
            w = lv[0]
            pot = sum(contrib)
            self.stacks[w] += pot
            winners_log.append([w, pot, None])
        else:
            scores = {i: evaluate(hole[i] + board) for i in lv}
            shown = {str(i): [to_str(c) for c in hole[i]] for i in lv}
            levels = sorted(set(contrib[i] for i in range(n) if contrib[i] > 0))
            prev = 0
            won = [0] * n
            for lvl in levels:
                portion = sum(min(c, lvl) - min(c, prev) for c in contrib)
                elig = [i for i in lv if contrib[i] >= lvl] or lv
                best = max(scores[i] for i in elig)
                ws = [i for i in elig if scores[i] == best]
                # Odd chips go to the first winner left of the button.
                ws.sort(key=lambda i: (i - button - 1) % n)
                share, odd = divmod(portion, len(ws))
                for k, i in enumerate(ws):
                    won[i] += share + (1 if k < odd else 0)
                prev = lvl
            for i in range(n):
                if won[i]:
                    self.stacks[i] += won[i]
                    winners_log.append([i, won[i], hand_name(scores[i])])
            rec["showdown"] = {str(i): hand_name(scores[i]) for i in lv}

        for w in winners_log:
            rec["events"].append(["win"] + w)
        rec["board"] = [to_str(c) for c in board]
        rec["end"] = list(self.stacks)
        if self.record:
            self.log.append(rec)

        summary = {
            "type": "hand_end",
            "hand_number": hand_no,
            "board": [to_str(c) for c in board],
            "shown": shown,
            "winners": [{"seat": w[0], "amount": w[1], "hand": w[2]} for w in winners_log],
            "stacks": list(self.stacks),
            "history": history,
        }
        for i in seats:
            self.players[i].hand_end(summary)

    def _betting_round(self, street, first, hole, board, bets, contrib, folded,
                       history, rec, hand_no, button, sb_amt, bb_amt, level, put):
        n = self.n
        current = max(bets)
        min_inc = bb_amt
        structure = self.cfg.get("betting", "no_limit")
        cap = effective_raise_cap(self.cfg)
        if structure == "fixed_limit":
            # Small bet pre-flop and on the flop, big bet on the turn and river.
            min_inc = bb_amt if street in ("preflop", "flop") else 2 * bb_amt
        raises = 0
        # Players who still owe an action, and whether they may raise.
        pending = {i for i in range(n) if not folded[i] and self.stacks[i] > 0}
        may_raise = {i: True for i in pending}
        seat = first
        guard = 0
        while pending and guard < 10000:
            guard += 1
            if sum(1 for i in range(n) if not folded[i]) <= 1:
                return
            if seat not in pending:
                seat = (seat + 1) % n
                continue
            i = seat
            to_call = min(current - bets[i], self.stacks[i])
            others_can_act = any(not folded[j] and self.stacks[j] > 0 for j in range(n) if j != i)
            stack_to = bets[i] + self.stacks[i]
            if structure == "fixed_limit":
                max_to = min(current + min_inc, stack_to)
            elif structure == "pot_limit":
                # Largest raise = the pot after you call.
                max_to = min(current + sum(contrib) + to_call, stack_to)
            else:
                max_to = stack_to
            can_raise = (may_raise.get(i, True) and max_to > current and others_can_act
                         and not (cap and raises >= cap))
            min_to = min(current + min_inc, max_to)
            legal = (["fold", "call"] if to_call > 0 else ["check"]) + (["raise"] if can_raise else [])
            state = {
                "type": "act",
                "hand_number": hand_no,
                "street": street,
                "seat": i,
                "button": button,
                "hole_cards": [to_str(c) for c in hole[i]],
                "board": [to_str(c) for c in board],
                "small_blind": sb_amt,
                "big_blind": bb_amt,
                "blind_level": level,
                "pot": sum(contrib),
                "stacks": list(self.stacks),
                "bets": list(bets),
                "folded": list(folded),
                "to_call": to_call,
                "min_raise_to": min_to if can_raise else None,
                "max_raise_to": max_to if can_raise else None,
                "legal_actions": legal,
                "betting": structure,
                "raise_cap": cap or None,
                "raises_this_street": raises,
                "history": list(history),
            }
            decision = self.players[i].act(state) or {}
            action = str(decision.get("action", "")).lower()
            amount = decision.get("amount")

            if action in ("raise", "bet", "all_in", "allin") and can_raise:
                if action in ("all_in", "allin"):
                    amount = max_to
                try:
                    target = int(amount)
                except (TypeError, ValueError, OverflowError):
                    target = min_to
                target = max(min_to, min(target, max_to))
                put(i, target - bets[i])
                raise_size = target - current
                full = raise_size >= min_inc
                if full and structure != "fixed_limit":
                    min_inc = raise_size
                current = target
                raises += 1
                pending = {j for j in range(n) if j != i and not folded[j] and self.stacks[j] > 0}
                for j in pending:
                    if full:
                        may_raise[j] = True
                    # An incomplete all-in raise does not reopen raising for
                    # players who have already acted.
                    else:
                        may_raise.setdefault(j, True)
                act, amt = "raise", target
            elif action in ("call", "raise", "bet", "all_in", "allin") and to_call > 0:
                put(i, to_call)
                act, amt = "call", to_call
            elif to_call == 0:
                # Anything else when there is nothing to call is a check.
                act, amt = "check", 0
            else:
                folded[i] = True
                act, amt = "fold", 0
            pending.discard(i)
            may_raise[i] = False
            history.append({"seat": i, "street": street, "action": act, "amount": amt})
            rec["events"].append(["act", i, act, amt])
            seat = (seat + 1) % n


class FixedHandsTable(SitAndGo):
    """Play exactly `hands` hands. Every hand starts all players on
    `starting_stack` chips with fixed blinds; the score is chips won.

    play() returns {"chips": [...], "hands": n, "log": [...] if record}.
    Chips across the table always sum to zero.
    """

    def __init__(self, players, hands=1000, config=None, seed=None, record=False, rng=None):
        cfg = dict(config or {})
        sb, bb = cfg.pop("fixed_blinds", (10, 20))
        cfg.update(blinds=[[sb, bb]], hands_per_level=10 ** 9, max_hands=hands)
        super().__init__(players, cfg, seed=seed, record=record, rng=rng)
        self.hands = hands

    def play(self):
        start = self.cfg["starting_stack"]
        for seat, p in enumerate(self.players):
            p.start_table(seat, {
                "seat": seat,
                "num_players": self.n,
                "format": "fixed_hands",
                "hands": self.hands,
                "starting_stack": start,
                "stacks_reset_each_hand": True,
                "small_blind": self.cfg["blinds"][0][0],
                "big_blind": self.cfg["blinds"][0][1],
                "betting": self.cfg["betting"],
                "raise_cap": effective_raise_cap(self.cfg) or None,
            })
        chips = [0] * self.n
        button = self.rng.randrange(self.n)
        for hand_no in range(1, self.hands + 1):
            self.stacks = [start] * self.n
            button = (button + 1) % self.n
            self._play_hand(hand_no, button)
            for i in range(self.n):
                chips[i] += self.stacks[i] - start
            self.hands_played = hand_no
        return {"chips": chips, "hands": self.hands_played,
                "log": self.log if self.record else None}
