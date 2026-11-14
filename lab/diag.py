"""Diagnose our heads-up bets: by size bucket, how often they get folds and what the hands earn."""
import importlib.util, os, random, sys
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__)); KIT=os.environ.get("KIT", os.path.dirname(HERE))
sys.path.insert(0,HERE); sys.path.insert(0,KIT)
import ab
from engine import FixedHandsTable
from engine.players import LocalPlayer
bot=ab._load(os.path.abspath(sys.argv[1]),"dbot"); bot.DEBUG=True
fieldname=sys.argv[2]; rounds=int(sys.argv[3]) if len(sys.argv)>3 else 3
agg=defaultdict(lambda:[0,0,0.0,0.0])
class Rec(bot.Agent):
    def on_hand_end(self, summary):
        net=summary["stacks"][self.me]-2000
        for d in self.dbg:
            if d[0]==summary["hand_number"]:
                hand,si,e,frac,stg,pot=d
                # did the villain fold right after this bet? approximate: we won without showdown
                key=(si, "S" if frac<0.5 else "M" if frac<0.95 else "B" if frac<1.6 else "O" if frac<3 else "ALLIN", "val" if e>=0.5 else "bluff")
                a=agg[key]; a[0]+=1; a[1]+= (not summary.get("shown")) and net>0; a[2]+=net; a[3]+=e
        self.dbg=[d for d in self.dbg if d[0]!=summary["hand_number"]]
        super().on_hand_end(summary)
tot=0
for r in range(rounds):
    rng=random.Random(r+77); opps=ab.field(rng, fieldname)+ab.field(rng, fieldname)[:1]
    seats=[Rec]+opps; order=list(range(8)); rng.shuffle(order)
    res=FixedHandsTable([LocalPlayer(seats[i]) for i in order],hands=1000,seed=r).play()
    tot+=res["chips"][order.index(0)]
print("bot %+.1f bb/100 vs %s"%(tot/20/rounds/10, fieldname))
print("street size  kind    bets  won-no-showdown  avg e   net chips per bet-hand")
for k in sorted(agg):
    a=agg[k]; print("  %d    %-5s %-6s %5d   %5.0f%%        %.2f   %+8.0f"%(k[0],k[1],k[2],a[0],100*a[1]/a[0],a[3]/a[0],a[2]/a[0]))
