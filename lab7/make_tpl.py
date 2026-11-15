"""bot_think.py (v6) -> lab7/tpl.py : adds seat identification + team virtual history. Behaviour with TEAMS=[] is v6."""
import sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, '..', 'bot_think.py')).read()

def rep(old, new, count=1):
    global src
    assert src.count(old) == count, (src.count(old), old[:80])
    src = src.replace(old, new)

# ---- config
rep('"commit_spr": 0.85, "commit_mult": 1.0}',
    '"commit_spr": 0.85, "commit_mult": 1.0, "tp_w": 0.3, "tp_wp": 1.0, "id_min": 6, "id_gap": 3.0, "id_gap_open": 8.0, "id_freq": 0.5, "szm": [[0.02, 0.02, 0.2, 1.0, 1.3, 1.2], [0.02, 0.02, 0.2, 2.5, 3.0, 5.0]], "szr": [1.8, 2.5], "csh": [0.5, 0.3, 0.1], "steal_cap": [0.92, 0.7, 0.5], "iso_th": 0.3, "final_think": 2.0}')
rep('#@CONFIG_END@\n', '#@CONFIG_END@\n\n#@TEAMS_START@\nTEAMS = []\nTABLE = []\n#@TEAMS_END@\n\n# Positions in Opp.vec() that hold postflop counters (ag, pa, fb, fd, an, aw, then fbk, fdk, ank, awk).\n_POST = frozenset([6, 7, 8, 9, 12, 13] + list(range(26, 48)))\n')

# ---- Opp
rep('"tbc", "tbco", "r4c", "r4co", "sd1n", "sd1s", "sd4n", "sd4s", "bbo", "bbf")',
    '"tbc", "tbco", "r4c", "r4co", "sd1n", "sd1s", "sd4n", "sd4s", "bbo", "bbf",\n                 "so", "sb", "s3", "tid", "vh", "hn", "cfm")')
rep('''        self.bbo = self.bbf = 0   # in the big blind facing one raise / folded it
        self.sd4s = [0.0, 0.0]
''', '''        self.bbo = self.bbf = 0   # in the big blind facing one raise / folded it
        self.sd4s = [0.0, 0.0]
        # Bet-size fingerprint: opening raise sizes (-1 = limp), first-bet sizes postflop (tenths of pot),
        # re-raise sizes (tenths of the raise faced). Used only to recognise which team sits here.
        self.so = {}
        self.sb = {}
        self.s3 = {}
        self.hn = 0       # real hands seen (n also holds the virtual history)
        self.tid = -1     # index into TEAMS once recognised
        self.vh = None    # the virtual history added for that team
        self.cfm = 1.0    # how much wider (>1) or tighter (<1) to flat-call this seat's opens

    def vec(self):
        """All learned counters as one flat list (same order as load)."""
        return ([self.n, self.vpip, self.pfr, self.tbo, self.tb, self.shv, self.ag, self.pa, self.fb, self.fd,
                 self.bigf, self.bigc, self.an, self.aw, self.f3o, self.f3f, self.fro, self.frf, self.r4o, self.r4,
                 self.pjo, self.pjc, self.pbo, self.pbc, self.bbo, self.bbf]
                + self.fbk[0] + self.fbk[1] + self.fdk[0] + self.fdk[1] + self.ank + self.awk + self.sdn + self.sds
                + self.tbc + self.tbco + self.r4c + self.r4co + self.sd1n + self.sd1s + self.sd4n + self.sd4s)

    def load(self, v, k):
        """Add k times the counter vector v (k = -1 takes it out again)."""
        (n, vpip, pfr, tbo, tb, shv, ag, pa, fb, fd, bigf, bigc, an, aw, f3o, f3f, fro, frf, r4o, r4,
         pjo, pjc, pbo, pbc, bbo, bbf) = v[:26]
        self.n += k * n; self.vpip += k * vpip; self.pfr += k * pfr; self.tbo += k * tbo; self.tb += k * tb
        self.shv += k * shv; self.ag += k * ag; self.pa += k * pa; self.fb += k * fb; self.fd += k * fd
        self.bigf += k * bigf; self.bigc += k * bigc; self.an += k * an; self.aw += k * aw
        self.f3o += k * f3o; self.f3f += k * f3f; self.fro += k * fro; self.frf += k * frf
        self.r4o += k * r4o; self.r4 += k * r4; self.pjo += k * pjo; self.pjc += k * pjc
        self.pbo += k * pbo; self.pbc += k * pbc; self.bbo += k * bbo; self.bbf += k * bbf
        i = 26
        for lst in (self.fbk[0], self.fbk[1], self.fdk[0], self.fdk[1], self.ank, self.awk, self.sdn, self.sds,
                    self.tbc, self.tbco, self.r4c, self.r4co, self.sd1n, self.sd1s, self.sd4n, self.sd4s):
            for j in range(len(lst)):
                lst[j] += k * v[i]
                i += 1
''')

