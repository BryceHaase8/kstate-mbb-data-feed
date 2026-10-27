#!/usr/bin/env python3
"""Small deterministic safety checks for scheduled public NIL pricing updates."""
import json, tempfile, pathlib, copy
from nil_season_engine import player_weight, preview_rates
from record_stock_history import record

def test():
    assert player_weight(0,0,700,30)[0]==0
    assert player_weight(5,150,700,30)[0]>player_weight(5,30,700,30)[0]
    assert player_weight(30,900,700,30)[0]>.90
    assert .74<player_weight(30,180,700,30)[0]<.85
    old={'minutes':600,'gp':25,'gs':10,'three_pm':48,'three_pa':140,'two_pm':85,'two_pa':170,'fta':67,'ftm':46}
    new={'minutes':31,'gp':1,'gs':1,'three_pm':5,'three_pa':7,'two_pm':2,'two_pa':5,'fta':4,'ftm':3}
    pct=preview_rates(new,old)['three_pct']
    assert .32<pct<.46, pct # hot week cannot become a 71% shooting prior
    with tempfile.TemporaryDirectory() as t:
        p=pathlib.Path(t);(p/'stock').mkdir();ids=[str(4000000+i) for i in range(1200)]
        baseline={pid:150000 for pid in ids}
        (p/'stock/preseason_2027.json').write_text(json.dumps({'schemaVersion':1,'season':2027,'asOf':'2026-10-24','byESPNId':baseline}))
        (p/'stock/manifest_2027.json').write_text(json.dumps({'schemaVersion':1,'season':2027,'dates':[],'months':[]}))
        def candidate(day,updated):
            rows={id:{'preseason':150000,'value':(170000 if id==ids[0] and updated else 150000),'games':1 if updated else 0,'status':'UPDATED' if updated else 'PRESEASON_BASELINE'} for id in ids}
            (p/'candidate.json').write_text(json.dumps({'schemaVersion':1,'model':'NIL Estimation Model','season':2027,'policyVersion':3,'generatedAt':day+'T00:00:00Z','playerCount':len(rows),'byESPNId':rows}))
            return p/'candidate.json'
        assert not record(candidate('2026-10-25',False),p/'stock')['appended']
        assert record(candidate('2026-11-05',True),p/'stock')['appended']
        assert record(candidate('2026-11-05',True),p/'stock')['appended'] # same calendar day updates in place
        manifest=json.loads((p/'stock/manifest_2027.json').read_text())
        assert manifest['dates']==['2026-11-05']
        month=json.loads((p/'stock/2026-11.json').read_text())
        assert month['byESPNId'][ids[0]]==[170000]
        assert month['byESPNId'][ids[1]]==[150000]
        try:record(candidate('2026-11-04',True),p/'stock');assert False,'Backfilled older history'
        except ValueError:pass
    print('PASS model evidence weights, shooting stability, immutable stock history, same-day idempotence')

if __name__=='__main__':test()
