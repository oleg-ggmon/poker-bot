# lab/nn : fold-probability net

`bot_nn.py` (kit root, also `lab/versions/bot_12_nn.py`) is v5 (`bot.py`, sha 40c34c63) with one change:
when we bet first into a single opponent, the chance they fold comes from a small net instead of the
fold-rate table (`fold_at` x `oop_fold`). `PARAMS["nn"] = 0` turns the net off.

Net: 33 inputs -> 16 -> 8 -> 1, 689 parameters, trained on 37,324 real opponent decisions facing a
postflop bet (rounds r002-r051). Inputs are listed in `extract.py` (`FEATS`).

    python3 extract.py                       # hands -> data.npz (replays v5 so stats match live play)
    python3 train.py                         # held-out test: train r002-r041, test r042-r051
    python3 cv.py                            # 5-fold by round; calibration on our own bets
    python3 train.py --final "[16, 8]" 14    # retrain on everything -> weights.json
    python3 build_nn.py ../../bot.py ../versions/bot_12_nn.py
    python3 parity.py ../versions/bot_12_nn.py   # bot-side inputs/outputs equal the training code
    python3 policy_diff.py ../../bot.py ../versions/bot_12_nn.py

After new rounds arrive: rerun extract, train --final, build_nn, parity.
