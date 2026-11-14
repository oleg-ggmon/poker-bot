# lab/ : the analyser, tuner and test tools for bot.py

`../bot.py` is a build product. Edit `bot_template.py` (code) or `config.json` (numbers), then rebuild.

## The loop (run inside lab/)

```bash
cd ..; python3 fetch_hands.py --token YOUR-TOKEN; cd lab    # 1. pull new rounds into ../hands/
python3 analyse.py ../hands                                  # 2. opponent table, field fold/bluff rates, our leaks
                                                             #    writes config.json (field priors) + replicas.json
python3 build.py candidate.py                                # 3. bake config.json into a candidate bot
python3 ab.py ../bot.py candidate.py 40                      # 4. gate: candidate vs live bot on identical deals
cp candidate.py ../bot.py                                    #    only if step 4 is not worse
python3 selftest.py .. 3 3                                   # 5. gate: 0 errors
cd ..; python3 local_sim.py --rounds 5                       # 6. gate: 0 timeouts, 0 errors, think s/rd < 5
```

Upload `../bot.py` only if steps 5 and 6 are clean. Earlier bots are kept in `versions/` for rollback.

## Files

| file | what it does |
|---|---|
| `bot_template.py` | the bot's code. The config block at the top holds every tunable number |
| `build.py` | template + `tables.json` + `config.json` -> a bot file |
| `analyse.py` | hand histories -> per-opponent stats and types, field fold rates by bet size, bluff rates, leak report |
| `ab.py` | old bot vs new bot at the same tables on duplicate deals; `--field eq` (or `starter`, `house_tag`, `rep_lag`, `station`...) for one opponent type, `--weak` to add stations and random bots |
| `diag.py` | how each of our bet sizes performs against one opponent type |
| `tune.py` | hill-climbs `PARAMS` against replicas + house bots (slow and noisy; use `--seeds 16`+) |
| `repcore.py`, `testbots/` | test opponents: replicas of measured profiles, equity-vs-random bots, the starter bot |
| `selftest.py` | in-process stress test: hidden errors and decision times |
| `fieldtest.py` | bot vs tight / loose / aggressive / shove-happy archetype fields |
| `precompute.py`, `evalcore.py`, `tables.json` | preflop tables (already computed; no need to rerun) |

`python3 analyse.py ../hands --schema` prints the raw shape of a downloaded file, useful if the
site's format differs from what the analyser expects.
