#!/usr/bin/env python3
"""ESPN-native inference-only features. Fitted market training labels are not published."""
import math
import numpy as np
NUMS=['gp', 'minutes', 'mpg', 'start_rate', 'ppg', 'rpg', 'apg', 'points_per30', 'rebs_per30', 'assists_per30', 'steals_per30', 'blocks_per30', 'tov_per30', 'fouls_per30', 'oreb_per30', 'dreb_per30', 'fga_per30', 'two_pa_per30', 'three_pa_per30', 'fta_per30', 'fts_drawn_per_fga', 'ts_pct', 'efg_pct', 'two_pct', 'three_pct', 'ft_pct', 'three_share', 'ast_to', 'usage_proxy_per30', 'team_rank', 'team_rank_pct', 'career_seasons', 'prior_year_mpg', 'prior_year_ppg', 'prior_year_ts_pct', 'pct_minutes_available', 'shot_volume', 'three_pa', 'two_pa', 'ft_attempts']
CATS=['position', 'conference']
def number(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else np.nan
    except (TypeError,ValueError): return np.nan

def safe_div(x,y): return x/y if np.isfinite(x) and np.isfinite(y) and y>0 else np.nan

def feat(row, seasons, context):
    gp=number(row.get('gp'));minutes=number(row.get('minutes'))
    mpg=number(row.get('mpg'))
    if not np.isfinite(minutes) and np.isfinite(gp) and np.isfinite(mpg):minutes=gp*mpg
    def stat(k):return number(row.get(k))
    num={k:np.nan for k in NUMS}
    num.update(gp=gp,minutes=minutes,mpg=mpg,start_rate=safe_div(stat('gs'),gp),
      ppg=stat('ppg'),rpg=stat('rpg'),apg=stat('apg'),
      points_per30=safe_div(stat('pts')*30,minutes),rebs_per30=safe_div(stat('reb')*30,minutes),
      assists_per30=safe_div(stat('ast')*30,minutes),steals_per30=safe_div(stat('stl')*30,minutes),
      blocks_per30=safe_div(stat('blk')*30,minutes),tov_per30=safe_div(stat('tov')*30,minutes),
      fouls_per30=safe_div(stat('pf')*30,minutes),oreb_per30=safe_div(stat('oreb')*30,minutes),
      dreb_per30=safe_div(stat('dreb')*30,minutes),fga_per30=safe_div(stat('fga')*30,minutes),
      two_pa_per30=safe_div(stat('two_pa')*30,minutes),three_pa_per30=safe_div(stat('three_pa')*30,minutes),
      fta_per30=safe_div(stat('fta')*30,minutes),fts_drawn_per_fga=safe_div(stat('fta'),stat('fga')),
      ts_pct=stat('ts_pct'),efg_pct=stat('efg_pct'),two_pct=stat('two_pt_pct'),
      three_pct=stat('three_pt_pct'),ft_pct=stat('ft_pct'),
      three_share=safe_div(stat('three_pa'),stat('fga')),ast_to=safe_div(stat('ast'),stat('tov')),
      usage_proxy_per30=safe_div(30*(stat('fga')+.44*stat('fta')+stat('tov')),minutes),
      career_seasons=len({int(s['season']) for s in seasons if s.get('season')}),
      pct_minutes_available=safe_div(minutes,gp*40) if np.isfinite(gp) else np.nan,
      shot_volume=stat('fga')+.44*stat('fta') if np.isfinite(stat('fga')) and np.isfinite(stat('fta')) else np.nan,
      three_pa=stat('three_pa'),two_pa=stat('two_pa'),ft_attempts=stat('fta'))
    rank=number(context.get('rank'));rank_total=number(context.get('rankTotal'))
    num['team_rank']=rank;num['team_rank_pct']=safe_div(rank,rank_total)
    prev=[s for s in seasons if number(s.get('season'))<number(row.get('season'))]
    if prev:
        p=max(prev,key=lambda z:number(z.get('season')))
        num['prior_year_mpg']=number(p.get('mpg'))
        num['prior_year_ppg']=number(p.get('ppg'))
        num['prior_year_ts_pct']=number(p.get('ts_pct'))
    cat={'position':str(row.get('position') or 'Unknown').upper(),
      'conference':str(context.get('conference') or 'Unknown')}
    return num|cat

