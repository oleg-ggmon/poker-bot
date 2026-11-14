# AlgoSoc Pokerbots — Starter Kit

```
bot.py                 your bot (edit this, upload this)
fetch_hands.py         download your team's hand histories from the site
local_sim.py           play your bot against others locally
examples/              house bots to test against
engine/                the exact engine the tournament runs
```

## Quick start

Needs Python 3.9 or later and nothing else. Works on Windows, macOS and Linux
(use `py` or `python3` instead of `python` if that's how Python runs on your machine).

```bash
python local_sim.py                                   # bot.py vs house bots, 5 rounds of 1,000 hands
python local_sim.py --rounds 20                       # more rounds, steadier numbers
python local_sim.py bot.py examples/tight_aggressive.py
python local_sim.py --show-prints --rounds 1 --hands 20   # see what your bot print()s
python local_sim.py --seed 42                         # same cards every run
```

Empty seats are filled with random house bots, up to eight. You get a table
like this at the end:

```
bot                               chips    bb/100 timeouts  errors  bank out think s/rd
bot.py                          +351732    +879.3        0       0         0        0.2
```

`chips` is what your bot won over all rounds and `bb/100` is the same per 100
hands, in big blinds: the number the leaderboard ranks on. `timeouts`,
`errors` and `bank out` count decisions your bot missed. `think s/rd` is your
worst round of thinking time; keep it well under the 10 s bank. The first error
from each bot is printed in full.

**How good is good?** Folding every hand loses the blinds, about −19 bb/100
at an eight-bot table. The house bots are weak, so a decent bot should be well
above zero against them.

## Your bot

Upload a single file, `bot.py`, on the AI Poker Bots page. It may only import the
Python standard library. Keep the class name `Agent`: the platform imports it.

### The sandbox

On the platform every bot runs in its own sealed container: Python 3.12, no
internet, no files except its own `bot.py` (read-only), a small `/tmp` wiped
every round, 512 MB of memory, 32 processes and one CPU core. Nothing carries
over between rounds. Using lots of CPU when it isn't your turn, running out of
memory, crashing, or flooding the dealer stops your bot for the rest of that
round (it checks or folds) and flags it for the organisers. Trying to get round
the sandbox, or colluding with another team, is cheating and gets you removed.

A fresh `Agent()` is made for every table in every round, so anything you
store on `self` lasts one round of 1,000 hands, with the same opponents. Three methods are called:

| method | when | required |
|---|---|---|
| `on_table_start(info)` | once, before the first hand | no |
| `act(state)` | every time it's your turn | **yes** |
| `on_hand_end(summary)` | after every hand | no |

`act(state)` returns one of:

```python
{"action": "fold"}
{"action": "check"}
{"action": "call"}
{"action": "raise", "amount": 200}   # raise TO 200 this street (your total bet)
{"action": "all_in"}                 # raise to your whole stack
```

`state["legal_actions"]` lists which of `fold`, `check`, `call`, `raise` you
may use right now. `all_in` never appears in it: it counts as a raise when
raising is allowed, and as a call when it isn't.

### What happens if you get it wrong

You always get *some* action. Nothing crashes the table.

| you return | what the engine does |
|---|---|
| a raise below `min_raise_to` or above `max_raise_to` | raises to the nearest legal amount |
| `raise` or `all_in` when raising isn't allowed | calls (or checks if nothing to call) |
| `call` with nothing to call | checks |
| `check` when there's a bet to call | **folds** |
| anything else, an error, or no answer within the time limit | checks if it can, otherwise **folds** |

### Your table's data

After each round the AI Poker Bots page shows every hand you played: every
action at the table, the board, every seat's chip result, your own cards, and
opponents' cards only when they reached showdown. Nothing about other bots'
hidden cards, code or timing. To download all of it for analysis, copy your
team's data token from the page (under "Your table's data") and run:

```bash
python fetch_hands.py --token YOUR-DATA-TOKEN
```

One team has one live bot: each upload replaces your previous version from
the next round on, and each person can be in only one team (up to 4 people).

### Cards

Two-character strings: rank then suit. Ranks `23456789TJQKA` (`T` is ten),
suits `c d h s`. For example `"As"` is the ace of spades, `"Td"` the ten of diamonds.

### `state` (passed to `act`)

| field | example | meaning |
|---|---|---|
| `hole_cards` | `["As", "Kd"]` | your two cards |
| `board` | `["7h", "2c", "Js"]` | community cards so far (0, 3, 4 or 5) |
| `street` | `"flop"` | `preflop`, `flop`, `turn` or `river` |
| `seat` | `3` | your seat; index into `stacks`, `bets`, `folded` |
| `button` | `5` | dealer seat |
| `stacks` | `[1980, 0, ...]` | chips each seat has left, not counting bets in front of them |
| `bets` | `[0, 0, 40, ...]` | what each seat has put in **this street** |
| `folded` | `[false, true, ...]` | who has folded (busted seats show `true`) |
| `pot` | `130` | all chips put in this hand, including this street's bets |
| `to_call` | `40` | chips you need to add to call (capped at your stack) |
| `min_raise_to` / `max_raise_to` | `80` / `1980` | legal "raise to" range; `null` if you can't raise |
| `legal_actions` | `["fold", "call", "raise"]` | what you may do now |
| `small_blind` / `big_blind` | `10` / `20` | current blinds |
| `blind_level` | `0` | always 0: blinds don't rise |
| `hand_number` | `17` | 1 to 1,000 in a round |
| `betting` | `"no_limit"` | `no_limit`, `pot_limit` or `fixed_limit` |
| `raise_cap` | `null` | max bets/raises per street, or `null` for no cap |
| `raises_this_street` | `1` | bets/raises made so far this street (blinds don't count) |
| `history` | see below | every action **this hand** so far |

Each `history` entry looks like `{"seat": 2, "street": "flop", "action": "raise", "amount": 80}`.
`action` is `small_blind`, `big_blind`, `fold`, `check`, `call` or `raise`.
For `raise` the amount is the "raise to" total; for `call` it's the chips added.

`info` (passed to `on_table_start`) holds `seat`, `num_players`, `hands`
(1,000), `starting_stack` (2,000), `stacks_reset_each_hand` (true),
`small_blind`, `big_blind`, `betting` and `raise_cap`.

`summary` (passed to `on_hand_end`) holds `hand_number`, `board`, `shown`
(hole cards of everyone who reached showdown, keyed by seat as a string),
`winners` (list of `{seat, amount, hand}`), `stacks` and the hand's full `history`.

### Time and output

You get **10 ms per decision**, including the time to send you the state, and a
**10 s time bank per round**: your total thinking time over the round's
1,000 hands. A decision over 10 ms is auto-played (check, else fold). Once the
bank is empty, every decision for the rest of that round is auto-played. The
simulator uses the same limits by default. `print()` is safe: it never breaks
the game. Run with `--show-prints` to see it.

## The game

- No-Limit Texas Hold'em, tables of 7 or 8 bots.
- A **round** is 1,000 hands at one table. Every hand starts every bot on
  2,000 chips (100 big blinds), blinds fixed at 10/20, so nobody busts and
  every table deals the same number of hands.
- Your score is the chips you win. Standings rank on **bb/100**: big blinds
  won per 100 hands, over every hand you've played.
- **Saturday:** practice rounds every 5 minutes from 12:35 to 1:55 p.m. (they
  don't count), then counted rounds every 5 minutes from 3:00 to 7:25 p.m.
  Everyone is reseated each round, so you play everyone. A new upload plays
  from the next round.
- **Sunday:** Saturday's ranking seeds bucket tables. Each bucket table plays
  rounds 9:00–11:55 a.m.; the top two by chips go through to the final table.
- **Final:** 5,000 hands at one table; the most chips wins. Every 100th hand
  is shown as an animated replay.
- The organisers may switch to Pot-Limit or Fixed-Limit, or cap raises per
  street; every `state` tells you the settings in force (`betting`, `raise_cap`).

## Betting rules (summary)

- Raises are "raise to" amounts. Minimum raise = the last bet/raise this street
  (never less than the big blind). Maximum: your stack (No-Limit), the pot after
  calling (Pot-Limit), or exactly one bet (Fixed-Limit: 1 BB pre-flop/flop, 2 BB turn/river).
- If a raise cap is set, after that many bets/raises on a street you can only call or fold.
  Fixed-Limit has a cap of 4 unless the organisers set another.
- Raises are capped by your 2,000-chip stack each hand.
- You can always go all in. A short all-in doesn't reopen raising for bots that already acted.
- Side pots, uncalled bets returned, odd chip to the first winner left of the button.

Practise under other structures:

```bash
python local_sim.py --betting pot_limit
python local_sim.py --betting fixed_limit
python local_sim.py --raise-cap 3
```
