"""Copy hand files that the browser downloaded into ~/Downloads (finished or still temp) into ../hands/."""
import glob, json, os, shutil
here = os.path.dirname(os.path.abspath(__file__))
dl = os.path.dirname(os.path.dirname(here))
dst = os.path.join(os.path.dirname(here), "hands")
os.makedirs(dst, exist_ok=True)
for f in glob.glob(os.path.join(dl, ".*claudefordesktop*")) + glob.glob(os.path.join(dl, "pokerhands__*.json")):
    try:
        d = json.load(open(f))
        ref = d["round"]["ref"].replace("/", "_")
    except Exception:
        continue
    out = os.path.join(dst, ref + ".json")
    if not os.path.exists(out):
        shutil.copyfile(f, out)
        print("saved", ref, len(d["hands"]), "hands", round(d["round"]["bb100"], 1), "bb/100", "timeouts", d["round"].get("timeouts"))
print(sorted(os.listdir(dst)))
