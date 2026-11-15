import pickle, sys, math
def table(path, verbose=True):
    rows = pickle.load(open(path, 'rb'))
    tot = 0.0; nn = 0; out = []
    for street in ('flop', 'turn', 'river'):
        for kind in ('bet', 'raise'):
            for lo, hi in ((0, 0.2), (0.2, 0.45), (0.45, 0.75), (0.75, 0.95), (0.95, 1.6), (1.6, 99)):
                sel = [r for r in rows if r['street'] == street and r['actual'] == 'call' and lo <= r['frac'] < hi and r['tc'] > 0 and r['nlive'] == 1
                       and r['e'] is not None and r['sd'] and ((r['mybet'] > 0) == (kind == 'raise'))]
                if len(sel) < 6: continue
                w = sum(1.0 if r['result'] > 0 else (0.5 if r['result'] == 0 else 0) for r in sel) / len(sel)
                e = sum(r['e'] for r in sel) / len(sel)
                ll = 0.0
                for r in sel:
                    p = min(0.97, max(0.03, r['e'])); y = 1.0 if r['result'] > 0 else (0.5 if r['result'] == 0 else 0.0)
                    ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
                if street == 'river': tot += ll; nn += len(sel)
                out.append('  %-5s %-5s %.2f-%.2f n=%3d  e=%.2f  won=%.2f  diff %+.2f  logloss %.3f' % (street, kind, lo, hi, len(sel), e, w, e - w, ll / len(sel)))
    if verbose: print('\n'.join(out))
    print('RIVER log-loss %.4f over %d' % (tot / nn, nn))
if __name__ == '__main__': table(sys.argv[1])
