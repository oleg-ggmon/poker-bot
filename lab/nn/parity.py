"""Check that the bot computes the same net inputs and output as the training code.

For every real heads-up first bet WE made, rebuild the state the bot saw, ask the built bot for its
fold probability, and compare with the numpy model on the training row for the opponent's reply."""
import glob, json, os, sys
import numpy as np
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE, "train.py")).read().split('if "--final"')[0])
from extract import load_bot
w = json.load(open(os.path.join(HERE, "weights.json")))
model = (np.array(w["mu"]), np.array(w["sd"]), [np.array(a) for a in w["W"]], [np.array(a) for a in w["B"]])
pn = predict(model, X)
key = {}
for i in range(len(y)):
    if M[i, 7] == 1 and M[i, 6] == 1:
        key[(int(M[i, 0]), int(M[i, 1]), int(M[i, 2]), int(M[i, 9]))] = i
mod = load_bot(sys.argv[1])
diffs = []; xd = 0.0
for f in sorted(glob.glob(os.path.join(HERE, "../../hands/*.json"))):
    data = json.load(open(f)); rnd_ = int(os.path.basename(f).split("_r")[1][:3])
    me = data["seat"]; n = len(data["players"])
    ag = mod.Agent(); ag.on_table_start({"seat": me, "num_players": n})
    for h in data["hands"]:
        stacks = [2000] * n; bets = [0] * n; contrib = [0] * n; folded = [False] * n
        history = []; street = "preflop"; board = []; cur = 0; nposts = 0
        for e in h["events"]:
            if e[0] == "post":
                s, amt = e[1], e[2]; stacks[s] -= amt; bets[s] += amt; contrib[s] += amt
                history.append({"seat": s, "street": "preflop", "action": "small_blind" if nposts == 0 else "big_blind", "amount": amt}); nposts += 1; cur = max(bets)
            elif e[0] == "board":
                street = e[1]; board = e[2]; bets = [0] * n; cur = 0
            elif e[0] == "refund":
                stacks[e[1]] += e[2]; contrib[e[1]] -= e[2]
            elif e[0] == "act":
                s, a, amt = e[1], e[2], e[3] or 0
                live = [j for j in range(n) if j != me and not folded[j]]
                if s == me and street != "preflop" and cur - bets[s] == 0 and a == "raise" and len(live) == 1:
                    s1 = live[0]
                    k = (rnd_, h["n"], s1, {"flop": 0, "turn": 1, "river": 2}[street])
                    if k in key and stacks[s1] > 0:
                        st = {"street": street, "history": list(history), "board": list(board), "seat": me}
                        ag.me = me; ag.n = n
                        L, lastr = ag._scan(st)[:2]
                        nnx = ag._nnctx(st, s1, L, lastr)
                        p = ag._nnfold(nnx, ag.opp[s1], amt - bets[me], sum(contrib), stacks[s1])
                        i = key[k]
                        diffs.append(abs(p - min(0.95, max(0.02, pn[i]))))
                        xd = max(xd, float(np.abs(np.array(nnx[0]) - X[i]).max()))
                        if diffs[-1] > 0.01 and len(diffs) < 4000 and sum(d > 0.01 for d in diffs) <= 3:
                            print("mismatch", k, p, pn[i], [(FE, round(a_, 3), round(float(b_), 3)) for FE, a_, b_ in zip(range(33), nnx[0], X[i]) if abs(a_ - b_) > 1e-3])
                if a == "raise":
                    add = amt - bets[s]; stacks[s] -= add; bets[s] = amt; contrib[s] += add; cur = amt
                elif a == "call":
                    stacks[s] -= amt; bets[s] += amt; contrib[s] += amt
                elif a == "fold":
                    folded[s] = True
                history.append({"seat": s, "street": street, "action": a, "amount": amt})
        shown = {k: h["hole"][k] for k in h.get("showdown", {}) if k in h["hole"]}
        ag.on_hand_end({"hand_number": h["n"], "board": h["board"], "shown": shown, "winners": [], "stacks": [2000 + r for r in h["results"]], "history": history})
d = np.array(diffs)
print("our bets checked", len(d), "of", len(key), " max input diff %.4f  max prob diff %.4f  mean %.5f  over 0.01: %d" % (xd, d.max(), d.mean(), (d > 0.01).sum()))
