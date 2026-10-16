#!/usr/bin/env python3
"""Experimental NCAA ESPN five-man stint reconstruction and quality audit.

Read a zipped ESPN/hoopR clean PBP file. No guesswork if a five-man starter
set cannot be established from first-substitution and player-event evidence.
Does not pretend this is possession RAPM; samples stints for future QC.
"""
from __future__ import annotations
import csv,zipfile,collections,argparse,json,math,statistics
from pathlib import Path

MISSING={'','NA','null','None','nan'}
def valid(x):return x is not None and x not in MISSING
def player(r):return r['athlete_id_1'] if valid(r['athlete_id_1']) else None
def period_secs(rows):
    n=int(rows[0]['period_number']); return 1200 if n<=2 else 300

def get_clock(r):
    try:return int(float(r['seconds_remaining_period']))
    except (ValueError,TypeError):return None

def seed_period(rows,team):
    first={}
    for r in rows:
        if r['team_id']!=team:continue
        a=player(r)
        if a is None: continue
        if r['event_type']=='Substitution':
            typ='in' if 'subbing in' in r['text'].lower() else 'out' if 'subbing out' in r['text'].lower() else 'unknown'
        else:typ='action'
        first.setdefault(a,typ)
    starters={a for a,typ in first.items() if typ in ('out','action')}
    return starters, first

def build_period(rows,home,away, gid, official_first_half=None):
    season=rows[0]['season'];per=int(rows[0]['period_number'])
    full=period_secs(rows)
    seeds={t:seed_period(rows,t)[0] for t in (home,away)}
    if per==1 and official_first_half:
        for team in (home,away):
            verified=official_first_half.get(team)
            if verified is not None and len(verified)==5:
                seeds[team]=set(verified)
    problems=[]
    for t in (home,away):
        if len(seeds[t])!=5: problems.append(f'seed_{t}_{len(seeds[t])}')
    if problems:return {'ok':False,'reason':';'.join(problems),'period':per,'game_id':gid,'stints':[],'violations':[],'duration':0,'expected_duration':full,'events':len(rows),'player_events':0,'on_court_events':0}
    lineup={t:set(seeds[t]) for t in (home,away)}
    cur=full
    lastscore=None
    subs_counter=0;score_deviation=0;negative_deltas=0
    oncourt_events=0;players_events=0
    individual_sub_errors=[];moments=[]
    mins=collections.Counter();stints=[]
    current_start=cur; current_points=[0,0]
    event_types=collections.Counter()
    # Batch all rows at same time. A row can have a scoring play followed
    # by interleaved substitutions. Collect scores between events, and
    # apply all swaps at end of the common clock time.
    groups=[];g=[];prevtime=None
    for r in rows:
        clock=get_clock(r)
        if clock is None: continue
        if prevtime is not None and clock!=prevtime:
            groups.append((prevtime,g));g=[]
        g.append(r);prevtime=clock
    if g:groups.append((prevtime,g))
    for t,grp in groups:
        if t>cur+1:problems.append('clock_reset');break
        # All score increments at this timestamp belong to the interval
        # ending here (except ambiguous interleaved substitution/FT moments).
        grp_points=[0,0]
        for sr in grp:
            try:
                ph=int(float(sr['home_score']));pa=int(float(sr['away_score']))
                if lastscore is not None:
                    grp_points[0]+=ph-lastscore[0]
                    grp_points[1]+=pa-lastscore[1]
                lastscore=(ph,pa)
            except (ValueError,TypeError):pass
        dur=max(0,cur-t)
        if dur:
            stints.append({'game_id':gid,'season':season,'period':per,'home_team_id':home,'away_team_id':away,
                'start_remaining':cur,'end_remaining':t,'duration_s':dur,
                'home_players':'|'.join(sorted(lineup[home])),'away_players':'|'.join(sorted(lineup[away])),
                'home_pts':grp_points[0],'away_pts':grp_points[1]})
            for a in lineup[home] | lineup[away]:mins[a]+=dur
            current_points=[0,0]
        cur=t
        outs=collections.defaultdict(set);ins=collections.defaultdict(set)
        for r in grp:
            a=player(r);team=r['team_id'];kind=r['event_type'];event_types[kind]+=1
            if kind=='Substitution' and team in lineup and a:
                if 'subbing out' in r['text'].lower():outs[team].add(a)
                elif 'subbing in' in r['text'].lower():ins[team].add(a)
                subs_counter+=1
            elif a and team in lineup:
                players_events+=1
                if a in lineup[team]:oncourt_events+=1
                # Events at substitution timestamps may include the newly
                # subbed-in player. Do not flag these as off-court errors.
                elif not any(s['athlete_id_1']==a and s['event_type']=='Substitution' for s in grp):
                    individual_sub_errors.append((t,team,a,kind))
        if any(outs.values()) or any(ins.values()):
            for team in (home,away):
                if outs[team]-lineup[team]:individual_sub_errors.append((t,team,'bad_out',sorted(outs[team]-lineup[team])))
                if ins[team]&lineup[team]:individual_sub_errors.append((t,team,'bad_in',sorted(ins[team]&lineup[team])))
                lineup[team].difference_update(outs[team]);lineup[team].update(ins[team])
                if len(lineup[team])!=5: problems.append(f'lineup_count_{team}_{len(lineup[team])}@{t}')
    if cur>0 and not problems:
        stints.append({'game_id':gid,'season':season,'period':per,'home_team_id':home,'away_team_id':away,
            'start_remaining':cur,'end_remaining':0,'duration_s':cur,
            'home_players':'|'.join(sorted(lineup[home])),'away_players':'|'.join(sorted(lineup[away])),
            'home_pts':current_points[0],'away_pts':current_points[1]})
        for a in lineup[home] | lineup[away]:mins[a]+=cur
    duration=sum(s['duration_s'] for s in stints)
    reasons=problems+(['event_off_court'] if individual_sub_errors else [])
    return {'ok':not reasons and duration==full,'reason':';'.join(reasons) if reasons else None,'period':per,'game_id':gid,
        'stints':stints,'violations':individual_sub_errors[:12],'num_subs':subs_counter,
        'on_court_events':oncourt_events,'player_events':players_events,'duration':duration,
        'expected_duration':full,'players':len(mins),'events':len(rows),'event_types':dict(event_types)}