# ---- learning: fingerprints
rep('''        lr = -1
        bbs = -1
        for h in summary["history"]:''', '''        lr = -1
        bbs = -1
        nl = 0
        for h in summary["history"]:''')
rep('''                if a == "raise":
                    vp.add(s)
                    pr.add(s)
                    L += 1
                    maxlvl[s] = L''', '''                if L == 0:
                    if nl == 0 and (a == "raise" or a == "call"):
                        k = amt if a == "raise" else -1
                        o.so[k] = o.so.get(k, 0) + 1
                    if a == "call":
                        nl += 1
                elif L == 1 and a == "raise" and cur > 0:
                    k = int(10.0 * amt / cur + 0.5)
                    o.s3[k] = o.s3.get(k, 0) + 1
                if a == "raise":
                    vp.add(s)
                    pr.add(s)
                    L += 1
                    maxlvl[s] = L''')
rep('''                    szb.setdefault(s, set()).add(0 if fr_ < 0.5 else (1 if fr_ < 0.95 else 2))
                elif a == "call" or a == "check":
                    o.pa += 1''', '''                    szb.setdefault(s, set()).add(0 if fr_ < 0.5 else (1 if fr_ < 0.95 else 2))
                    if tc == 0:
                        k = int(10.0 * fr_ + 0.5)
                        if k > 25:
                            k = 25
                        o.sb[k] = o.sb.get(k, 0) + 1
                elif a == "call" or a == "check":
                    o.pa += 1''')
rep('''        for s in range(n):
            o = opp[s]
            o.n += 1
            if s in vp:''', '''        for s in range(n):
            o = opp[s]
            o.n += 1
            o.hn += 1
            if s in vp:''')

# ---- identification
rep('''    # ------------------------------------------------------------------ this hand so far
    def _scan(self, st):''', '''    # ------------------------------------------------------------------ who sits where
    def _ident(self):
        """Match each seat's bet-size fingerprint (and how often it plays) against the known teams.

        A recognised seat gets that team's measured history added to its counters, as if we had already
        watched it for a few hundred hands; everything else in the bot then works unchanged. A seat that fits
        no team well (TEAMS[0] is the whole field) stays on the field priors, and a match can be taken back."""
        T = TEAMS
        P = self.P
        w = P.get("tp_w", 0.0)
        if not T or w <= 0.0:
            return
        allowed = self.allowed
        gap = P["id_gap"] if allowed is not None else P["id_gap_open"]
        fq = P["id_freq"]
        found = []
        for s in range(self.n):
            if s == self.me:
                continue
            o = self.opp[s]
            so = o.so
            nobs = 0
            for k in so:
                nobs += so[k]
            if nobs < P["id_min"]:
                continue
            hn = o.hn
            vp_ = o.vpip - (o.vh[1] if o.vh else 0.0)
            pf_ = o.pfr - (o.vh[2] if o.vh else 0.0)
            best = sec = -1e18
            bi = -1
            l0 = 0.0
            for i in range(len(T)):
                if i and allowed is not None and i not in allowed:
                    continue
                t = T[i]
                ll = 0.0
                for obs, tab in ((so, t[1]), (o.sb, t[2]), (o.s3, t[3])):
                    fl = tab[-99]
                    for k in obs:
                        ll += obs[k] * tab.get(k, fl)
                lg = t[4]
                ll += fq * (vp_ * lg[0] + (hn - vp_) * lg[1] + pf_ * lg[2] + (hn - pf_) * lg[3])
                if i == 0:
                    l0 = ll
                    continue
                if ll > best:
                    sec = best
                    best = ll
                    bi = i
                elif ll > sec:
                    sec = ll
            if bi > 0 and best - l0 >= gap and best - sec >= gap:
                found.append((best - (sec if sec > l0 else l0), s, bi))
        found.sort(reverse=True)
        taken = {}
        for m, s, bi in found:
            if bi not in taken:
                taken[bi] = s
        seat_team = dict((s, bi) for bi, s in taken.items())
        for s in range(self.n):
            if s == self.me:
                continue
            o = self.opp[s]
            ti = seat_team.get(s, -1)
            if ti == o.tid:
                continue
            if o.vh:
                o.load(o.vh, -1.0)
                o.vh = None
            o.tid = ti
            o.cfm = 1.0
            if ti > 0:
                o.cfm = T[ti][6].get("cf", 1.0)
                # Preflop habits are learned live within a few dozen hands, so the team history counts for
                # little there (tp_w); postflop fold and bluff rates take a whole round to see (tp_wp).
                wp = P.get("tp_wp", w)
                v = T[ti][5]
                o.vh = [v[i] * (wp if i in _POST else w) for i in range(len(v))]
                o.load(o.vh, 1.0)

    # ------------------------------------------------------------------ this hand so far
    def _scan(self, st):''')
