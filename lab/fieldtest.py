"""Quick check of the current bot against hand-written archetype fields.

    REPLICA_SHARE=1.0 python3 fieldtest.py 8     # replica-only tables, 8 rounds per field
"""
import os, sys, statistics, random
from multiprocessing import Pool
import tune
FIELDS = {
 "TAG field":      [{"vpip":.22,"pfr":.17,"tb":.07,"jam":.01,"ftb":.50,"bet":.50,"size":.65,"open":2.5}],
 "nit field":      [{"vpip":.10,"pfr":.08,"tb":.03,"jam":.005,"ftb":.65,"bet":.35,"size":.6,"open":3}],
 "LAG field":      [{"vpip":.38,"pfr":.30,"tb":.14,"jam":.03,"ftb":.35,"bet":.75,"size":.8,"open":3}],
 "loose-passive":  [{"vpip":.55,"pfr":.06,"tb":.02,"jam":.0,"ftb":.25,"bet":.25,"size":.5,"open":3}],
 "shover field":   [{"vpip":.30,"pfr":.25,"tb":.10,"jam":.20,"ftb":.40,"bet":.5,"size":.7,"open":3}],
 "mixed":          None,
}
if __name__ == "__main__":
    m = tune._bot_module(); P = dict(m.PARAMS); P["open_scale"] = 1.0
    allp = [v[0] for v in FIELDS.values() if v]
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    for name, profs in FIELDS.items():
        profs = profs or allp
        # force replicas only: play() mixes in 20% house bots, acceptable for a smoke test
        with Pool() as pool:
            r = pool.map(tune.play, [(P, 50 + s, profs) for s in range(n)])
        print("%-15s %+8.1f bb/100  (+- %.0f)" % (name, statistics.mean(r), statistics.stdev(r) / n ** 0.5))
