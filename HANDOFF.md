# Poker bot handoff (Imperial AI Hack, Track 04)

Written Sat 14 Nov 2026, 19:28. Owner: Oleg (team "Anker Batteries", with nathaniel.melnichenko@gmail.com).

## Goal
Finish top 2 at Sunday's bucket table, then win the 8-bot final.

## Schedule
- Sat 19:30: uploads closed, teams fixed. Sat 20:30: bucket tables announced.
- Sun 09:00-11:55: bucket tables, a round every 5 min, same opponents all morning. Top 2 by chips go through.
- Sun 12:00: uploads close (page says so; confirm they reopen Sunday morning). Sun 12:05: final, 5,000 hands.

## Rules that matter
- No-limit hold'em, 7-8 bots, 1,000 hands a round, stacks reset to 2,000 (100bb) every hand, blinds 10/20.
- One file `bot.py`, class `Agent`, standard library only, Python 3.12, 200 KB, 512 MB.
- 25 ms per decision (raised from 10 ms on Saturday evening), 10 s thinking bank per round. The tournament adds about 1.5 ms overhead per decision (about 2 s per round).
- Seats are anonymous during play. Team names appear only in downloaded hand files.

## Where everything is
Mac: `~/Downloads/imperial-ai-hack-pokerbots-kit/`
- `bot.py`: v5, the bot that was live at 19:28 (sha256 starts 40c34c63). Uploaded by the teammate.
- `bot_think.py`: v5 plus longer thinking in bigger pots (sha 0c4c3ef5). Oleg may have uploaded it just before 19:30: check the site's "Your bot" SHA.
- `hands/saturday_rNNN.json`: every counted round r002-r051.
- `lab/`: tools. `README_LAB.md` lists them. Key ones: `analyse.py` (field stats, leaks, writes `config.json` priors and `replicas.json`), `replay.py` (run a bot through real hands; exact effect of extra folds), `ab.py` (two bots on duplicate deals; `--field real` uses replicas of real opponents), `selftest.py`, `build.py` (template + config -> bot), `collect.py`, `versions/` (all builds).
- Caution: `lab/bot_template.py` is build 7's code. v5 is newer (faster evaluator `prep`/`ev2`, `oop_fold` correction) and exists only as a built file. To change v5, patch the built file or port its changes into the template first.

## Fetching data
The site blocks `fetch_hands.py` from the Mac (403) and shells have no network. It works through the Claude desktop app's built-in browser on imperialaihack.com/poker: JavaScript `fetch('/api/poker/results')` and `/api/poker/hands?ref=...` with header `Authorization: Bearer <token>`, then a blob download per round, then `python3 lab/collect.py` copies them into `hands/`. Data token (reads this team's results only; do not share): `73aaed015a619150.22c3388d1ecf61d8337c566c71f7041a`. A helper `window.__pull()` was defined in that tab; redefine it if the page reloaded.

## How the bot works
- Preflop: hand percentile table plus all-in equity vs range tables. Opens by position; steals wide from button/small blind when the players behind fold enough; re-raises on equity vs the raiser's range; bluff re-raises openers that fold to re-raises.
- Postflop: time-capped Monte Carlo equity against each opponent's estimated range, skewed by their betting. Heads-up bets are chosen by expected value using that opponent's fold rate by bet size and by first bet vs later bets, pooled across the table.
- Per-seat live stats with field priors (`DEFAULT_PRIOR`, `FOLD_PRIOR`, `BLUFF_PRIOR` in the config block).
- Detects its own timeouts and halves thinking time.

## Results (bb/100, real rounds)
| Live version | Build | Rounds | Average |
|---|---|---|---|
| v1 | build 4 | 7 | +3.6 |
| v2 | build 5 | 2 | +30.5 |
| v3 | build 6 | 13 | +39.2 |
| v4 | build 7 | 25 | +15.9 |
| v5 | teammate's v5 | 3 | +49.5 (+80.2, +71.4, -3.1) |

Standings at round 51: 6th of 39 on +22.8. Top two: Attention Is All In +45.8, Gherkers +45.5.

## What was learned
- The field is tight and folds a lot: about 55% to a first bet of half to full pot, about 70% to pot-sized or bigger, about 63% to a preflop re-raise. Big bets are bluffs only about 10% of the time.
- It got tougher during the day: our late-position steals got all folds 47% early, 35% late. Build 6 also faded (+56 first 7 rounds, +19 last 6), so builds 6 and 7 are about equal.
- Fold-to-re-raise varies by team: Red, SARS, supernut about 92%; Anton 19%; ediz_slow 0%.
- Biggest single fix all day: stop calling all-ins from tight players with hands like KQ, ATs (build 5).
- Simulations against stand-in opponents do not predict real results well. One real round swings 30-50 bb/100; differences under about 10 cannot be seen in a few rounds.

## Tried and rejected
- Folding one pair to pot-plus bets of 30bb+: slightly worse on 13 replayed rounds.
- Refreshing priors from the latest 15 rounds on top of v5: level or slightly worse in simulation (`lab/versions/bot_10_candidate.py`).
- Flat triple thinking time: level with v5 in simulation.
- Neural net: too little data, moving field, tight time and size limits.

## Next steps
1. Confirm which bot is live (site SHA) and whether Sunday uploads are open.
2. After 20:30, get the bucket table's teams. Build per-team profiles from `hands/` (fold to raise, to re-raise, to bets by size; bet-size tells; opening raise size as a fingerprint) and set the bot's priors to that table.
3. Sunday morning: fetch after each round, compare by version, change only what passes `selftest.py`, `replay.py` and a real-sim run.