rep('''            self._learn(summary)
            if summary.get("hand_number", 1) % 50 == 0:
                gc.collect()''', '''            self._learn(summary)
            hn = summary.get("hand_number", 1)
            if hn > 1100 and self.hands <= 1500:
                # More hands than a round has: this is the final even though the table info did not say so.
                self.hands = 5000
                self.allowed = None
                self.bk = 5.0
                self.tmax = self.P.get("final_think", 2.0)
            if hn % 10 == 0 or hn == 5:
                self._ident()
            if hn % 50 == 0:
                gc.collect()''')
rep('''        self.tmo = 0          # replies of ours the dealer replaced with check/fold (we were too slow)''',
    '''        self.allowed = None   # team indexes that can be at this table (None = any)
        self.hands = 1000
        self.tmo = 0          # replies of ours the dealer replaced with check/fold (we were too slow)''')
rep('''            self.opp = [Opp(DEFAULT_PRIOR) for _ in range(self.n)]
        except Exception:
            pass
''', '''            self.opp = [Opp(DEFAULT_PRIOR) for _ in range(self.n)]
        except Exception:
            pass
        try:
            # A 1,000-hand round on Sunday is our bucket table, whose teams are known; the 5,000-hand final
            # can seat anyone.
            self.hands = int(info.get("hands", 1000) or 1000)
            if TABLE and self.hands <= 1500:
                self.allowed = set(TABLE)
        except Exception:
            self.allowed = None
''')
# ---- bet-size calibration of how much a bet narrows the bettor's range
rep("""                    pts[s] += (0.6 + 0.8 * (frac if frac < 1.5 else 1.5) + (1.2 if tc > 0 else 0.0)
                               + (0.8 if tc > 0 and frac >= 1.2 else 0.0)) * opp[s].hon(kb)""",
"""                    # How much a bet narrows the bettor's range, by size. Fitted to 1,300 real hands we called
                    # down: the old flat scale made bets under 3/4 pot look 13-26 points too strong and
                    # bigger bets and raises 9-26 points too weak. Flop sizes say less than turn and river ones.
                    zi = 0 if street == "flop" else 1
                    if tc > 0:
                        zm = self.P["szr"][zi]
                    else:
                        z = self.P["szm"][zi]
                        zm = z[0] if frac < 0.2 else (z[1] if frac < 0.45 else (z[2] if frac < 0.75 else (
                            z[3] if frac < 0.95 else (z[4] if frac < 1.6 else z[5]))))
                    pts[s] += (0.6 + 0.8 * (frac if frac < 1.5 else 1.5) + (1.2 if tc > 0 else 0.0)
                               + (0.8 if tc > 0 and frac >= 1.2 else 0.0)) * opp[s].hon(kb) * zm""")
# ---- calls of small bets: the equity model is still pessimistic there (real showdowns), so shift it
rep("""        margin = P["call_margin"]
        if street != "river" and not allin:
            margin += P["early_margin"]
        if e >= req + margin:
            return CALL
        return FOLD""", """        margin = P["call_margin"]
        if street != "river" and not allin:
            margin += P["early_margin"]
        if no == 1 and mybet == 0 and pot > tc:
            # Facing a bet (not a raise) of under three-quarters pot from one opponent: on 900 real called
            # hands that reached showdown we won 14-21 points more often than the equity says, even after
            # the size correction in _scan ('szm'). 'csh' moves the equity up, in log-odds, by bet size.
            fr_ = tc / float(pot - tc)
            csh = P["csh"]
            sh = csh[0] if fr_ < 0.2 else (csh[1] if fr_ < 0.45 else (csh[2] if fr_ < 0.75 else 0.0))
            if sh:
                x = 0.01 if e < 0.01 else (0.99 if e > 0.99 else e)
                e = 1.0 / (1.0 + (1.0 - x) / x * _exp(-sh))
        if e >= req + margin:
            return CALL
        return FOLD""")
