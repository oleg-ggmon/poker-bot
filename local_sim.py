"""Run your bot against other bots on your own machine, in the tournament format.

    python local_sim.py                          # bot.py vs house bots, 5 rounds of 1,000 hands
    python local_sim.py --rounds 20
    python local_sim.py bot.py examples/tight_aggressive.py
    python local_sim.py --show-prints --rounds 1 --hands 20   # see your bot's print() output

Every bot runs in its own process with the same limits the tournament uses
(10 ms per decision, 10 s time bank per round), so what you see here is what
you'll get on the day.
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import FixedHandsTable  # noqa: E402
from engine.players import SubprocessPlayer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HOUSE = ["examples/tight_aggressive.py", "examples/calling_station.py", "examples/random_bot.py"]
SEATS = 8
BIG_BLIND = 20


def resolve(path):
    """Find a bot file given relative to where you are or to the kit folder."""
    for cand in (os.path.abspath(path), os.path.join(HERE, path)):
        if os.path.isfile(cand):
            return cand
    sys.exit("Can't find bot file: %s" % path)


def label(path):
    rel = os.path.relpath(path, HERE)
    return os.path.basename(path) if rel.startswith("..") else rel


def check_loads(path):
    """Start the bot once so a broken file stops the run instead of scoring."""
    p = SubprocessPlayer(path)
    try:
        p.start_table(0, {"seat": 0, "num_players": SEATS, "format": "fixed_hands", "hands": 1000,
                          "starting_stack": 2000, "stacks_reset_each_hand": True,
                          "small_blind": 10, "big_blind": 20, "betting": "no_limit", "raise_cap": None})
        if p.load_error:
            sys.exit("\n%s failed to load:\n\n%s" % (label(path), p.load_error))
    finally:
        p.close()


def main():
    ap = argparse.ArgumentParser(description="Play bots against each other locally.")
    ap.add_argument("bots", nargs="*", default=["bot.py"],
                    help="bot files (default: bot.py). Empty seats are filled with house bots.")
    ap.add_argument("--rounds", type=int, default=5, help="rounds to play (a new table each round)")
    ap.add_argument("--hands", type=int, default=1000, help="hands per round (tournament: 1000)")
    ap.add_argument("--timeout", type=float, default=10.0, help="ms per decision (tournament: 10)")
    ap.add_argument("--bank", type=float, default=10.0,
                    help="seconds of thinking per bot per round (tournament: 10)")
    ap.add_argument("--seed", type=int, default=None, help="fix the cards so runs repeat")
    ap.add_argument("--betting", choices=["no_limit", "pot_limit", "fixed_limit"], default="no_limit")
    ap.add_argument("--raise-cap", type=int, default=0, help="max bets/raises per street, 0 = none")
    ap.add_argument("--show-prints", action="store_true",
                    help="show print() output from the bots you named (house bots stay quiet)")
    args = ap.parse_args()

    bots = [resolve(b) for b in args.bots]
    if len(set(bots)) != len(bots):
        sys.exit("Each bot file can only be named once. To play two copies, copy the file.")
    if len(bots) > SEATS:
        sys.exit("A table seats %d bots; you named %d." % (SEATS, len(bots)))
    for b in bots:
        check_loads(b)

    show = set(bots) if args.show_prints else set()
    config = {"betting": args.betting, "raise_cap": args.raise_cap}
    rng = random.Random(args.seed)
    # chips, hands, timeouts, errors, bank_out, worst round ms, error shown yet
    totals = {b: [0, 0, 0, 0, 0, 0.0, False] for b in bots}
    t0 = time.time()

    for r in range(args.rounds):
        seats = list(bots)
        while len(seats) < SEATS:
            seats.append(os.path.join(HERE, rng.choice(HOUSE)))
        rng.shuffle(seats)
        players = [SubprocessPlayer(p, timeout_ms=args.timeout, bank_ms=args.bank * 1000,
                                    stderr_path="inherit" if p in show else None) for p in seats]
        try:
            res = FixedHandsTable(players, hands=args.hands, config=config, seed=rng.random()).play()
        finally:
            for p in players:
                p.close()
        for i, path in enumerate(seats):
            if path not in totals:
                continue
            tot, st = totals[path], players[i].stats
            tot[0] += res["chips"][i]
            tot[1] += res["hands"]
            tot[2] += st.timeouts
            tot[3] += st.errors
            tot[4] += st.bank_out
            tot[5] = max(tot[5], st.total_ms)
            if st.error_samples and not tot[6]:
                tot[6] = True
                print("\n--- first error from %s (later ones are only counted) ---\n%s"
                      % (label(path), st.error_samples[0]))
        if not show:
            print("\rround %d/%d" % (r + 1, args.rounds), end="", flush=True)

    print("\n\n%-28s %10s %9s %8s %7s %9s %10s" % (
        "bot", "chips", "bb/100", "timeouts", "errors", "bank out", "think s/rd"))
    for b, (chips, hands, to, er, bo, worst, _) in totals.items():
        bb100 = chips / BIG_BLIND / max(hands, 1) * 100
        print("%-28s %+10d %+9.1f %8d %7d %9d %10.1f" % (label(b), chips, bb100, to, er, bo, worst / 1000))
    print("\n%.1fs elapsed. 'think s/rd' is your bot's worst round of thinking time; "
          "the bank is %.0f s." % (time.time() - t0, args.bank))


if __name__ == "__main__":
    main()
