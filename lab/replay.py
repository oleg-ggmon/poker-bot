"""Replay real rounds through a bot: at each of OUR real decision points ask the bot what it would do.

    python3 replay.py ../bot.py ../hands            # summary of where the bot disagrees with what was played
    python3 replay.py candidate.py ../hands --big   # also list disagreements in pots we lost big

The opponents' actions are replayed as they happened, so the bot's opponent model learns as it did live.
Where the candidate folds and the live bot continued, the exact saving or cost is known (we forfeit what
was already in the pot instead of the real result).
"""
import glob, importlib.util, json, os, sys


def load(path):
    spec = importlib.util.spec_from_file_location("rbot_" + str(abs(hash(path))), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def replay(data, mod):
    me = data["seat"]
    n = len(data["players"]) if "players" in data else 8
    ag = mod.Agent()
    ag.on_table_start({"seat": me, "num_players": n, "hands": 1000, "starting_stack": 2000, "big_blind": 20, "small_blind": 10})
    out = []
    for h in data["hands"]:
        bb = h.get("bb", 20)
        stacks = list(h.get("start_stacks", [2000] * n))
        bets = [0] * n
        contrib = [0] * n
        folded = [False] * n
        history = []
        street = "preflop"
        board = []
        cur = 0
        min_inc = bb
        raises = 0
        nposts = 0
        for e in h["events"]:
            if e[0] == "post":
                s, amt = e[1], e[2]
                stacks[s] -= amt; bets[s] += amt; contrib[s] += amt
                history.append({"seat": s, "street": "preflop", "action": "small_blind" if nposts == 0 else "big_blind", "amount": amt})
                nposts += 1
                cur = max(bets)
            elif e[0] == "board":
                street = e[1]; board = e[2]; bets = [0] * n; cur = 0; min_inc = bb; raises = 0
            elif e[0] == "refund":
                s, amt = e[1], e[2]
                stacks[s] += amt; contrib[s] -= amt
            elif e[0] == "act":
                s, a, amt = e[1], e[2], e[3] or 0
                if s == me:
                    to_call = min(cur - bets[s], stacks[s])
                    max_to = bets[s] + stacks[s]
                    others = any(not folded[j] and stacks[j] > 0 for j in range(n) if j != s)
                    can_raise = max_to > cur and others
                    legal = (["fold", "call"] if to_call > 0 else ["check"]) + (["raise"] if can_raise else [])
                    state = {"hand_number": h["n"], "street": street, "seat": me, "button": h["button"],
                             "hole_cards": h["hole"][str(me)], "board": list(board), "small_blind": bb // 2, "big_blind": bb,
                             "pot": sum(contrib), "stacks": list(stacks), "bets": list(bets), "folded": list(folded),
                             "to_call": to_call, "min_raise_to": min(cur + min_inc, max_to) if can_raise else None,
                             "max_raise_to": max_to if can_raise else None, "legal_actions": legal, "betting": "no_limit",
                             "raise_cap": None, "raises_this_street": raises, "history": list(history)}
                    d = ag.act(state) or {}
                    out.append({"n": h["n"], "street": street, "actual": a, "amt": amt, "bot": d.get("action"), "bot_amt": d.get("amount"),
                                "to_call": to_call, "pot": sum(contrib), "in": contrib[me], "result": h["results"][me],
                                "hole": "".join(h["hole"][str(me)]), "board": "".join(board), "max_to": max_to})
                if a == "raise":
                    add = amt - bets[s]
                    if amt - cur >= min_inc:
                        min_inc = amt - cur
                    stacks[s] -= add; bets[s] = amt; contrib[s] += add; cur = amt; raises += 1
                elif a == "call":
                    stacks[s] -= amt; bets[s] += amt; contrib[s] += amt
                elif a == "fold":
                    folded[s] = True
                history.append({"seat": s, "street": street, "action": a, "amount": amt})
        shown = {k: h["hole"][k] for k in h.get("showdown", {}) if k in h["hole"]}
        ag.on_hand_end({"hand_number": h["n"], "board": h["board"], "shown": shown, "winners": [],
                        "stacks": [2000 + r for r in h["results"]], "history": history})
    return out, ag


def main():
    mod = load(os.path.abspath(sys.argv[1]))
    files = sorted(glob.glob(os.path.join(sys.argv[2], "*.json")))
    big = "--big" in sys.argv
    tot_save = 0.0
    for f in files:
        data = json.load(open(f))
        decs, ag = replay(data, mod)
        seen = set()
        save = 0.0; nfold = 0; cont = 0; agree = 0; fold_strong = []
        rows = []
        for d in decs:
            if d["n"] in seen:
                continue
            a, b = d["actual"], d["bot"]
            b = "raise" if b == "all_in" else b
            if a == b or (a in ("call", "check") and b in ("call", "check")):
                agree += 1
                continue
            seen.add(d["n"])  # first disagreement in this hand
            if b == "fold" and a != "fold":
                nfold += 1
                save += (-d["in"]) - d["result"]   # candidate forfeits what was in; live bot got the real result
                rows.append(d)
            elif a == "fold" and b != "fold":
                cont += 1
                fold_strong.append(d)
            else:
                rows.append(d)
        tot_save += save
        print("%s: %d decisions, agree %d | candidate folds where live continued: %d hands, exact effect %+.0f bb | candidate continues where live folded: %d | errs %d" % (
            data.get("ref", os.path.basename(f)), len(decs), agree, nfold, save / 20.0, cont, getattr(ag, "errs", 0)))
        if big:
            for d in rows:
                if abs(d["result"]) >= 600:
                    print("   #%-4d %-7s %s %-10s live %-5s %-5s cand %-5s %-5s to_call %-5d pot %-5d result %+d" % (
                        d["n"], d["street"], d["hole"], d["board"], d["actual"], d["amt"], d["bot"], d["bot_amt"] or "", d["to_call"], d["pot"], d["result"]))
        if "--folds" in sys.argv:
            for d in fold_strong:
                print("   live FOLDED #%-4d %-7s %s %-10s cand %-5s %-5s to_call %-5d pot %-5d in %d" % (
                    d["n"], d["street"], d["hole"], d["board"], d["bot"], d["bot_amt"] or "", d["to_call"], d["pot"], d["in"]))
    print("TOTAL exact effect of the candidate's extra folds: %+.0f bb over %d rounds = %+.1f bb/100" % (tot_save / 20.0, len(files), tot_save / 20.0 / len(files) / 10))


if __name__ == "__main__":
    main()