def audit_game(rows, official_first_half=None):
    gid=rows[0]['game_id'];home=rows[0]['home_team_id'];away=rows[0]['away_team_id']
    per=collections.defaultdict(list)
    for r in rows:
        if valid(r['period_number']):per[r['period_number']].append(r)
    pp=[build_period(rr,home,away,gid, official_first_half=official_first_half) for _,rr in sorted(per.items(),key=lambda x:int(x[0]))]
    return {'id':gid,'home':rows[0].get('home_team_name',rows[0]['home_team_id']),'away':rows[0].get('away_team_name',rows[0]['away_team_id']),
            'periods':len(pp),'ok_periods':sum(x['ok'] for x in pp),
            'ok':bool(pp) and all(x['ok'] for x in pp),
            'results':pp}

def main():
    pa=argparse.ArgumentParser();pa.add_argument('zip');pa.add_argument('--max-games',type=int,default=400)
    pa.add_argument('--out',default='/mnt/data/rapm_audit');arg=pa.parse_args()
    path=Path(arg.out);path.mkdir(exist_ok=True,parents=True)
    report=[]; selected=[];rows=[];last=None
    with zipfile.ZipFile(arg.zip) as z,z.open(next(x for x in z.namelist() if x.endswith('.csv') and not x.startswith('__MACOSX/'))) as f:
        rr=csv.DictReader((ln.decode('utf-8-sig',errors='replace') for ln in f))
        for r in rr:
            gid=r['game_id']
            if last is not None and gid!=last:
                result=audit_game(rows);report.append(result)
                if result['ok']:selected.extend(s for q in result['results'] for s in q['stints'])
                if len(report)>=arg.max_games:break
                rows=[]
            rows.append(r);last=gid
        else:
            if rows:
                result=audit_game(rows);report.append(result)
                if result['ok']:selected.extend(s for q in result['results'] for s in q['stints'])
    reasons=collections.Counter(r['reason'] for g in report for r in g['results'] if not r['ok'])
    summary={'games_checked':len(report),'fully_valid_games':sum(g['ok'] for g in report),
        'periods_checked':sum(g['periods'] for g in report),'valid_periods':sum(g['ok_periods'] for g in report),
        'fully_valid_pct':sum(g['ok'] for g in report)/max(1,len(report)),
        'valid_period_pct':sum(g['ok_periods'] for g in report)/max(1,sum(g['periods'] for g in report)),
        'valid_stints':len(selected),'issue_reasons':dict(reasons),
        'flagged_examples':[{'game_id':g['id'],'teams':f"{g['away']} @ {g['home']}",'issues':[(p['period'],p['reason'],p['violations'][:3]) for p in g['results'] if not p['ok']]} for g in report if not g['ok']][:12],
        'notes':['Starter inferred from first action/first-out prior to first-in per player in each period; this is a stringent heuristic, not official starters.',
                 'At same-clock substitutions, scores can be misattributed to a lineup; per-event score attribution needs additional refinement.',
                 'Do not fit or interpret RAPM from stints until independent box-score minutes and possession-count reconciliation pass.']}
    (path/'lineup_qa_summary.json').write_text(json.dumps(summary,indent=2))
    (path/'game_period_qa.json').write_text(json.dumps([{'game_id':g['id'],'teams':f"{g['away']} @ {g['home']}",'ok':g['ok'],'periods':[{k:p[k] for k in ('period','ok','reason','duration','expected_duration','events','player_events','on_court_events')} for p in g['results']]} for g in report],indent=2))
    if selected:
        with open(path/'candidate_stints.csv','w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
