#!/usr/bin/env python3
"""Experimental ESPN possession state machine. Flags ambiguity; never calls this publication-ready RAPM.
Input: previously lineup- and score-reconciled games, validated five-player stints.
Output: offense/defense lineup per discrete observed possession, with audit and anomaly flags.
"""
from __future__ import annotations
import pandas as pd, numpy as np, collections, re, json
from pathlib import Path
ROOT=Path(__file__).parent
RE_FT=re.compile(r'free throw\s*(\d+)\s*of\s*(\d+)',re.I)
EV_SCORING={'2PT Shot','MadeFreeThrow'}
REQUIRED=['game_id','period_number','seconds_remaining_period','event_type','team_id','text','home_score','away_score']

def ft_last(r):
    m=RE_FT.search(r.text or '')
    if not m:return None
    return int(m.group(1)) == int(m.group(2))

def ft_made(r):return bool(re.search(r'\bmakes?\b|\bmade\b',str(r.text),re.I))

def shot_made(r):return str(r.shot_made).lower()=='true' or bool(re.search(r'\bmakes?\b',str(r.text),re.I))

def matchup_index(s):
    groups={}
    for (gid,p), g in s.groupby(['game_id','period'],sort=False):
        # Search intervals ordered by descending start time.
        g=g.sort_values(['start_remaining','end_remaining'],ascending=False)
        groups[(str(gid),int(p))]=g.to_dict('records')
    return groups

def lineups(stints,t):
    for v in stints:
        if v['start_remaining']>=t>=v['end_remaining']:
            return v['home_players'],v['away_players']
    return None

def score_deltas(df):
    out=[]; h0=a0=0; neg=0
    for r in df.itertuples(index=False):
        h=int(float(r.home_score));a=int(float(r.away_score));dh=h-h0;da=a-a0
        if dh<0 or da<0:neg+=1
        out.append((max(0,dh),max(0,da)))
        h0=h;a0=a
    return out,neg,(h0,a0)

