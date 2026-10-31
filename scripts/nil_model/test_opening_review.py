#!/usr/bin/env python3
"""Offline regression for approved preseason reappraisal; no private model needed."""
import copy
import json
import pathlib
import tempfile

from publish_guard import check
from record_stock_history import record

ESPN_ID = '5455519'
NEW_PRICE = 2_500_000
OLD_PRICE = 155_000
POLICY = 'STAFF_APPROVED_OPENING_PRICE_CORRECTIONS_V1'


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding='utf-8')
    return path


def run_tests():
    with tempfile.TemporaryDirectory(prefix='nil_opening_review_') as temporary:
        root = pathlib.Path(temporary)
        stock = root/'stock'
        ids = [str(4_000_000 + i) for i in range(1200)] + [ESPN_ID]
        originals = {pid: 155000 for pid in ids}
        review = {'schemaVersion':1,'season':2027,'policy':POLICY,'byESPNId':{
            ESPN_ID:{'playerName':'Juan Fernandez','teamId':'2579',
                     'sourceBaseline':OLD_PRICE,'value':NEW_PRICE,
                     'effectiveDate':'2026-10-31',
                     'reviewType':'INTERNATIONAL_PRO_PRESEASON_STAFF_REVIEWED'}
        }}
        frozen = write(stock/'preseason_2027.json', {
            'schemaVersion':1,'season':2027,'asOf':'2026-10-27',
            'byESPNId':originals})
        history = write(stock/'manifest_2027.json', {
            'schemaVersion':1,'season':2027,'baselineAsOf':'2026-10-27',
            'dates':[],'months':[]})
        corrections = write(stock/'opening_price_corrections_2027.json', review)
        def model(day, reviewed, played=False):
            prices={pid:{
                'value':OLD_PRICE,'preseason':OLD_PRICE,
                'anchorType':'FRESHMAN_HS','games':0,'status':'PRESEASON_BASELINE'
            } for pid in ids}
            if reviewed:
                prices[ESPN_ID].update({
                    'value':2_600_000 if played else NEW_PRICE,
                    'preseason':NEW_PRICE,
                    'anchorType':'INTERNATIONAL_PRO_PRESEASON_STAFF_REVIEWED',
                    'games':1 if played else 0,
                    'status':'UPDATED' if played else 'PRESEASON_BASELINE'
                })
            return {'schemaVersion':1,'model':'NIL Estimation Model','season':2027,
                'policyVersion':3,'generatedAt':day+'T00:00:00Z',
                'factualGeneratedAt':day+'T00:00:00Z',
                'playerCount':len(prices),'byESPNId':prices}
        def factual(day, season=2026):
            return {'latestSeason':season,'generatedAt':day+'T00:00:00Z'}
        before=write(root/'before.json',model('2026-10-30',False))
        after=write(root/'after.json',model('2026-10-31',True))
        facts=write(root/'facts.json',factual('2026-10-31'))
        assert check(after,before,facts,anchor=frozen,history=history,
                     opening_corrections=corrections)
        unchanged=json.loads(frozen.read_text())['byESPNId']
        assert unchanged[ESPN_ID]==OLD_PRICE
        assert not record(after,stock)['appended'], 'Repricing is NOT stock movement'
        # Regression: stale source, unrelated player edits and post-game reprices reject.
        bad=copy.deepcopy(json.loads(after.read_text()))
        bad['byESPNId'][ids[0]]['value']+=1000
        modified=write(root/'bad.json',bad)
        try:
            check(modified,before,facts,anchor=frozen,history=history,
                  opening_corrections=corrections)
        except ValueError:
            pass
        else:
            raise AssertionError('Unreviewed changes passed guard')
        bad=copy.deepcopy(json.loads(after.read_text()))
        bad['byESPNId'][ESPN_ID]['preseason']=OLD_PRICE
        write(modified,bad)
        try:
            record(modified,stock)
        except ValueError:
            pass
        else:
            raise AssertionError('Original $155k opening prior passed despite approved review')
        # Real games update from the revised $2.5m prior (the model weights it).
        next_model=write(root/'game1.json',model('2026-11-04',True,played=True))
        new_facts=write(root/'game_facts.json',factual('2026-11-04',2027))
        assert check(next_model,after,new_facts,anchor=frozen,history=history,
                     opening_corrections=corrections)
        saved=record(next_model,stock)
        assert saved['appended'] and saved['updated']==1
        assert json.loads((stock/'manifest_2027.json').read_text())['dates']==['2026-11-04']
        # Once there is dated stock history, a retroactive reprice is forbidden.
        try:
            check(after,before,facts,anchor=frozen,history=history,
                  opening_corrections=corrections)
        except ValueError:
            pass
        else:
            raise AssertionError('Retroactive opening reprice accepted after first snapshot')
        print('PASS: Juan reviewed $2.5m anchor; $155k frozen untouched; no fake stock; future updates work')


if __name__ == '__main__':
    run_tests()
