#!/usr/bin/env python3
"""Transparent 2026-27 cold-start NIL reference (NOT an ESPN college season).

The price-tier/position expectation is a modelling POLICY, not a verified box
score. It is used only as the *same-model reference* for comparing real 2026-27
college performance to each player's independently frozen preseason NIL price.
Never append these estimated stats to a player's factual season history.
"""
import math

FLOOR,CEILING=5_000,20_000_000

def clamp(x,low,high):
 return max(low,min(high,x))

def cold_start_reference(preseason_price,position,season,team_id):
 base=float(preseason_price)
 if not math.isfinite(base) or not FLOOR<=base<=CEILING:
  raise ValueError('Need valid published preseason NIL price')
 pos=str(position or 'G').upper()
 big='C' in pos
 wing='F' in pos and not big
 # Role is a broad staff market-informed expectation, not a proxy
 # for professional points, age, or fabricated college performance.
 band=clamp(math.log(base/50_000)/math.log(3_500_000/50_000),0,1)
 role=10+19*band**.70
 fga30=8+5*band
 three_share=.12 if big else .32 if wing else .42
 attempts3=fga30*three_share
 attempts2=fga30-attempts3
 attempts_ft=2.3+1.1*band
 pct2=.545 if big else .51
 pct3=.30 if big else .345
 pctft=.71 if big else .74
 rebs=(8 if big else 5.8 if wing else 4.1)+.8*band
 rates={'reb':rebs,'ast':(1.8 if big else 2.0 if wing else 4.0)+.6*band,
        'stl':.85,'blk':1.2 if big else .55 if wing else .22,
        'tov':1.35+.6*band,'pf':2.5,
        'oreb':2.7 if big else 1.45 if wing else .7,
        'dreb':rebs-(2.7 if big else 1.45 if wing else .7),
        'two_pa':attempts2,'three_pa':attempts3,'fta':attempts_ft}
 mins=30*role
 row={'season':season,'seasonLabel':f'{season-1}-{str(season)[-2:]}',
      'teamId':str(team_id),'position':pos,'gp':30,
      'gs':30*clamp((role-10)/19,0,1),'minutes':mins,'mpg':role}
 for key,rate in rates.items():
  row[key]=rate*mins/30
 row['two_pm']=row['two_pa']*pct2
 row['three_pm']=row['three_pa']*pct3
 row['ftm']=row['fta']*pctft
 row['fga']=row['two_pa']+row['three_pa']
 row['fgm']=row['two_pm']+row['three_pm']
 row['pts']=2*row['two_pm']+3*row['three_pm']+row['ftm']
 row['ppg']=row['pts']/30
 row['rpg']=row['reb']/30
 row['apg']=row['ast']/30
 row['two_pt_pct']=pct2
 row['three_pt_pct']=pct3
 row['ft_pct']=pctft
 row['fg_pct']=row['fgm']/row['fga']
 row['efg_pct']=(row['fgm']+.5*row['three_pm'])/row['fga']
 row['ts_pct']=row['pts']/(2*(row['fga']+.44*row['fta']))
 return row

def cold_start_relative_update(preseason,current_model,reference_model,evidence_weight):
 """Conservative bounded *relative* movement from immutable opening price.

 Model dollar-scale mismatch cannot replace a coach/staff-approved price.
 A low-level breakout may move as far as 8x on 30+ real games (not one),
 and the same cap applies to declines. These are guardrails, not forecasts.
 """
 base=float(preseason)
 now=float(current_model)
 ref=float(reference_model)
 weight=float(evidence_weight)
 if (not all(math.isfinite(x) for x in (base,now,ref,weight))
     or min(base,now,ref)<=0 or not 0<=weight<1):
  raise ValueError('Invalid cold-start baseline or model evidence')
 log_relative=clamp(math.log(now/ref),-math.log(8),math.log(8))
 return int(round(clamp(base*math.exp(weight*log_relative),FLOOR,CEILING)))
