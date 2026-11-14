"""In-process stress test: our bot (several copies) with house bots. Reports swallowed errors and decision times.

    python selftest.py KIT_DIR [rounds] [copies]
"""
import importlib.util, os, random, sys, time
kit = os.path.abspath(sys.argv[1]); rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
copies = int(sys.argv[3]) if len(sys.argv) > 3 else 3
sys.path.insert(0, kit)
from engine import FixedHandsTable
from engine.players import LocalPlayer

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m.Agent

Bot = load(os.path.join(kit, "bot.py"), "ourbot")
house = [load(os.path.join(kit, "examples", f), f[:-3]) for f in ("tight_aggressive.py", "calling_station.py", "random_bot.py")]
times = []
class Timed(LocalPlayer):
    def act(self, state):
        t = time.perf_counter(); out = super().act(state); times.append((time.perf_counter() - t) * 1000); return out
rng = random.Random(7); tot = 0; errs = 0; worst_used = 0; engine_errs = 0
for r in range(rounds):
    ps = [Timed(Bot) for _ in range(copies)] + [LocalPlayer(rng.choice(house)) for _ in range(8 - copies)]
    order = list(range(8)); rng.shuffle(order); ps = [ps[i] for i in order]
    res = FixedHandsTable(ps, hands=1000, seed=rng.random()).play()
    for i, p in enumerate(ps):
        if isinstance(p, Timed):
            tot += res["chips"][i]; errs += p.agent.errs; worst_used = max(worst_used, p.agent.used); engine_errs += p.stats.errors
            if p.agent.errs: print("ERR", p.agent.last_err)
times.sort()
print("our bots: %+.1f bb/100 avg | swallowed errors %d | engine errors %d" % (tot / 20 / (rounds * copies * 1000) * 100, errs, engine_errs))
print("decisions/round %.0f | ms median %.3f p99 %.3f max %.3f | worst self-timed s/round %.2f" % (
    len(times) / (rounds * copies), times[len(times)//2], times[int(len(times)*0.99)], times[-1], worst_used))
