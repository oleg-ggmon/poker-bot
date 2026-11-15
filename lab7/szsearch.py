import json, math, os, pickle, subprocess, sys
CL = [('b<.2', 'bet', 0, .2), ('b.2-.45', 'bet', .2, .45), ('b.45-.75', 'bet', .45, .75), ('b.75-.95', 'bet', .75, .95), ('b.95-1.6', 'bet', .95, 1.6), ('b1.6+', 'bet', 1.6, 99), ('raise', 'raise', 0, 99)]
def score(path):
    rows = pickle.load(open(path, 'rb')); out = []; tot = 0.0; n = 0
    for name, kind, lo, hi in CL:
        sel = [r for r in rows if r['actual'] == 'call' and lo <= r['frac'] < hi and r['tc'] > 0 and r['nlive'] == 1 and r['e'] is not None and r['sd'] and ((r['mybet'] > 0) == (kind == 'raise'))]
        w = sum(1.0 if r['result'] > 0 else (0.5 if r['result'] == 0 else 0) for r in sel) / len(sel)
        e = sum(r['e'] for r in sel) / len(sel); ll = 0.0
        for r in sel:
            p = min(0.97, max(0.03, r['e'])); y = 1.0 if r['result'] > 0 else (0.5 if r['result'] == 0 else 0.0)
            ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        tot += ll; n += len(sel)
        out.append('%s n%d %+.2f ll%.3f' % (name, len(sel), e - w, ll / len(sel)))
    return ' | '.join(out) + ' || ALL %.4f' % (tot / n)
for p in sys.argv[1:]:
    subprocess.run([sys.executable, 'dump.py', 'tpl.py', '/tmp/ds.pkl', p, '--calib'], stdout=subprocess.DEVNULL, check=True)
    print(p); print('   ', score('/tmp/ds.pkl'))
