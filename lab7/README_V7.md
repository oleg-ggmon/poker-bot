# bot_v7 (built Sat night for Sunday's Table D and the final)

`../bot_v7.py` = v6 (`bot_think.py`, the bot live at 19:30) plus the changes below. Upload it renamed to `bot.py`
(a ready copy is in `../upload/bot.py`). Your v5 `../bot.py` and v6 `../bot_think.py` are untouched: either is the rollback.

## What changed, and the evidence (all on your 50 real rounds, r002-r051)
1. **Knows who sits where.** Each seat's bet sizes (open size, limps, first-bet size, re-raise size) are matched to
   the 30 Sunday teams. A recognised seat starts with that team's measured history instead of field averages.
   With profiles that exclude the round being tested: 75% of seats right after 100 hands, 92% by the end,
   under 1% wrong; all 7 Table D teams were right by hand 100 in every round they appeared.
   Fold predictions against Table D teams improve (log-loss 0.662 -> 0.639; big bets 0.681 -> 0.643).
   At a 1,000-hand table only the Table D teams are candidates; at the 5,000-hand final all 30 are.
2. **Bet-size calibration.** On 1,300 real hands we called down, v6 thought bets under 3/4 pot were 13-26 points
   stronger than they were, and bigger bets and raises 9-26 points weaker. Fixed in the range model (`szm`, `szr`)
   plus a shift for calling small bets (`csh`). Calibration log-loss 0.659 -> 0.606.
3. **Preflop, from real results against folding:** button steals capped at the best 70% of hands and cutoff at 50%
   (`steal_cap`); one limper is raised with the best 30% (`iso_th`); flat calls of opens over 2.75bb tightened;
   per-team call width (`cf`: WBot 1.6, Poke 1.27, YSL 1.15, Anton 0.7, Resonance 0.8).
4. **Final table:** less extra thinking per big pot (`final_think`), in case the time bank is not bigger there.

Replay of all 50 rounds (held-out profiles): the folds v7 adds where the live bot continued are worth about
+3 to +4 bb/100; v6 on the same test is -1.8. Run-to-run noise is about 1. Duplicate-deal sims vs v6: +5.9 +- 3.6
(replica field), -3.0 +- 5.2 (mixed field): no regression, not proof. v7 has not played a live round.

Not taken from `bot_new.py`: `oop_med_pot` (the r018-r036 loss reverses in r037-r051: those bets made +128 a hand)
and `bb_def 0.0` (our cheap big-blind calls only break even against folding).

## Sunday
- 08:55 ask the help desk: **is the time bank in the 5,000-hand final 10 s or 50 s?** At 10 s every bot that thinks
  runs dry near hand 4,000. If they say 10 s: set `"final_think": 0` in PARAMS (top of the file) and re-upload.
- 09:00 upload `upload/bot.py`. The 09:00 round is played by v6 whatever you do.
- After each round check the results row: Missed and Problems must stay 0. If not, re-upload `bot_think.py`.
- About every 5 rounds: fetch the new hands (browser method in HANDOFF.md), then `python3 lab7/refresh.py`.
  It rebuilds the profiles from Sunday's hands (each team's current version only) and prints PASS or DO NOT UPLOAD.
  This is the tuning that works: 1,000 fresh hands per opponent per round at the exact table.
- Do not judge a build on one or two rounds: one round swings 30-50 bb/100.
- The last upload before 12:00 plays the final. Do not upload anything untested after 11:45.

## Files
`make_tpl.py` v6 -> template | `collect7.py` hands -> team counters | `build7.py` profiles -> bot | `refresh.py` all of it
`replay7.py` exact effect of extra folds | `eval_id.py` identification test | `eval_pred.py` prediction test
`calib.py`, `szsearch.py` bet-size calibration | `soak.py` overnight crash/timing soak
