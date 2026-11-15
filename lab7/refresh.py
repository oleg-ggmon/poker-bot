"""One command after new hand files arrive in ../hands :  python3 lab7/refresh.py

 1. re-reads every round with the bot's own learning code -> team profiles (each team's current bot version only)
 2. replays our own decisions -> per-team call adjustments
 3. builds ../bot_v7.py (and a numbered copy in lab7/builds/)
 4. checks it: loads, plays 2 self-test rounds with 0 errors, replays the latest rounds
Upload ../bot_v7.py as bot.py only if step 4 prints PASS."""
import glob, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); KIT = os.path.dirname(HERE)
def run(args, **kw):
    print('>', ' '.join(args)); r = subprocess.run([sys.executable] + args, cwd=HERE, capture_output=True, text=True, **kw)
    out = (r.stdout or '') + (r.stderr or '')
    if r.returncode: print(out); sys.exit('FAILED: ' + ' '.join(args))
    return out
print(run(['make_tpl.py']).strip())
print(run(['collect7.py']).strip())
print(run(['dump.py', 'tpl.py', 'decisions.pkl']).strip())
out = run(['build7.py', 'tpl.py', os.path.join(KIT, 'bot_v7.py')])
print('\n'.join(l for l in out.splitlines() if any(t in l for t in ('Resonance', 'Chinese', 'WBot', 'GamesGone', 'Poke ', 'Anton', 'YSL', 'teams'))))
os.makedirs(os.path.join(HERE, 'builds'), exist_ok=True)
stamp = time.strftime('%H%M'); shutil.copyfile(os.path.join(KIT, 'bot_v7.py'), os.path.join(HERE, 'builds', 'bot_v7_%s.py' % stamp))
tmp = os.path.join(HERE, '_selftest'); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
shutil.copyfile(os.path.join(KIT, 'bot_v7.py'), os.path.join(tmp, 'bot.py'))
for d in ('engine', 'examples'): shutil.copytree(os.path.join(KIT, d), os.path.join(tmp, d))
st = run([os.path.join(KIT, 'lab', 'selftest.py'), tmp, '2', '3']); print(st.strip())
size = os.path.getsize(os.path.join(KIT, 'bot_v7.py'))
ok = 'swallowed errors 0 | engine errors 0' in st and size < 200000
nfiles = len(glob.glob(os.path.join(KIT, 'hands', '*.json')))
rp = run(['replay7.py', 'tpl.py', '--from', str(max(0, 0))]) if '--replay' in sys.argv else ''
if rp: print(rp.splitlines()[0])
print('%s  bot_v7.py %d bytes, built from %d rounds (copy: lab7/builds/bot_v7_%s.py)' % ('PASS' if ok else 'DO NOT UPLOAD', size, nfiles, stamp))
