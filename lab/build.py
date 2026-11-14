"""Assemble bot.py from bot_template.py + tables.json (+ optional config.json written by the analyser/tuner).

    python build.py [out_path]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "bot.py")
src = open(os.path.join(HERE, "bot_template.py")).read()
t = json.load(open(os.path.join(HERE, "tables.json")))
tables = "BUCKETS = %r\nPCT = %r\nEQR = %r\nEQ3 = %r\nEQ6 = %r" % (
    t["buckets"],
    [round(x, 4) for x in t["pct"]],
    [[round(x, 3) for x in row] for row in t["eqr"]],
    [round(x, 3) for x in t["eq3"]],
    [round(x, 3) for x in t["eq6"]],
)
src = src.replace("#@TABLES@", tables)
cfg_path = os.path.join(HERE, "config.json")
a = src.index("#@CONFIG_START@")
b_ = src.index("#@CONFIG_END@")
ns = {}
exec(src[a:b_], ns)
names = ["PARAMS", "DEFAULT_PRIOR", "FOLD_PRIOR", "BLUFF_PRIOR"]
cfg = {k: ns[k] for k in names}
if os.path.exists(cfg_path):
    for k, v in json.load(open(cfg_path)).items():
        if k in ("PARAMS", "DEFAULT_PRIOR"):
            cfg[k].update(v)
        elif k in names:
            cfg[k] = v
block = "#@CONFIG_START@\n" + "".join("%s = %s\n" % (k, json.dumps(cfg[k])) for k in names)
src = src[:a] + block + src[b_:]
open(out, "w").write(src)
print("wrote", out, "%.1f KB" % (len(src) / 1024))
