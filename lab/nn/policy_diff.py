"""How the net changes what the bot does: replay both bots through our real postflop spots with nothing to call."""
import glob, json, os, random, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

def one(f):
    data = json.load(open(f)); res = []
    for path in sys.argv[1:3]:
        random.seed(1)
        out, ag = replay.replay(data, replay.load(os.path.abspath(path)))
        res.append([(d["n"], d["street"], d["bot"], (d["bot_amt"] or 0), d["pot"], d["max_to"]) for d in out if d["to_call"] == 0 and d["street"] != "preflop"])
    return res

if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(HERE, "../../hands/*.json")))
    with Pool() as p:
        allr = p.map(one, files)
    for i, name in enumerate(("old", "new")):
        rows = [r for x in allr for r in x[i]]
        bets = [r for r in rows if r[2] == "raise"]
        fr = [min(r[3], r[5]) / float(r[4]) for r in bets]
        b = [sum(1 for v in fr if lo <= v < hi) for lo, hi in ((0, .5), (.5, .95), (.95, 1.6), (1.6, 99))]
        print("%s: spots %d  bets %.1f%%  sizes small/medium/big/overbet %s  avg bet %.2f pot" % (name, len(rows), 100.0 * len(bets) / len(rows), [round(100.0 * v / len(rows), 1) for v in b], sum(fr) / len(fr)))
    same = sum(1 for x in allr for a, b in zip(x[0], x[1]) if a[2] == b[2]); tot = sum(len(x[0]) for x in allr)
    print("same check/bet choice in %.1f%% of spots" % (100.0 * same / tot))
