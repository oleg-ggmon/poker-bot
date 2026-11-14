"""Tuner: hill-climbs PARAMS against a field of replica opponents + house bots, using paired deals.

    python3 tune.py                 # one sweep over all parameters, 8 paired rounds per candidate
    python3 tune.py --seeds 16      # steadier, slower
    python3 tune.py --only value,raise,call_margin

Each candidate is compared with the current best on the SAME cards and the SAME opponents; a change is
kept only if it wins by more than 2 standard errors. Result goes to config.json; then run build.py.
"""
import importlib.util
import json
import os
import random
import statistics
import sys
import tempfile
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE) if os.path.isdir(os.path.join(os.path.dirname(HERE), "engine")) else os.environ.get("KIT", "")
sys.path.insert(0, HERE)
sys.path.insert(0, KIT)

TUNABLE = {  # name: (step, low, high)
    "value": (0.03, 0.50, 0.75), "raise": (0.04, 0.62, 0.92), "call_margin": (0.02, -0.02, 0.12),
    "early_margin": (0.02, 0.0, 0.10), "bet_med": (0.12, 0.3, 1.2), "bet_big": (0.15, 0.4, 1.5),
    "cbet_freq": (0.25, 0.0, 1.0), "bluff_edge": (0.05, 0.0, 0.3), "tb_frac": (0.05, 0.08, 0.5),
    "call_frac": (0.15, 0.3, 1.5), "allin_margin": (0.02, -0.02, 0.12), "open_bb": (0.5, 2.0, 5.0),
    "open_scale": (0.15, 0.5, 1.6),
}
_mod = None
REPLICA_SHARE = float(os.environ.get("REPLICA_SHARE", "0.8"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _bot_module():
    global _mod
    if _mod is None:
        fd, tmp = tempfile.mkstemp(suffix=".py")
        os.close(fd)
        os.system('"%s" "%s" "%s" > %s' % (sys.executable, os.path.join(HERE, "build.py"), tmp, os.devnull))
        _mod = _load(tmp, "tunebot")
        os.remove(tmp)
    return _mod


def apply(params):
    p = dict(params)
    sc = p.pop("open_scale", 1.0)
    p["open"] = [min(0.95, x * sc) for x in p["open"]]
    return p


def play(job):
    params, seed, profiles = job
    from engine import FixedHandsTable
    from engine.players import LocalPlayer
    import repcore
    mod = _bot_module()
    mod.PARAMS = apply(params)
    rng = random.Random(seed)
    house = [_load(os.path.join(KIT, "examples", f), f[:-3]).Agent for f in ("tight_aggressive.py", "calling_station.py", "random_bot.py")]
    opps = []
    for _ in range(7):
        if profiles and rng.random() < REPLICA_SHARE:
            opps.append(repcore.make(rng.choice(profiles)))
        else:
            opps.append(rng.choice(house))
    seats = [mod.Agent] + opps
    order = list(range(8))
    rng.shuffle(order)
    random.seed(seed)
    res = FixedHandsTable([LocalPlayer(seats[i]) for i in order], hands=1000, seed=seed).play()
    return res["chips"][order.index(0)] / 20.0 / 10.0  # bb/100


def main():
    nseeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 8
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else list(TUNABLE)
    cfg_path = os.path.join(HERE, "config.json")
    if os.path.exists(cfg_path):
        cfg = json.load(open(cfg_path))
    else:
        m = _bot_module()
        cfg = {"PARAMS": dict(m.PARAMS), "DEFAULT_PRIOR": dict(m.DEFAULT_PRIOR)}
    best = dict(cfg["PARAMS"])
    best.setdefault("open_scale", 1.0)
    rp = os.path.join(HERE, "replicas.json")
    profiles = json.load(open(rp)) if os.path.exists(rp) else []
    print("field: %d replica profiles + house bots | %d paired rounds per candidate" % (len(profiles), nseeds))
    seeds = [1000 + i for i in range(nseeds)]
    with Pool() as pool:
        base = pool.map(play, [(best, s, profiles) for s in seeds])
        print("baseline %+.1f bb/100" % statistics.mean(base))
        for name in only:
            step, lo, hi = TUNABLE[name]
            for sign in (1, -1):
                cand = dict(best)
                cand[name] = round(min(hi, max(lo, best[name] + sign * step)), 4)
                if cand[name] == best[name]:
                    continue
                res = pool.map(play, [(cand, s, profiles) for s in seeds])
                diff = [a - b for a, b in zip(res, base)]
                mean = statistics.mean(diff)
                se = statistics.stdev(diff) / len(diff) ** 0.5 if len(diff) > 1 else 1e9
                keep = mean > 2 * se and mean > 3
                print("%-13s %7.3f -> %7.3f   diff %+7.1f +- %5.1f  %s" % (name, best[name], cand[name], mean, se, "KEEP" if keep else ""))
                if keep:
                    best, base = cand, res
                    break
    out = apply(best)
    out["open_scale"] = 1.0
    cfg["PARAMS"] = out
    json.dump(cfg, open(cfg_path, "w"), indent=1)
    print("final %+.1f bb/100 on the tuning field. wrote config.json; now run: python3 build.py ../bot.py" % statistics.mean(base))


if __name__ == "__main__":
    main()
