"""Download every hand your team has played in the AI Poker Bots tournament.

    python fetch_hands.py --token YOUR-DATA-TOKEN

Your data token is on the AI Poker Bots page, under "Your table's data", once you're
logged in. It reads your own team's results and nothing else; don't share it.

Saves one JSON file per round in hands/, skipping rounds you already have. Each hand
has every action at your table, the board, every seat's chip result ("results"), your
own cards, and opponents' cards only when they reached showdown.

Event format (in "events"):
    ["post", seat, amount]                 blind posted
    ["act", seat, action, amount]          fold / check / call (chips added) / raise (raise-to total)
    ["board", street, cards]               flop / turn / river, all board cards so far
    ["refund", seat, amount]               uncalled bet returned
    ["win", seat, amount, hand_name]       chips won (hand_name is null if everyone else folded)
"""
import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def get(site, path, token):
    req = urllib.request.Request(site.rstrip("/") + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error")
        except Exception:
            msg = None
        raise SystemExit("%s: %s" % (e.code, msg or e.reason))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--token", required=True, help="your team's data token from the AI Poker Bots page")
    ap.add_argument("--site", default="https://imperialaihack.com")
    ap.add_argument("--out", default="hands")
    a = ap.parse_args()
    res = get(a.site, "/api/poker/results", a.token)
    rounds = res.get("rounds", [])
    os.makedirs(a.out, exist_ok=True)
    new = 0
    for rd in rounds:
        dest = os.path.join(a.out, rd["ref"].replace("/", "_") + ".json")
        if os.path.exists(dest):
            continue
        data = get(a.site, "/api/poker/hands?ref=" + urllib.parse.quote(rd["ref"]), a.token)
        data["round"] = rd
        with open(dest, "w") as f:
            json.dump(data, f)
        new += 1
        print("saved", dest, "(%d hands, %+d chips)" % (len(data["hands"]), rd["chips"]))
    print("%s: %d new round(s); %d in %s/" % (res.get("team", "your team"), new, len(rounds), a.out))


if __name__ == "__main__":
    main()