rep("import time\n", "import time\nfrom math import exp as _exp\n")
# ---- steals: the widest button / cutoff steals lost money on real hands
rep("""                edge = pf_all - (0.47, 0.52, 0.58)[nb - 1]
                if edge >= 0.0:
                    th = max(th, 0.92)
                elif edge >= -0.07:
                    th = max(th, 0.70)
                elif edge >= -0.14:
                    th = max(th, 0.50)
            if th > 0.92:
                th = 0.92""", """                edge = pf_all - (0.47, 0.52, 0.58)[nb - 1]
                # Real results of our opens (r002-r051): button opens with the weakest 30% of hands and
                # cutoff opens with the weakest half lost against folding; small-blind opens did not.
                cap = P["steal_cap"][nb - 1]
                if edge >= 0.0:
                    th = max(th, 0.92 if cap > 0.92 else cap)
                elif edge >= -0.07:
                    th = max(th, 0.70 if cap > 0.70 else cap)
                elif edge >= -0.14:
                    th = max(th, 0.50 if cap > 0.50 else cap)
                if th > cap:
                    th = cap
            if th > 0.92:
                th = 0.92""")
# ---- one limper: raise wider (raises over limpers earned +72 chips a hand with the 20-35% hands)
rep("""            if limp:
                th *= 0.9
            elif nb <= 3:""", """            if limp:
                if limp == 1:
                    if th < P["iso_th"]:
                        th = P["iso_th"]
                else:
                    th *= 0.9
            elif nb <= 3:""")
# ---- flat calls: price and who opened
rep("""            cf = P["call_frac"] * (1.6 if req <= 0.26 else 1.0)
            if p <= min(0.55, cf * t) and tc <= 0.08 * total:
                return CALL""", """            # Calling opens of more than 2.75bb about broke even and calling 5bb+ lost heavily on real hands;
            # against some teams calling earned far more than against others (o.cfm, set once the seat is known).
            cf = P["call_frac"] * (1.6 if req <= 0.26 else 1.0)
            capc = 0.08
            if me == (st["button"] + 2) % n:
                if o.cfm > 1.0:
                    cf *= o.cfm
            else:
                cf *= o.cfm
                capc = 0.05
                if tc > 55:
                    cf *= 0.8 if tc <= 70 else 0.5
            if p <= min(0.55, cf * t) and tc <= capc * total:
                return CALL""")
# ---- thinking time in the 5,000-hand final
rep("""            budget = P["mc_ms"] * self.scale * (6.0 if stake >= 1200 else (4.0 if stake >= 500 else (2.0 if stake >= 200 else 1.0)))""",
    """            mult = 6.0 if stake >= 1200 else (4.0 if stake >= 500 else (2.0 if stake >= 200 else 1.0))
            if mult > self.tmax:
                mult = self.tmax
            budget = P["mc_ms"] * self.scale * mult
            if self.tmax <= 0.0:
                budget = 0.25   # 'final_think': 0 = the final's time bank is NOT bigger than a round's: think least""")
rep("""        if self.used < 5.0:
            # Think longer""", """        if self.used < 5.0 * self.bk:
            # Think longer""")
rep("""        elif self.used < 7.5:
            budget = 1.0""", """        elif self.used < 7.5 * self.bk:
            budget = 1.0""")
rep("""        self.allowed = None   # team indexes that can be at this table (None = any)
        self.hands = 1000""", """        self.allowed = None   # team indexes that can be at this table (None = any)
        self.hands = 1000
        self.tmax = 6.0       # most extra thinking in a big pot
        self.bk = 1.0         # time-bank scale: the final is five rounds long""")
rep("""            if TABLE and self.hands <= 1500:
                self.allowed = set(TABLE)""", """            if TABLE and self.hands <= 1500:
                self.allowed = set(TABLE)
            if self.hands > 1500:
                # The final: assume the time bank grows with the hand count, but spend less per big pot in
                # case it does not ('final_think' = most extra thinking; 6 = same as a normal round).
                self.bk = self.hands / 1000.0
                self.tmax = self.P.get("final_think", 2.0)""")
open(os.path.join(HERE, 'tpl.py'), 'w').write(src)
print('ok', len(src))
