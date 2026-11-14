"""Analyser: turns downloaded hand histories into opponent profiles, a leak report and bot config.

    python3 analyse.py hands/                 # full report + writes config.json and replicas.json
    python3 analyse.py hands/ --schema        # just show what the downloaded files look like
    python3 analyse.py hands/ --last 6        # only the most recent 6 rounds

Then:  python3 build.py ../bot.py   to bake config.json into a fresh bot.py.
"""
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evalcore import cls, ev  # noqa: E402

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: RANKS.index(r) * 4 + SUITS.index(s) for r in RANKS for s in SUITS}
PCT = json.load(open(os.path.join(HERE, "tables.json")))["pct"]
POS = {0: "BB", 1: "SB", 2: "BTN", 3: "CO", 4: "HJ", 5: "LJ", 6: "UTG+1", 7: "UTG"}


def first(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def seat_names(data, n):
    raw = first(data, ["names", "teams", "seats", "players", "bots"]) or first(data.get("round", {}), ["names", "teams", "seats", "players"])
    out = [None] * n
    if isinstance(raw, list):
        for i, x in enumerate(raw[:n]):
            if isinstance(x, dict):
                seat = x.get("seat", i)
                nm = first(x, ["team", "name", "team_name", "label", "bot"])
                ver = first(x, ["version", "bot_version", "v"])
                if isinstance(seat, int) and seat < n:
                    out[seat] = "%s%s" % (nm, " v%s" % ver if ver is not None else "")
            else:
                out[i] = str(x)
    elif isinstance(raw, dict):
        for k, x in raw.items():
            try:
                out[int(k)] = str(first(x, ["team", "name"]) if isinstance(x, dict) else x)
            except (ValueError, IndexError):
                pass
    return out


def hole_of(hand):
    return first(hand, ["hole", "hole_cards", "cards", "shown"], {}) or {}


def my_seat(data, hands):
    s = first(data, ["seat", "my_seat", "you"])
    if s is None:
        s = first(data.get("round", {}), ["seat", "my_seat"])
    if isinstance(s, int):
        return s
    cnt = defaultdict(int)
    for h in hands:
        hc = hole_of(h)
        if isinstance(hc, dict):
            for k in hc:
                cnt[int(k)] += 1
    return max(cnt, key=cnt.get) if cnt else 0


class Stat:
    def __init__(self):
        self.d = defaultdict(float)

    def rate(self, a, b):
        return self.d[a] / self.d[b] if self.d[b] else float("nan")


def walk(hand, n, me, S, leaks, ref):
    """Replay one hand, updating per-seat stats S[seat] and our own leak buckets."""
    ev_list = hand["events"]
    bb = first(hand, ["bb", "big_blind"], 20)
    button = first(hand, ["button"], 0)
    bets = [0] * n
    pot = 0
    cur = 0
    street = "preflop"
    L = 0
    vp, pr, agg, jam, saw_flop = set(), set(), set(), set(), set()
    folded = set()
    inpost = set()
    opener = -1
    opener_done = False
    sizes = defaultdict(set)
    my_line = []
    my_first = None
    for e in ev_list:
        kind = e[0]
        if kind == "post":
            _, s, amt = e
            bets[s] = amt
            pot += amt
            cur = max(cur, amt)
        elif kind == "board":
            street = e[1]
            bets = [0] * n
            cur = 0
            if street == "flop":
                saw_flop = set(range(n)) - folded
        elif kind == "act":
            _, s, a, amt = e
            amt = amt or 0
            st = S[s].d
            tc = cur - bets[s]
            if street == "preflop":
                if L >= 1:
                    st["tbo"] += 1
                    if a == "raise":
                        st["tb"] += 1
                    if L == 1 and s != opener:
                        st["fro"] += 1
                        if a == "fold":
                            st["frf"] += 1
                    elif L == 2 and s == opener and not opener_done:
                        opener_done = True
                        st["f3o"] += 1
                        if a == "fold":
                            st["f3f"] += 1
                if a == "raise":
                    vp.add(s)
                    pr.add(s)
                    L += 1
                    if L == 1:
                        opener = s
                    if amt >= 40 * bb:
                        jam.add(s)
                    else:
                        st["open_sz"] += amt / bb
                        st["open_n"] += 1
                elif a == "call":
                    vp.add(s)
                if s == me and my_first is None:
                    my_first = ("open" if L == 1 else "3bet+") if a == "raise" else (a if L == 0 or a == "fold" else "call-raise")
                    if a == "fold":
                        my_first = "fold"
            else:
                if tc > 0:
                    st["fb"] += 1
                    if a == "fold":
                        st["fd"] += 1
                    before = pot - tc
                    fr_ = tc / float(before) if before > 0 else 1.0
                    kb = 0 if fr_ < 0.5 else (1 if fr_ < 0.95 else (2 if fr_ < 1.6 else 3))
                    stg = 1 if s in inpost else 0
                    st["fb_%d_%d" % (stg, kb)] += 1
                    if a == "fold":
                        st["fd_%d_%d" % (stg, kb)] += 1
                    if tc >= 0.8 * pot:
                        st["bigf"] += 1
                        if a != "fold":
                            st["bigc"] += 1
                else:
                    st["chk_opp"] += 1
                    if a == "raise":
                        st["bet_when_checked"] += 1
                if a == "raise":
                    st["ag"] += 1
                    agg.add(s)
                    base = pot + tc
                    frac = (amt - cur) / base if base > 0 else 1.0
                    st["bet_frac"] += frac
                    st["bet_n"] += 1
                    sizes[s].add(0 if frac < 0.5 else (1 if frac < 0.95 else 2))
                elif a in ("call", "check"):
                    st["pa"] += 1
                if a in ("raise", "call"):
                    inpost.add(s)
            if s == me:
                my_line.append(street[0] + a[0])
            if a == "raise":
                pot += amt - bets[s]
                bets[s] = amt
                cur = amt
            elif a == "call":
                pot += amt
                bets[s] += amt
            elif a == "fold":
                folded.add(s)
    results = first(hand, ["results", "result", "delta"])
    if results is None and "end" in hand and "stacks" in hand:
        results = [a - b for a, b in zip(hand["end"], hand["stacks"])]
    board = [CARD[c] for c in first(hand, ["board"], []) if c in CARD]
    hc = hole_of(hand)
    shown = {}
    if isinstance(hc, dict):
        for k, v in hc.items():
            if v and len(v) == 2 and v[0] in CARD:
                shown[int(k)] = [CARD[v[0]], CARD[v[1]]]
    bcat = (ev(board) >> 26) if len(board) == 5 else -1
    live = set(range(n)) - folded
    for s in range(n):
        st = S[s].d
        st["n"] += 1
        st["vpip"] += s in vp
        st["pfr"] += s in pr
        st["jam"] += s in jam
        st["flop"] += s in saw_flop
        if results:
            st["chips"] += results[s]
        if s in live and len(live) > 1 and len(board) == 5:
            st["sd"] += 1
            if results and results[s] > 0:
                st["sd_won"] += 1
        if s in shown and s != me:
            p = PCT[cls(*shown[s])]
            if s in pr:
                st["sr_n"] += 1
                st["sr_s"] += p
            elif s in vp:
                st["sc_n"] += 1
                st["sc_s"] += p
            if s in agg and bcat >= 0:
                st["an"] += 1
                weak = (ev(board + shown[s]) >> 26) <= bcat
                st["aw"] += weak
                for kb in sizes[s]:
                    key = ("small", "mid", "big")[kb]
                    st["sz_%s_n" % key] += 1
                    st["sz_%s_weak" % key] += weak
    if results is not None and me is not None:
        r = results[me]
        nb = (button + 2 - me) % n
        leaks["position"][POS.get(nb, str(nb))].append(r)
        leaks["first preflop action"][my_first or "none"].append(r)
        last = "preflop"
        for x in my_line:
            last = {"p": "preflop", "f": "flop", "t": "turn", "r": "river"}[x[0]]
        if my_first != "fold":
            leaks["last street we acted on (hands played)"][last].append(r)
            sd = me in live and len(live) > 1 and len(board) == 5
            leaks["showdown"]["went to showdown" if sd else ("we folded later" if me in folded else "won without showdown")].append(r)
        mine = shown.get(me)
        leaks["_hands"].append((r, ref, first(hand, ["n", "hand_number", "hand"], "?"),
                                "".join(RANKS[c >> 2] + SUITS[c & 3] for c in mine) if mine else "??", " ".join(my_line)))


def label(st):
    r = st.rate
    vp, pf, ftb, jam = r("vpip", "n"), r("pfr", "n"), r("fd", "fb"), r("jam", "n")
    af = st.d["ag"] / max(1.0, st.d["ag"] + st.d["pa"])
    if jam > 0.10:
        return "shover"
    if vp > 0.60 and pf < 0.12 and (ftb != ftb or ftb < 0.15):
        return "station"
    if vp > 0.55 and pf > 0.25:
        return "maniac/random"
    if vp < 0.10:
        return "nit"
    if vp > 0.40:
        return "loose-passive" if af < 0.3 else "loose-aggressive"
    if pf / max(vp, 1e-9) > 0.6:
        return "tight-aggressive"
    return "tight-passive"


def fmt(x, pct=True):
    if x != x:
        return "   - "
    return "%4.0f%%" % (100 * x) if pct else "%5.2f" % x


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = args[0] if args else "hands"
    files = sorted(glob.glob(os.path.join(folder, "*.json")), key=os.path.getmtime)
    if "--last" in sys.argv:
        files = files[-int(sys.argv[sys.argv.index("--last") + 1]):]
    if not files:
        sys.exit("No .json files in %s. Run fetch_hands.py first." % folder)
    if "--schema" in sys.argv:
        d = json.load(open(files[-1]))
        print("top-level keys:", {k: type(v).__name__ for k, v in d.items()})
        print("round:", json.dumps(d.get("round"))[:600])
        print("first hand:", json.dumps(d["hands"][0])[:1500])
        return

    leaks = defaultdict(lambda: defaultdict(list))
    leaks["_hands"] = []
    rows = []
    byname = defaultdict(Stat)
    me_total = Stat()
    for f in files:
        d = json.load(open(f))
        hands = d.get("hands", [])
        if not hands:
            continue
        n = len(first(hands[0], ["stacks", "results", "end"], [0] * 8))
        me = my_seat(d, hands)
        names = seat_names(d, n)
        ref = first(d.get("round", {}), ["ref"], os.path.basename(f))
        S = [Stat() for _ in range(n)]
        for h in hands:
            try:
                walk(h, n, me, S, leaks, ref)
            except Exception as ex:  # one malformed hand shouldn't kill the report
                leaks["_bad"]["x"].append(repr(ex))
        for s in range(n):
            tgt = me_total if s == me else byname[names[s]] if names[s] else None
            if tgt is not None:
                for k, v in S[s].d.items():
                    tgt.d[k] += v
            if s != me:
                rows.append((ref, s, names[s], S[s]))

    def line(tag, st):
        r = st.rate
        d = st.d
        af = d["ag"] / max(1.0, d["ag"] + d["pa"])
        return "%-34s %5d %+8.1f %s %s %s %s %s %s %s %s %s  %s" % (
            tag[:34], d["n"], d["chips"] / 20 / max(d["n"], 1) * 100,
            fmt(r("vpip", "n")), fmt(r("pfr", "n")), fmt(r("tb", "tbo")), fmt(r("jam", "n")),
            fmt(af), fmt(r("fd", "fb")), fmt(r("bigc", "bigf")), fmt(r("sd", "flop")), fmt(r("aw", "an")), label(st))

    head = "%-34s %5s %8s %5s %5s %5s %5s %5s %5s %5s %5s %5s  %s" % (
        "who", "hands", "bb/100", "VPIP", "PFR", "3bet", "jam", "agg", "f2bet", "cBig", "WTSD", "bluff", "type")
    print("\n== US ==\n" + head)
    print(line("our bot (%d rounds)" % len(files), me_total))
    if byname:
        print("\n== OPPONENTS BY TEAM (all rounds) ==\n" + head)
        for nm, st in sorted(byname.items(), key=lambda x: -x[1].d["chips"] / max(x[1].d["n"], 1)):
            print(line(nm, st))
    print("\n== OPPONENTS BY SEAT, latest rounds ==\n" + head)
    for ref, s, nm, st in rows[-7 * 4:]:
        print(line("%s s%d %s" % (str(ref)[-14:], s, nm or ""), st))

    types = defaultdict(int)
    for _, _, _, st in rows:
        types[label(st)] += 1
    print("\n== FIELD MIX (opponent seat-rounds) ==")
    for k, v in sorted(types.items(), key=lambda x: -x[1]):
        print("  %-18s %3d  %4.0f%%" % (k, v, 100.0 * v / len(rows)))

    print("\n== BET SIZE TELLS (share of showdowns where the bettor had nothing beyond the board) ==")
    src = byname.items() if byname else [("all opponents", Stat())]
    if not byname:
        for _, _, _, st in rows:
            for k, v in st.d.items():
                src[0][1].d[k] += v
    for nm, st in src:
        parts = []
        for key in ("small", "mid", "big"):
            nn = st.d["sz_%s_n" % key]
            if nn >= 5:
                parts.append("%s bets: %.0f%% weak (n=%d)" % (key, 100 * st.d["sz_%s_weak" % key] / nn, nn))
        if parts:
            print("  %-28s %s" % (str(nm)[:28], " | ".join(parts)))

    print("\n== OUR LEAKS (bb/100 by situation; look for big negatives with many hands) ==")
    for group, buckets in leaks.items():
        if group.startswith("_"):
            continue
        print("  " + group)
        for k, v in sorted(buckets.items(), key=lambda x: sum(x[1])):
            print("    %-26s hands %6d   total %+9.0f bb   %+8.1f bb/100" % (k, len(v), sum(v) / 20.0, sum(v) / 20.0 / len(v) * 100))
    worst = sorted(leaks["_hands"])[:12]
    print("  biggest single losses (chips, round, hand, our cards, our line)")
    for r, ref, hn, cards, ln in worst:
        print("    %+6d  %s #%s  %s  %s" % (r, str(ref)[-14:], hn, cards, ln))
    if leaks.get("_bad"):
        print("  (%d hands could not be parsed: %s)" % (len(leaks["_bad"]["x"]), leaks["_bad"]["x"][0]))

    # ---- field priors -> config.json, replica profiles -> replicas.json
    tot = Stat()
    profiles = []
    for ref, s, nm, st in rows:
        for k, v in st.d.items():
            tot.d[k] += v
        d = st.d
        if d["n"] >= 300:
            profiles.append({
                "name": "%s_s%d" % (str(ref).replace("/", "_")[-12:], s), "team": nm, "type": label(st),
                "vpip": round(st.rate("vpip", "n"), 3), "pfr": round(st.rate("pfr", "n"), 3),
                "tb": round(d["tb"] / max(d["tbo"], 1), 3), "jam": round(st.rate("jam", "n"), 3),
                "ftb": round(d["fd"] / max(d["fb"], 1), 3),
                "f3": round((d["f3f"] + 0.63 * 4) / (d["f3o"] + 4), 3),
                "bet": round(d["bet_when_checked"] / max(d["chk_opp"], 1), 3),
                "size": round(d["bet_frac"] / max(d["bet_n"], 1), 2),
                "open": round(d["open_sz"] / max(d["open_n"], 1), 1),
                "bb100": round(d["chips"] / 20 / d["n"] * 100, 1),
            })
    r = tot.rate

    def clamp(x, lo, hi, dflt):
        return dflt if x != x else max(lo, min(hi, x))

    prior = {
        "vpip": round(clamp(r("vpip", "n"), 0.12, 0.6, 0.28), 3),
        "pfr": round(clamp(r("pfr", "n"), 0.06, 0.4, 0.16), 3),
        "tb": round(clamp(r("tb", "tbo"), 0.02, 0.2, 0.06), 3),
        "shove": round(clamp(r("jam", "n"), 0.003, 0.1, 0.01), 3),
        "af": round(clamp(tot.d["ag"] / max(1.0, tot.d["ag"] + tot.d["pa"]), 0.12, 0.6, 0.30), 3),
        "ftb": round(clamp(r("fd", "fb"), 0.15, 0.7, 0.42), 3),
        "cbig": round(clamp(r("bigc", "bigf"), 0.15, 0.8, 0.35), 3),
        "fr": round(clamp(r("frf", "fro"), 0.3, 0.95, 0.78), 3),
        "f3": round(clamp(r("f3f", "f3o"), 0.1, 0.9, 0.5), 3),
    }
    dflt = [[0.37, 0.45, 0.53, 0.61], [0.22, 0.30, 0.38, 0.46]]
    fold_prior = [[round((tot.d["fd_%d_%d" % (g, k)] + dflt[g][k] * 20) / (tot.d["fb_%d_%d" % (g, k)] + 20), 3)
                   for k in range(4)] for g in range(2)]
    bluff_prior = [round((tot.d["sz_%s_weak" % k] + 0.2 * 10) / (tot.d["sz_%s_n" % k] + 10), 3) for k in ("small", "mid", "big")]
    print("\n== FIELD FOLD RATES when facing a bet (rows: first bet of the hand, later bets; cols: <0.5 pot, <0.95, <1.6, bigger) ==")
    for g in range(2):
        print("  " + "   ".join("%4.0f%% (n=%d)" % (100 * fold_prior[g][k], tot.d["fb_%d_%d" % (g, k)]) for k in range(4)))
    print("== FIELD BLUFF RATES at showdown after small / medium / big bets: %s ==" % bluff_prior)
    cfg_path = os.path.join(HERE, "config.json")
    cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
    cfg["DEFAULT_PRIOR"] = prior
    cfg["FOLD_PRIOR"] = fold_prior
    cfg["BLUFF_PRIOR"] = bluff_prior
    json.dump(cfg, open(cfg_path, "w"), indent=1)
    json.dump(profiles, open(os.path.join(HERE, "replicas.json"), "w"), indent=1)
    print("\n== FIELD PRIOR (what an unknown opponent is assumed to be) ==\n  %s" % prior)
    print("\nwrote config.json (prior from %d opponent hands) and replicas.json (%d opponent profiles)" % (tot.d["n"], len(profiles)))
    print("next: python3 build.py ../bot.py   (bakes the new prior in),  python3 tune.py   (retunes PARAMS against replicas)")


if __name__ == "__main__":
    main()