def run_one(gid,df,index):
    home=str(df.iloc[0].home_team_id);away=str(df.iloc[0].away_team_id)
    allpos=[]; game_flags=collections.Counter(); statistics={t:collections.Counter() for t in (home,away)}
    ds,neg,final=score_deltas(df)
    if neg:game_flags['negative_score_correction']+=neg
    df=df.copy().reset_index(drop=True)
    df['dh']=[x[0] for x in ds];df['da']=[x[1] for x in ds]
    total_points=collections.Counter();flagr=0
    for per,pdf in df.groupby('period_number',sort=False):
        stints=index.get((gid,int(per)),[])
        if not stints:game_flags['no_stints']+=1;continue
        pdf=pdf.reset_index(drop=True)
        owner=None;count=0; start_time=None; begin_lineup=None;pts=0
        flags=set(); shot_pending=False;ft_seq=None; saw_event=False
        def begin(team,r):
            nonlocal owner,start_time,begin_lineup,pts,flags,shot_pending,saw_event,ft_seq
            owner=team;start_time=int(float(r.seconds_remaining_period))
            begin_lineup=lineups(stints,start_time)
            pts=0;flags=set();shot_pending=False;saw_event=True;ft_seq=None
        def finish(reason,t):
            nonlocal owner,start_time,begin_lineup,pts,flags,shot_pending,saw_event,ft_seq,count
            if owner is None:return
            count+=1
            if begin_lineup is None:flags.add('lineup_missing')
            ap=begin_lineup
            if ap:
                hplayers,aplayers=ap
                allpos.append({'game_id':gid,'period':int(per),'off_team':owner,'def_team':away if owner==home else home,
                    'off_players':hplayers if owner==home else aplayers,'def_players':aplayers if owner==home else hplayers,
                    'points':pts,'clock_start':start_time,'clock_end':t,'end_reason':reason,'flags':'|'.join(sorted(flags))})
            else:game_flags['missing_lineup']+=1
            if flags:
                for f in flags:game_flags[f]+=1
            owner=None;start_time=None;begin_lineup=None;pts=0;flags=set();shot_pending=False;saw_event=False;ft_seq=None
        for i,r in enumerate(pdf.itertuples(index=False)):
            team=str(r.team_id) if str(r.team_id) in (home,away) else None
            clock=int(float(r.seconds_remaining_period)) if str(r.seconds_remaining_period) not in ('NA','') else None
            typ=str(r.event_type);txt=str(r.text)
            # Establish current offense before attributing points. A made shot/FT may
            # be the FIRST observable event of a possession; that is not an error.
            if typ in ('2PT Shot','MadeFreeThrow','Turnover') and team:
                if owner is None:begin(team,r)
                elif owner != team and typ != 'MadeFreeThrow':
                    flags.add('implicit_possession_switch')
                    finish('implicit_switch',clock)
                    begin(team,r)
            # Record scoreboard deltas AFTER establishing the scoring possession.
            for team_scored,points in ((home,int(r.dh)),(away,int(r.da))):
                if points:
                    total_points[team_scored]+=points
                    if owner is None:
                        begin(team_scored,r)
                        flags.add('score_no_offensive_event')
                    if owner!=team_scored:
                        flags.add('opponent_score_during_possession')
                        game_flags['orphan_opponent_points']+=points
                        # Exclude the disputed points rather than crediting opponents.
                    else:pts+=points
            if typ=='2PT Shot' and team:
                statistics[team]['fga']+=1
                if shot_made(r):statistics[team]['fgm']+=1
                if owner is None:begin(team,r)
                if shot_made(r):
                    # And-one check. Ignore sub/foul/rebounds/timeouts between FG and immediate FT.
                    andone=False
                    for j in range(i+1,min(i+12,len(pdf))):
                        n=pdf.iloc[j]; nt=str(n.event_type)
                        ntm=str(n.team_id)
                        diff=clock-int(float(n.seconds_remaining_period))
                        if diff>3:break
                        if nt=='MadeFreeThrow':andone=(ntm==team);break
                        if nt in ('2PT Shot','Turnover') or (nt=='Rebound' and 'Defensive' in str(n.text)):break
                    if andone: flags.add('and_one');shot_pending=True
                    else:finish('made_fg',clock)
            elif typ=='Turnover' and team:
                statistics[team]['tov']+=1
                if owner is None:begin(team,r)
                finish('turnover',clock)
            elif typ=='Rebound' and team:
                t=txt.lower()
                if 'offensive rebound' in t:
                    statistics[team]['oreb']+=1
                    if owner is None:begin(team,r);flags.add('orphan_oreb')
                    elif owner!=team:flags.add('offensive_rebound_wrong_owner')
                elif 'defensive rebound' in t:
                    statistics[team]['dreb']+=1
                    if owner is not None:
                        if team==owner:flags.add('def_reb_same_owner')
                        finish('def_rebound',clock)
                    # Next possession begins with offensive play, do not count an empty record.
                # deadball rebound does NOT count as OREB and does not change ownership.
            elif typ=='MadeFreeThrow' and team:
                statistics[team]['fta']+=1
                if ft_made(r):statistics[team]['ftm']+=1
                if owner is None:begin(team,r);flags.add('free_throw_without_known_possession')
                elif owner!=team:
                    # May be technical FT on defense, or former offense after another phase.
                    flags.add('free_throw_by_nonpossessor');game_flags['technical_or_ambiguous_ft']+=1
                    continue
                if ft_last(r) is None:
                    flags.add('unnumbered_ft')
                elif ft_last(r):
                    if ft_made(r):finish('last_ft_made',clock)
                    # on last missed FT, wait for rebound or next action
            elif typ=='Jumpball':
                # May be a held-ball tie-up; leave ownership until positive possession evidence.
                pass
            elif typ=='End Period':
                if owner is not None:finish('period_end',0)
        if owner is not None:finish('period_end_unmarked',0)
    for t in (home,away):
        est=statistics[t]['fga']-statistics[t]['oreb']+statistics[t]['tov']+0.44*statistics[t]['fta']
        count=sum(p['off_team']==t for p in allpos)
        statistics[t]['poss_est']=round(est,2)
        statistics[t]['state_poss']=count
        statistics[t]['poss_diff']=round(count-est,2)
        statistics[t]['points']=total_points[t]
    return allpos,game_flags,statistics,final

