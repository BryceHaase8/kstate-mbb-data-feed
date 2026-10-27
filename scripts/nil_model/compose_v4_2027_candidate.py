#!/usr/bin/env python3
"""Research-only V4 preseason baseline composition for the public data feed.

Does not overwrite Stock Watch, any public price, or private freshman prices.
The direct V4 prices are an offline 2025-26 reconstruction using saved source
data, and become a one-time 2026-27 frozen starting valuation. The 52
unresolved identities retain their exact previously published prices.
"""
import argparse
import json
import pathlib

FLOOR=20_000

def v(x):
    if isinstance(x, dict): x=x.get('value')
    if type(x) not in (int,float) or not 15000<=x<=20_000_000:
        raise ValueError('Invalid historical valuation')
    return int(round(x))

def compose(old, recovered, freshman_ids=None):
    if old.get('schemaVersion')!=1 or old.get('season')!=2027: raise ValueError('Wrong old season')
    prices=old.get('byESPNId') or {}
    if len(prices)<3000:raise ValueError('Original site baseline is missing or incomplete')
    if recovered.get('model')!='V4_RECOMPUTED_FROZEN_2026' or recovered.get('season')!=2027:
        raise ValueError('Not a verified V4 source')
    v4=recovered.get('byESPNId') or {}
    if len(v4)<2950:raise ValueError('V4 recovery below expected minimum')
    if any(not str(k).isdigit() for x in (prices,v4) for k in x):
        raise ValueError('Non-ESPN identifiers')
    freshman_ids=set(freshman_ids or [])
    if freshman_ids and not freshman_ids.issubset(prices):
        raise ValueError('Freshman price identities absent from existing frozen feed')
    # Never change a declared approved freshman price.
    result={}; sources={};changes=0;floors=0
    for pid,original in prices.items():
        previous=v(original)
        if pid in freshman_ids or pid not in v4:
            amount=previous
            reason='APPROVED_FRESHMAN_PRESERVED' if pid in freshman_ids else 'EXISTING_PRICE_PRESERVED'
        else:
            raw=v(v4[pid])
            amount=max(FLOOR,raw)
            reason='V4_VERIFIED_FROZEN'
            floors+=int(raw<FLOOR)
            changes+=int(amount!=previous)
        result[pid]=amount
        sources[pid]=reason
    counts={category:sum(x==category for x in sources.values())
            for category in sorted(set(sources.values()))}
    assert set(result)==set(prices), 'Baseline creation is not allowed to drop or invent ESPN IDs'
    assert all(result[pid]==v(prices[pid]) for pid in freshman_ids), 'A freshman changed'
    payload={'schemaVersion':1,'season':2027,'asOf':'2026-10-27',
             'sourceGeneratedAt':old.get('sourceGeneratedAt'),
             'model':'NIL Estimation Model',
             'basis':'Versioned 2026-27 preseason: recovered 2025-26 V4 for verified ESPN IDs, existing prices for others',
             'baselineVersion':'V4_VERIFIED_WITH_EXPLICIT_EXISTING_FALLBACKS_2026_10_27',
             'playerCount':len(result),'byESPNId':result}
    qa={'publishReady':False,'players':len(result),'rawV4Candidates':len(v4),
        'approvedFreshmenUnchanged':len(freshman_ids),
        'v4Verified':counts.get('V4_VERIFIED_FROZEN',0),
        'oldPricesPreserved':counts.get('EXISTING_PRICE_PRESERVED',0),
        'lowEndDisplayFloors':floors,'pricesChangedFromLegacy':changes,
        'baselineESPNIdsIdentical':True,
        'requiresSeparateStockWatchMigration':True,
        'requires2027FreshmanAndRosterValidation':True}
    return payload,qa,sources

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for arg in ('old','v4','output'):
        p.add_argument('--'+arg,required=True)
    p.add_argument('--approved-freshmen')
    a=p.parse_args()
    read=lambda x:json.loads(pathlib.Path(x).read_text())
    freshmen=None
    if a.approved_freshmen:
        doc=read(a.approved_freshmen)
        freshmen=set(doc.get('byESPNId',{}))
        if not freshmen: raise ValueError('Empty verified freshmen input')
        for pid,price in doc['byESPNId'].items():
            if pid not in read(a.old).get('byESPNId',{}) or v(price)!=v(read(a.old)['byESPNId'][pid]):
                raise ValueError('Approved freshman price conflict at ESPN ID '+pid)
    candidate,qa,_=compose(read(a.old),read(a.v4),freshmen)
    path=pathlib.Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(candidate,separators=(',',':'))+'\n')
    path.with_suffix('.audit.json').write_text(json.dumps(qa,indent=2)+'\n')
    print(json.dumps(qa,indent=2))
