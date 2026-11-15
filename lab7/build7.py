"""recs.pkl (collect7.py) + a template -> bot file with TEAMS/TABLE filled in.

    python3 build7.py tpl.py out.py            # all rounds
Functions are reused by the tests (leave-one-round-out profiles)."""
import math, os, pickle, re, sys
from common import *

def tv(a, b):
    ta = float(sum(a.values()) or 1); tb = float(sum(b.values()) or 1)
    return 0.5 * sum(abs(a.get(k, 0) / ta - b.get(k, 0) / tb) for k in set(a) | set(b))

def regime(rs, thr=0.35):
    """Latest run of rounds in which the team opened with the same sizes (its current bot version)."""
    rs = sorted(rs, key=lambda r: -r['round'])
    acc = dict(rs[0]['so']); used = [rs[0]]
    for r in rs[1:]:
        if tv(r['so'], acc) > thr: break
        used.append(r)
        for k, v in r['so'].items(): acc[k] = acc.get(k, 0) + v
    return used

def add(d, e):
    for k, v in e.items(): d[k] = d.get(k, 0) + v

def logtab(cnt, fld, a=3.0, floor=0.004):
    """log P(size) for sizes the team has used; anything else scores the floor (so one odd bet is no veto)."""
    n = float(sum(cnt.values())); out = {}
    for k, c in cnt.items():
        p = (c + a * fld.get(k, 0.0)) / (n + a)
        if p > floor:
            out[k] = round(math.log(p), 2)
    out[-99] = round(math.log(floor), 2)
    return out

def tweaks(dec):
    """Per-team adjustments from our own real results: how our flat calls of that team's opens did against folding."""
    out = {}
    if not dec: return out
    agg = {}
    for r in dec:
        if r['street'] == 'preflop' and r['k'] == 0 and r['L'] == 1 and r['actual'] == 'call' and r['bettor']:
            a = agg.setdefault(r['bettor'], [0, 0.0]); a[0] += 1; a[1] += r['result'] + r['in']
    for tm, (n, tot) in agg.items():
        m = 1.0 + (tot / n) / 100.0 * n / (n + 100.0)
        out[tm] = {'cf': round(min(1.6, max(0.6, m)), 2)}
    return out

def teams(recs, exclude_round=None, names=None, verbose=False, dec=None):
    by = {}
    for r in recs:
        if r['round'] == exclude_round or r['team'] == ME: continue
        by.setdefault(r['team'], []).append(r)
    fso, fsb, fs3 = {}, {}, {}; fvec = None; fhn = 0
    agg = {}
    for tm, rs in by.items():
        used = regime(rs)
        so, sb, s3 = {}, {}, {}; vec = [0.0] * len(rs[0]['vec']); hn = 0
        for r in used:
            add(so, r['so']); add(sb, r['sb']); add(s3, r['s3']); hn += r['hn']
            vec = [x + y for x, y in zip(vec, r['vec'])]
        agg[tm] = (so, sb, s3, vec, hn, [r['round'] for r in used])
        add(fso, so); add(fsb, sb); add(fs3, s3); fhn += hn
        fvec = vec if fvec is None else [x + y for x, y in zip(fvec, vec)]
    def norm(d):
        t = float(sum(d.values()) or 1); return dict((k, v / t) for k, v in d.items())
    pso, psb, ps3 = norm(fso), norm(fsb), norm(fs3)
    def freq(vec, hn):
        vp = min(0.95, max(0.02, vec[1] / hn)); pf = min(0.9, max(0.01, vec[2] / hn))
        return [round(math.log(vp), 3), round(math.log(1 - vp), 3), round(math.log(pf), 3), round(math.log(1 - pf), 3)]
    T = [['', logtab(fso, pso), logtab(fsb, psb), logtab(fs3, ps3), freq(fvec, fhn), [], {}]]
    tw = tweaks(dec)
    order = [t for t in (names or sorted(agg)) if t in agg]
    for tm in order:
        so, sb, s3, vec, hn, used = agg[tm]
        T.append([tm, logtab(so, pso), logtab(sb, psb), logtab(s3, ps3), freq(vec, hn), [round(x * 1000.0 / hn, 2) for x in vec], tw.get(tm, {})])
        if verbose: print('  %-26s tweaks %s' % (tm, tw.get(tm, {})), end='')
        if verbose: print('  %-26s rounds used %s' % (tm, sorted(used)))
    return T

def inject(tpl_path, out_path, T, table_names):
    src = open(tpl_path).read()
    table = [i for i, t in enumerate(T) if t[0] in table_names]
    block = '#@TEAMS_START@\nTEAMS = %r\nTABLE = %r\n#@TEAMS_END@' % (T, table)
    src2 = re.sub(r'#@TEAMS_START@.*?#@TEAMS_END@', lambda m: block, src, flags=re.S)
    assert src2 != src
    open(out_path, 'w').write(src2)
    return len(src2)

if __name__ == '__main__':
    recs = pickle.load(open(os.path.join(HERE, 'recs.pkl'), 'rb'))
    names = [t for t in SUNDAY]
    dp = os.path.join(HERE, 'decisions.pkl')
    dec = pickle.load(open(dp, 'rb')) if os.path.exists(dp) else None
    T = teams(recs, names=names, verbose=True, dec=dec)
    n = inject(sys.argv[1], sys.argv[2], T, TABLE_D)
    print('teams', len(T) - 1, 'file bytes', n)
