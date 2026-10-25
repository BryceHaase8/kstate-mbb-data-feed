#!/usr/bin/env python3
"""Feature contract shared by historical training and live ESPN season scoring.

Prior seasons are restricted to season < target season. Context is restricted to
same-season ratings available at `as_of` as enforced by scorer.
"""
import math,numpy as np

def val(z):
 try:
  x=float(z);return x if math.isfinite(x) else np.nan
 except (TypeError,ValueError):return np.nan

def divide(x,y):
 x,y=val(x),val(y);return x/y if np.isfinite(x) and np.isfinite(y) and y>0 else np.nan

def enrich(core,latest,past,target_season,context=None):
 s=dict(core);past=[r for r in past if val(r.get('season'))<target_season];past.sort(key=lambda z:int(z['season']),reverse=True)
 p=past[0] if past else {};q=past[1] if len(past)>1 else {}
 s.update(prior2_mpg=val(q.get('mpg')),prior2_ppg=val(q.get('ppg')),prior2_minutes=val(q.get('minutes')),
  prior_year_start_rate=divide(p.get('gs'),p.get('gp')),
  prior_year_usage30=divide(30*(val(p.get('fga'))+.44*val(p.get('fta'))+val(p.get('tov'))),p.get('minutes')),
  prior_year_three_share=divide(p.get('three_pa'),p.get('fga')),
  prior_year_fta30=divide(30*val(p.get('fta')),p.get('minutes')),
  prior_year_3pa30=divide(30*val(p.get('three_pa')),p.get('minutes')))
 s['career_pre_minutes']=sum(val(r['minutes']) for r in past if np.isfinite(val(r.get('minutes'))))
 s['career_pre_gp']=sum(val(r['gp']) for r in past if np.isfinite(val(r.get('gp'))))
 s['career_pre_max_mpg']=max([val(r['mpg']) for r in past if np.isfinite(val(r.get('mpg')))],default=np.nan)
 s['career_pre_max_ppg']=max([val(r['ppg']) for r in past if np.isfinite(val(r.get('ppg')))],default=np.nan)
 s['current_minus_prior_mpg']=val(latest.get('mpg'))-val(p.get('mpg')) if p else np.nan
 s['current_minus_prior_ppg']=val(latest.get('ppg'))-val(p.get('ppg')) if p else np.nan
 prior_pts=sum(val(r['pts']) for r in past if np.isfinite(val(r.get('pts'))))
 s['current_vs_career30_points']=val(core.get('points_per30'))-divide(prior_pts*30,s['career_pre_minutes']) if s['career_pre_minutes'] else np.nan
 s['experience_seasons_10gp']=sum(val(r.get('gp'))>=10 for r in past)
 coef=[.16602243,.30067325,.20836273,.64476939,1.85027614,1.60850955,-1.1198,.01075546,.02311012,-.07391859,-.16563894,13.27755495,-.67106523,1.78621102,.58333765,.11189127,.00114392,.00507862,-.02052928,-.09096408,.07651178,.10960992]
 rank=val((context or {}).get('rank'));gp=val(latest.get('gp'));minutes=val(latest.get('minutes'))
 s['historical_box_impact_proxy']=np.nan
 if np.isfinite(rank) and rank>=1 and gp>=8 and minutes>=150:
  def v(k):
   x=val(latest.get(k));return float(x) if np.isfinite(x) else 0.
  a=[v(k)*30/minutes for k in ['pts','ast','reb','oreb','stl','blk','tov','pf','three_pa','fta','fga']]
  a.extend([v('ts_pct') if latest.get('ts_pct') is not None else .5,v('efg_pct') if latest.get('efg_pct') is not None else .49,divide(v('three_pa'),v('fga')) if v('fga') else 0.,v('ast')/(v('tov') or 1),val(latest.get('mpg')),minutes,gp,rank,float('G' in str(latest.get('position') or '').upper()),float('F' in str(latest.get('position') or '').upper()),float('C' in str(latest.get('position') or '').upper())])
  if all(np.isfinite(z) for z in a):s['historical_box_impact_proxy']=-11.92526177+sum(x*y for x,y in zip(a,coef))
 return s

def make_catboost_row(feat,features):
 return [str(feat.get(k) or 'Unknown') if k in {'position','conference'} else (float(val(feat.get(k))) if np.isfinite(val(feat.get(k))) else -999.) for k in features]
