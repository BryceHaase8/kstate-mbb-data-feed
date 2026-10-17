#!/usr/bin/env python3
"""Small, reviewable research summary of 2026 RAPM V2: never updates Portal."""
import csv,json,math,statistics
from pathlib import Path
import numpy as np
BASE=Path('research_qa')
model=json.loads((BASE/'rapm_v2_model_2026.json').read_text())
audit=json.loads((BASE/'rapm_v2_model_2026_audit.json').read_text())
variants=model['variants']; old=json.loads((BASE/'rapm_official_model_2026.json').read_text())
lookup={}
p=Path('data/current_player_season_stats.csv')
if p.is_file():
    with p.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if str(r.get('season'))=='2026':
                lookup[str(r.get('athlete_id'))]={'name':r.get('player_name'),
                    'team':r.get('team_name'),'teamId':r.get('team_id')}
player_ids={r['espnAthleteId'] for r in variants['baselineV1']}
if len({len(v) for v in variants.values()})!=1 or len(player_ids)!=len(variants['baselineV1']):
    raise RuntimeError('All variants must have the identical player cohort')
indexed={k:{r['espnAthleteId']:r for r in v} for k,v in variants.items()}
baseline=indexed['baselineV1']; full=indexed['torvikAndLuckAdjusted']
original={r['espnAthleteId']:r for r in old['ratings']}
inter=set(baseline)&set(original)
comparison=[(baseline[p]['totalRAPM'],original[p]['totalRAPM']) for p in inter]
refit_abs=[abs(a-b) for a,b in comparison]
# Refit need not exactly equal old V1 if Torvik missing-team exclusions changed
# the sample. Report overlap and delta transparently.
high=[i for i in player_ids if baseline[i]['cleanPossessionExposure']>=1000]
deltas=[full[i]['totalRAPM']-baseline[i]['totalRAPM'] for i in high]
def percentiles(vals):
    if not vals:return None
    return {'p50':round(float(np.median(vals)),3),'p90':round(float(np.quantile(vals,.90)),3),
            'p95':round(float(np.quantile(vals,.95)),3),'max':round(float(np.max(vals)),3)}
def corr(k1,k2,cohort):
    aa=[indexed[k1][i]['totalRAPM'] for i in cohort]
    bb=[indexed[k2][i]['totalRAPM'] for i in cohort]
    return round(float(np.corrcoef(aa,bb)[0,1]),4) if len(cohort)>5 else None
def detail(pid):
    return {'espnAthleteId':pid,**lookup.get(pid,{}),
        'verifiedExposure':baseline[pid]['cleanPossessionExposure'],
        'v1':baseline[pid]['totalRAPM'],
        'torvik':indexed['torvikInformed'][pid]['totalRAPM'],
        'luck':indexed['luckAdjusted'][pid]['totalRAPM'],
        'torvikLuck':full[pid]['totalRAPM'],
        'change':round(full[pid]['totalRAPM']-baseline[pid]['totalRAPM'],2)}
highest=sorted(high,key=lambda i:full[i]['totalRAPM']-baseline[i]['totalRAPM'],reverse=True)
spots={'Flory Bidunga':'5044426','Milan Momcilovic':'4848637',
'JT Toppin':'5143604','Moustapha Thiam':'5149078',
'Robert Wright III':'5060709','Terrence Brown':'5177233'}
report={'schemaVersion':1,'season':2026,'status':'RESEARCH_ONLY_NOT_VALIDATED_FORECAST',
    'samePossessionsAllVariants':True,'gamesAccepted':model['gamesAccepted'],
    'cleanPossessions':model['cleanPossessions'],'players':len(player_ids),
    'officialMinuteCoverage':model['verifiedMinuteCoverageInFit'],
    'luck3AttemptsAttributed':audit.get('luck3AttemptsAttributed'),
    'luckFTAttemptsAttributed':audit.get('luckFTAttemptsAttributed'),
    'luckDeltaPointsTotal':audit.get('luckDeltaPointsTotal'),
    'torvikMissingGameExclusions':audit.get('torvikMissingGameExclusions'),
    'highExposureCutoff':1000,'highExposurePlayers':len(high),
    'highExposureCorrelation':{k:corr('baselineV1',k,high) for k in variants if k!='baselineV1'},
    'highExposureAbsoluteChangePointsPer100':percentiles([abs(d) for d in deltas]),
    'highExposureMeanDelta':round(float(np.mean(deltas)),3),
    'baselineRefitVsOfficialV1':{'oldPlayers':len(old['ratings']),'sharedPlayers':len(inter),
       'refitMedianAbsDiff':round(float(np.median(refit_abs)),3) if refit_abs else None,
       'refitP90AbsDiff':round(float(np.quantile(refit_abs,.9)),3) if refit_abs else None},
    'namedSpotchecks':{name:detail(pid) if pid in baseline else None for name,pid in spots.items()},
    'largestPositiveChangesHighExposure':[detail(i) for i in highest[:15]],
    'largestNegativeChangesHighExposure':[detail(i) for i in highest[-15:][::-1]],
    'cautions':[
      'Final 2025-26 Torvik ratings are retrospective, not available as-of earlier games; cannot use as out-of-time predictive validation.',
      'Opponent lineups and team effects already exist in baseline RAPM: Torvik is a candidate offset, not a proven improvement.',
      '3P/FT posterior skill estimates exclude the current game but include other same-season future games. Future daily workflow must use past games only.',
      'Full production use awaits held-out next-season value and official-minute coverage review.']}
dest=BASE/'rapm_v2_diagnostic_summary.json'
dest.write_text(json.dumps(report,indent=2)+'\n')
print('RAPM V2 DIAGNOSTICS',json.dumps({k:report[k] for k in
    ['gamesAccepted','cleanPossessions','players','highExposurePlayers',
     'luck3AttemptsAttributed','luckFTAttemptsAttributed',
     'highExposureAbsoluteChangePointsPer100','highExposureCorrelation']}))
