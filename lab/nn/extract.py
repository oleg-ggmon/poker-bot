"""Build the training set for the fold-probability net.

One row per real postflop decision where an opponent seat faced a bet. Features use only what the bot
knows live at that moment: the situation, and v5's own per-seat stats learned from EARLIER hands of
the same round (the v5 Agent is replayed through each round so the stats are exactly the live ones).

    python3 extract.py            # writes data.npz (X, y, meta) from ../../hands
"""
import glob, importlib.util, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(os.path.dirname(HERE))
RANKS = "23456789TJQKA"

FEATS = ["flop", "turn", "river", "log_frac", "frac_c", "log_pot_bb", "log_spr", "allin", "n_others", "headsup",
         "stage", "faced_before", "was_pf_raiser", "bettor_pf_raiser", "is_raise", "own_bet_street", "acts_after",
         "bettor_barrels", "pf_level", "paired", "flushy", "high", "straighty",
         "vp", "pf", "af", "ftb", "cbig", "fr", "f3", "log_n", "base_logit", "table_logit"]


def load_bot(path):
    spec = importlib.util.spec_from_file_location("v5bot", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def logit(p):
    p = min(0.98, max(0.02, p))
    return math.log(p / (1 - p))


def board_feats(board):
    rs = [RANKS.index(c[0]) for c in board]
    ss = [c[1] for c in board]
    paired = 1.0 if len(set(rs)) < len(rs) else 0.0
    fl = max(ss.count(x) for x in "cdhs")
    flushy = (fl - 1) / 3.0 if fl < 4 else 1.0
    high = max(rs) / 12.0
    u = set(rs) | ({-1} if 12 in rs else set())
    best = 0
    for lo in range(-1, 9):
        k = sum(1 for r in range(lo, lo + 5) if r in u)
        if k > best:
            best = k
    return paired, flushy, high, (best - 1) / 4.0


def situation(o, ag, kb, stg, fr_, pot, tc, stack_s, n_others, street, faced, was_pfr, bet_pfr, is_raise,
              own_bet, acts_after, barrels, L, board):
    """Feature vector. Kept in one place so the bot-side code can mirror it line for line."""
    base = o.fold_at(kb, stg, ag.tfb, ag.tfd)
    tb = ag.tfb[stg]; td = ag.tfd[stg]
    trate = (sum(td) + 0.45 * 8.0) / (sum(tb) + 8.0)
    pr, fy, hi, sy = board_feats(board)
    fc = fr_ if fr_ < 3.0 else 3.0
    spr = (stack_s - tc) / float(pot) if stack_s > tc else 0.0
    return [1.0 if street == "flop" else 0.0, 1.0 if street == "turn" else 0.0, 1.0 if street == "river" else 0.0,
            math.log(fc + 0.05), fc, math.log(pot / 20.0 + 1.0), math.log(spr + 0.1), 1.0 if tc >= stack_s else 0.0,
            float(n_others), 1.0 if n_others == 1 else 0.0, float(stg), float(min(faced, 3)),
            1.0 if was_pfr else 0.0, 1.0 if bet_pfr else 0.0, 1.0 if is_raise else 0.0, 1.0 if own_bet else 0.0,
            1.0 if acts_after else 0.0, float(min(barrels, 3)), float(min(L, 3)), pr, fy, hi, sy,
            o.vp(), o.pf(), o.af(), o.ftb(), o.cbig(), o.fr(), o.f3(), math.log(o.n + 1.0), logit(base), logit(trate)]


def run(bot_path, hand_dir):
    mod = load_bot(bot_path)
    X = []; Y = []; M = []
    files = sorted(glob.glob(os.path.join(hand_dir, "*.json")))
    for fi, f in enumerate(files):
        data = json.load(open(f))
        rnd = int(os.path.basename(f).split("_r")[1][:3])
        me = data["seat"]
        n = len(data["players"])
        ag = mod.Agent()
        ag.on_table_start({"seat": me, "num_players": n, "hands": 1000, "starting_stack": 2000, "big_blind": 20, "small_blind": 10})
        for h in data["hands"]:
            stacks = list(h.get("start_stacks", [2000] * n))
            bets = [0] * n; contrib = [0] * n; folded = [False] * n
            history = []; street = "preflop"; board = []; cur = 0; nposts = 0
            L = 0; lastr = -1; inpost = set(); faced = [0] * n; barrels = [0] * n
            bet_this = set(); bettor = -1; nraise = 0; acted = []
            for e in h["events"]:
                if e[0] == "post":
                    s, amt = e[1], e[2]
                    stacks[s] -= amt; bets[s] += amt; contrib[s] += amt
                    history.append({"seat": s, "street": "preflop", "action": "small_blind" if nposts == 0 else "big_blind", "amount": amt})
                    nposts += 1; cur = max(bets)
                elif e[0] == "board":
                    street = e[1]; board = e[2]; bets = [0] * n; cur = 0
                    bet_this = set(); bettor = -1; nraise = 0; acted = []
                elif e[0] == "refund":
                    stacks[e[1]] += e[2]; contrib[e[1]] -= e[2]
                elif e[0] == "act":
                    s, a, amt = e[1], e[2], e[3] or 0
                    tc = cur - bets[s]
                    if street != "preflop" and tc > 0 and s != me and stacks[s] > 0:
                        pot = sum(contrib)
                        before = pot - tc
                        fr_ = tc / float(before) if before > 0 else 1.0
                        kb = 0 if fr_ < 0.5 else (1 if fr_ < 0.95 else (2 if fr_ < 1.6 else 3))
                        stg = 1 if s in inpost else 0
                        others = sum(1 for j in range(n) if j != s and not folded[j])
                        o = ag.opp[s]
                        # acts_after: this seat had not yet acted on this street when the bet went in
                        x = situation(o, ag, kb, stg, fr_, pot, tc, stacks[s], others, street, faced[s], s == lastr,
                                      bettor == lastr, nraise >= 2, s in bet_this, s not in acted, barrels[bettor], L, board)
                        X.append(x); Y.append(0 if a == "fold" else (1 if a == "call" else 2))
                        # meta: round, hand, seat, kb, stg, v5 base estimate, heads-up opening bet flag, bettor is us
                        M.append([rnd, h["n"], s, kb, stg, o.fold_at(kb, stg, ag.tfb, ag.tfd),
                                  1 if (others == 1 and nraise == 1) else 0, 1 if bettor == me else 0,
                                  1 if s not in acted else 0, 0 if street == "flop" else (1 if street == "turn" else 2),
                                  (stacks[s] - tc) / float(pot) if pot else 0.0])
                    if street != "preflop":
                        if tc > 0:
                            faced[s] += 1
                        acted.append(s)
                    if a == "raise":
                        add = amt - bets[s]
                        stacks[s] -= add; bets[s] = amt; contrib[s] += add; cur = amt
                        if street == "preflop":
                            L += 1; lastr = s
                        else:
                            if s not in bet_this:
                                barrels[s] += 1
                            bet_this.add(s); bettor = s; nraise += 1; inpost.add(s)
                    elif a == "call":
                        stacks[s] -= amt; bets[s] += amt; contrib[s] += amt
                        if street != "preflop":
                            inpost.add(s)
                    elif a == "fold":
                        folded[s] = True
                    history.append({"seat": s, "street": street, "action": a, "amount": amt})
            shown = {k: h["hole"][k] for k in h.get("showdown", {}) if k in h["hole"]}
            ag.on_hand_end({"hand_number": h["n"], "board": h["board"], "shown": shown, "winners": [],
                            "stacks": [2000 + r for r in h["results"]], "history": history})
        if ag.errs:
            print("bot errors in", f, ag.errs, ag.last_err)
        print(os.path.basename(f), len(X), flush=True)
    return np.array(X, dtype=np.float32), np.array(Y, dtype=np.int8), np.array(M, dtype=np.float64)


if __name__ == "__main__":
    X, Y, M = run(os.path.join(KIT, "bot.py"), os.path.join(KIT, "hands"))
    np.savez_compressed(os.path.join(HERE, "data.npz"), X=X, y=Y, meta=M)
    print("rows", len(Y), "fold/call/raise", [(Y == k).mean().round(3) for k in range(3)])
