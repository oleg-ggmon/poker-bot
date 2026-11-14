"""A/B test two bot files at the same tables against a realistic mixed field, on duplicate deals.

    python3 ab.py versions/bot_v1.py ../bot.py 40        # old, new, number of deals (each played twice)

Every deal is played twice with the two bots' seats swapped, so both get the same cards in the same
seat against the same opponents. Prints new-minus-old in bb/100 with its standard error.
"""
import importlib.util
import os
import random
import statistics
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE) if os.path.isdir(os.path.join(os.path.dirname(HERE), "engine")) else os.environ.get("KIT", "")
sys.path.insert(0, HERE)
sys.path.insert(0, KIT)

ARCH = [
    {"vpip": .22, "pfr": .17, "tb": .07, "jam": .01, "ftb": .50, "bet": .50, "size": .65, "open": 2.5},
    {"vpip": .10, "pfr": .08, "tb": .03, "jam": .005, "ftb": .65, "bet": .35, "size": .6, "open": 3},
    {"vpip": .38, "pfr": .30, "tb": .14, "jam": .03, "ftb": .35, "bet": .75, "size": .8, "open": 3},
    {"vpip": .55, "pfr": .06, "tb": .02, "jam": .0, "ftb": .25, "bet": .25, "size": .5, "open": 3},
    {"vpip": .30, "pfr": .25, "tb": .10, "jam": .15, "ftb": .40, "bet": .5, "size": .7, "open": 3},
]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def field(rng, weak):
    """Six opponents: mostly equity-style bots, plus replicas, the starter bot and house bots."""
    import repcore
    eq = _load(os.path.join(HERE, "testbots", "equity_bot.py"), "eqbot")
    starter = _load(os.path.join(HERE, "testbots", "starter.py"), "starter").Agent
    house = [_load(os.path.join(KIT, "examples", f), f[:-3]).Agent
             for f in ("tight_aggressive.py", "calling_station.py", "random_bot.py")]
    named = {"eq": eq.Agent, "eq_loose": eq.Loose, "eq_tight": eq.Tight, "eq_aggro": eq.Aggro, "starter": starter,
             "house_tag": house[0], "station": house[1], "random": house[2],
             "rep_tag": repcore.make(ARCH[0]), "rep_nit": repcore.make(ARCH[1]), "rep_lag": repcore.make(ARCH[2]),
             "rep_passive": repcore.make(ARCH[3]), "rep_shover": repcore.make(ARCH[4])}
    sh = _load(os.path.join(HERE, "testbots", "allin.py"), "shovers")
    named.update({"allin": sh.Agent, "allin30": sh.Top30, "allin10": sh.Top10})
    if weak == "real":  # replicas of the opponents measured in the real rounds (analyse.py -> replicas.json)
        import json
        profs = json.load(open(os.path.join(HERE, "replicas.json")))
        return [repcore.make(rng.choice(profs)) for _ in range(6)]
    if isinstance(weak, str):
        if "+" in weak:  # e.g. allin+eq : one of the first type, the rest of the second
            a_, b_ = weak.split("+")
            return [named[a_]] + [named[b_]] * 5
        return [named[weak]] * 6
    pool = [eq.Agent, eq.Loose, eq.Tight, eq.Aggro, starter, house[0]] + [repcore.make(a) for a in ARCH]
    if weak:
        pool += [house[1], house[2]]
    return [rng.choice(pool) for _ in range(6)]


def deal(job):
    old_path, new_path, seed, weak = job
    from engine import FixedHandsTable
    from engine.players import LocalPlayer
    old = _load(old_path, "old_bot").Agent
    new = _load(new_path, "new_bot").Agent
    rng = random.Random(seed)
    opps = field(rng, weak)
    order = list(range(8))
    rng.shuffle(order)
    out = []
    for swap in (0, 1):
        seats = ([new, old] if not swap else [old, new]) + opps
        random.seed(seed * 2 + swap)
        res = FixedHandsTable([LocalPlayer(seats[i]) for i in order], hands=1000, seed=seed).play()
        a, b = res["chips"][order.index(0)], res["chips"][order.index(1)]
        out.append((a, b) if not swap else (b, a))
    new_c = (out[0][0] + out[1][0]) / 2.0
    old_c = (out[0][1] + out[1][1]) / 2.0
    return new_c / 200.0, old_c / 200.0  # bb/100


def main():
    old_path, new_path = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    weak = "--weak" in sys.argv
    if "--field" in sys.argv:
        weak = sys.argv[sys.argv.index("--field") + 1]
    first = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 0
    with Pool() as pool:
        res = pool.map(deal, [(old_path, new_path, 500 + first + i, weak) for i in range(n)])
    new = [r[0] for r in res]
    old = [r[1] for r in res]
    diff = [a - b for a, b in zip(new, old)]
    se = statistics.stdev(diff) / n ** 0.5 if n > 1 else float("nan")
    print("field: %s | %d deals x2 | old %+.1f  new %+.1f  | new-old %+.1f +- %.1f bb/100 %s" % (
        weak if isinstance(weak, str) else ("with stations/random" if weak else "no free money"), n, statistics.mean(old), statistics.mean(new),
        statistics.mean(diff), se, "(significant)" if abs(statistics.mean(diff)) > 2 * se else "(within noise)"))


if __name__ == "__main__":
    main()
