"""Overnight soak: keeps playing bot_v7 against v6 on duplicate deals and stress-testing it, logging to soak.log.

    cd lab7 && nohup python3 soak.py > soak.log 2>&1 &        (stop with: pkill -f soak.py)

It does NOT tune anything (simulated opponents do not predict real results). It is there to catch a rare
crash or slow decision before 09:00: every line should show 'swallowed errors 0 | engine errors 0'."""
import os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); KIT = os.path.dirname(HERE)
tmp = os.path.join(HERE, '_selftest'); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
shutil.copyfile(os.path.join(KIT, 'bot_v7.py'), os.path.join(tmp, 'bot.py'))
for d in ('engine', 'examples'): shutil.copytree(os.path.join(KIT, d), os.path.join(tmp, d))
i = 0
while True:
    for field in (['--field', 'real'], [], ['--weak']):
        r = subprocess.run([sys.executable, os.path.join(KIT, 'lab', 'ab.py'), os.path.join(KIT, 'bot_think.py'), os.path.join(KIT, 'bot_v7.py'), '40', '--from', str(i * 40)] + field,
                           capture_output=True, text=True, cwd=os.path.join(KIT, 'lab'))
        print(time.strftime('%H:%M'), (r.stdout or r.stderr).strip().splitlines()[-1], flush=True)
    r = subprocess.run([sys.executable, os.path.join(KIT, 'lab', 'selftest.py'), tmp, '3', '4'], capture_output=True, text=True)
    print(time.strftime('%H:%M'), ' | '.join((r.stdout or r.stderr).strip().splitlines()), flush=True)
    i += 1