def main():
    s=pd.read_csv(ROOT/'data/candidate_stints.csv',dtype={'game_id':str,'home_team_id':str,'away_team_id':str,'home_players':str,'away_players':str})
    bad=set(json.loads((ROOT/'data/score_validation.json').read_text())['bad_game_ids'])
    s=s[~s.game_id.isin(bad)].copy()
    index=matchup_index(s)
    e=pd.read_pickle(ROOT/'verified_events.pkl',compression='gzip')
    e=e[e.game_id.isin(set(s.game_id))]
    out=[]; audits=[]; global_flags=collections.Counter()
    for k,x in e.groupby('game_id',sort=False):
        ps,fl,stat,score=run_one(k,x,index)
        out.extend(ps)
        global_flags.update(fl)
        audit={'game_id':k,'possessions':len(ps),'flags':dict(fl),'final_home':score[0],'final_away':score[1]}
        for team,v in stat.items():
            for metric,val in v.items():audit[f'{team}_{metric}']=val
        h=x.iloc[0].home_team_id; a=x.iloc[0].away_team_id
        audit['max_poss_diff']=max(abs(stat[h]['poss_diff']),abs(stat[a]['poss_diff']))
        audit['total_points_mismatch']=abs(stat[h]['points']-score[0])+abs(stat[a]['points']-score[1])
        audit['severe_events']=sum(v for n,v in fl.items() if n not in ('and_one',))
        audits.append(audit)
    frame=pd.DataFrame(out);qa=pd.DataFrame(audits)
    frame.to_pickle(ROOT/'possessions_all.pkl',compression='gzip')
    qa.to_csv(ROOT/'possession_qa.csv',index=False)
    # Verify ATTRIBUTED possession points, not merely scoreboard deltas.
    # Scores can be corrected and technical points can be orphaned from a possession.
    # Both home and away totals must match independently.
    matchup={gid:(str(g.iloc[0].home_team_id),str(g.iloc[0].away_team_id)) for gid,g in e.groupby('game_id',sort=False)}
    tally=frame.groupby(['game_id','off_team']).points.sum().to_dict()
    qa['home_attributed_points']=[int(tally.get((str(gid),matchup[str(gid)][0]),0)) for gid in qa.game_id]
    qa['away_attributed_points']=[int(tally.get((str(gid),matchup[str(gid)][1]),0)) for gid in qa.game_id]
    qa['home_attribution_gap']=qa.final_home-qa.home_attributed_points
    qa['away_attribution_gap']=qa.final_away-qa.away_attributed_points
    qa['exact_attributed_score']=(qa.home_attribution_gap==0)&(qa.away_attribution_gap==0)
    qa.to_csv(ROOT/'possession_qa.csv',index=False)
    valid=(qa.max_poss_diff<=5)&qa.exact_attributed_score&(qa.total_points_mismatch==0)
    selected=set(qa.loc[valid,'game_id'])
    frame[frame.game_id.isin(selected)].to_csv(ROOT/'possession_stints_QA_pass.csv',index=False)
    report={'games':len(qa),'complete_possessions':len(frame),'quality_games':len(selected),
            'quality_possessions':int(frame.game_id.isin(selected).sum()),
            'exact_attributed_score_games':int(qa.exact_attributed_score.sum()),
            'median_max_poss_diff':float(qa.max_poss_diff.median()),
            'median_severe_events':float(qa.severe_events.median()),
            'event_flags':dict(global_flags),
            'poss_diff_quantiles':{str(k):float(v) for k,v in qa.max_poss_diff.quantile([0,.25,.5,.75,.9,.95,.99,1]).items()}}
    (ROOT/'possession_engine_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
