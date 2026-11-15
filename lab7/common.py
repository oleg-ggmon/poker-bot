import glob, importlib.util, json, os, pickle, sys
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
ME = 'Anker Batteries'
TABLE_D = ['Resonance Qt', 'Chinese people can fly', 'WBot', 'GamesGone', 'Poke', 'Anton', 'YSL_TWIZZY']
SUNDAY = ["Attention Is All In","Kojack","Mohil'sPokerBot","Astra La Vista","gamblerlove","munchlax","test",
          "Gherkers","Equity Engine","Phil AIvey","JoCal","supernut","SARS","bigRoddy","AIl IN",
          "The Market Makers","FisherMen","Durahim 1453","Claudebot","Jump Street","matcha mille crêpes cake","85p","Joca",
          "Resonance Qt","Chinese people can fly","WBot","GamesGone","Poke","Anton","YSL_TWIZZY"]

def load(path, name=None):
    spec = importlib.util.spec_from_file_location(name or ('m' + str(abs(hash(path)))), path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    if hasattr(m, 'gc'):   # the bot's manual collections are slow inside a lab process that holds every hand file
        class _G(object):
            @staticmethod
            def collect(): return 0
        m.gc = _G
    return m

def rounds(pattern='*.json'):
    out = []
    for f in sorted(glob.glob(os.path.join(KIT, 'hands', pattern))):
        d = json.load(open(f))
        ref = d['round']['ref']
        day = 0 if 'saturday' in ref else 1
        num = int(''.join(ch for ch in ref.split('/')[-1] if ch.isdigit()) or 0)
        out.append((day * 1000 + num, d))
    out.sort(key=lambda x: x[0])
    return out

def hand_iter(data, me_cb=None):
    """Yield ('act', state_fn, event) for our decisions and ('end', summary) per hand, as replay.py builds them."""
    me = data['seat']; n = len(data['players'])
    for h in data['hands']:
        bb = h.get('bb', 20)
        stacks = list(h.get('start_stacks', [2000] * n)); bets = [0] * n; contrib = [0] * n; folded = [False] * n
        history = []; street = 'preflop'; board = []; cur = 0; min_inc = bb; raises = 0; nposts = 0
        for e in h['events']:
            if e[0] == 'post':
                s, amt = e[1], e[2]
                stacks[s] -= amt; bets[s] += amt; contrib[s] += amt
                history.append({'seat': s, 'street': 'preflop', 'action': 'small_blind' if nposts == 0 else 'big_blind', 'amount': amt})
                nposts += 1; cur = max(bets)
            elif e[0] == 'board':
                street = e[1]; board = e[2]; bets = [0] * n; cur = 0; min_inc = bb; raises = 0
            elif e[0] == 'refund':
                s, amt = e[1], e[2]; stacks[s] += amt; contrib[s] -= amt
            elif e[0] == 'act':
                s, a, amt = e[1], e[2], e[3] or 0
                if s == me or me_cb == 'all':
                    to_call = min(cur - bets[s], stacks[s]); max_to = bets[s] + stacks[s]
                    others = any(not folded[j] and stacks[j] > 0 for j in range(n) if j != s)
                    can_raise = max_to > cur and others
                    legal = (['fold', 'call'] if to_call > 0 else ['check']) + (['raise'] if can_raise else [])
                    state = {'hand_number': h['n'], 'street': street, 'seat': s, 'button': h['button'],
                             'hole_cards': h['hole'].get(str(s)), 'board': list(board), 'small_blind': bb // 2, 'big_blind': bb,
                             'pot': sum(contrib), 'stacks': list(stacks), 'bets': list(bets), 'folded': list(folded),
                             'to_call': to_call, 'min_raise_to': min(cur + min_inc, max_to) if can_raise else None,
                             'max_raise_to': max_to if can_raise else None, 'legal_actions': legal, 'betting': 'no_limit',
                             'raise_cap': None, 'raises_this_street': raises, 'history': list(history)}
                    yield ('act', state, (s, a, amt), h, contrib[s])
                if a == 'raise':
                    add = amt - bets[s]
                    if amt - cur >= min_inc: min_inc = amt - cur
                    stacks[s] -= add; bets[s] = amt; contrib[s] += add; cur = amt; raises += 1
                elif a == 'call':
                    stacks[s] -= amt; bets[s] += amt; contrib[s] += amt
                elif a == 'fold':
                    folded[s] = True
                history.append({'seat': s, 'street': street, 'action': a, 'amount': amt})
        shown = {k: h['hole'][k] for k in h.get('showdown', {}) if k in h['hole']}
        yield ('end', {'hand_number': h['n'], 'board': h['board'], 'shown': shown, 'winners': [],
                       'stacks': [2000 + r for r in h['results']], 'history': history}, None, h, None)
