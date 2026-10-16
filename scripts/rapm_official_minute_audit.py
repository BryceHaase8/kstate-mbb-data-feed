#!/usr/bin/env python3
"""Official ESPN starter + player-minute full-season RAPM lineup gate.
Research-only. Does not publish or fit coefficients."""
import argparse,csv,collections,gzip,json,datetime
from pathlib import Path
from rapm_lineups import audit_game
def read_box(path):
    by=collections.defaultdict(list)
    with open(path,encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            gid=str(row.get('game_id',''))
            if gid:by[gid].append(row)
    return by
def as_minutes(v):
    if v is None or str(v).strip() in ('','NA','nan'):return None
    try:
        t=str(v).split(':')
        return float(t[0])+float(t[1])/60 if len(t)==2 else float(v)
    except (ValueError,TypeError):return None
def audit(pbp_path,box_path,outdir,max_games=0):
    box=read_box(box_path)
    p=Path(outdir);p.mkdir(exist_ok=True,parents=True)
    reasons=collections.Counter();sums=collections.Counter();records=[]
    def check(gid,rows):
        if gid not in box:
            sums['games_missing_official_box']+=1;return
        b=box[gid]
        starters=collections.defaultdict(set)
        official_minutes={}
        for r in b:
            team=str(r['team_id']);pid=str(r['athlete_id'])
            if str(r.get('starter','')).lower() in ('true','1','t'):starters[team].add(pid)
            m=as_minutes(r.get('minutes'))
            if m is not None:official_minutes[pid]=m
        g=audit_game(rows,official_first_half=starters)
        valid=[z for z in g['results'] if z['ok']]
        duration=sum(z['duration'] for z in valid)
        possible=sum(z['expected_duration'] for z in g['results'])
        sums['games_with_official_box']+=1
        sums['periods_total']+=g['periods'];sums['periods_lineup_valid']+=len(valid)
        sums['possible_lineup_player_minutes']+=possible*10/60
        sums['internal_valid_lineup_player_minutes']+=duration*10/60
        sums['games_with_any_valid_period']+=bool(valid)
        sums['games_with_all_valid_periods']+=g['ok']
        reconstructed=collections.Counter()
        for part in valid:
            for s in part['stints']:
                for pid in (s['home_players']+'|'+s['away_players']).split('|'):
                    reconstructed[pid]+=float(s['duration_s'])/60
        unknown=set(reconstructed)-set(official_minutes)
        diffs={pid:abs(reconstructed.get(pid,0)-m) for pid,m in official_minutes.items()}
        worst=max(diffs.values(),default=0)
        # Full game: reconstructed minutes must agree for every official player.
        # Partial game: reconstructed minutes must not exceed full-game box minutes.
        minutes_pass=bool(valid) and len(official_minutes)>=10 and not unknown and (
            all(delta<=1.01 for delta in diffs.values()) if g['ok'] else
            all(reconstructed.get(pid,0)<=m+1.01 for pid,m in official_minutes.items()))
        sums['games_with_verified_minutes']+=int(minutes_pass)
        if minutes_pass:
            sums['official_verified_lineup_player_minutes']+=duration*10/60
            sums['official_verified_periods']+=len(valid)
        elif valid:
            reasons['official_minutes_mismatch']+=1
        for z in g['results']:
            if not z['ok']:
                reasons['lineup_'+str(z['reason']).split(';')[0].split('@')[0]]+=1
        if any(len(starters[t])!=5 for t in (str(rows[0]['home_team_id']),str(rows[0]['away_team_id']))):
            reasons['official_starter_count_not_five']+=1
        records.append({'game_id':gid,'periods':g['periods'],'periods_valid':len(valid),
            'lineup_minutes_percent':round(duration/possible*100,2) if possible else 0,
            'official_starter_count_home':len(starters[str(rows[0]['home_team_id'])]),
            'official_starter_count_away':len(starters[str(rows[0]['away_team_id'])]),
            'official_minute_validation':minutes_pass,'max_player_minute_error':round(worst,3) if g['ok'] else '',
            'unknown_player_ids':len(unknown)})
    prev=None;rows=[];count=0
    with open(pbp_path,encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            gid=r['game_id']
            if prev is not None and gid!=prev:
                check(prev,rows);count+=1
                if count%500==0:print('Audited',count,'games',flush=True)
                if max_games and count>=max_games:break
                rows=[]
            rows.append(r);prev=gid
        else:
            if rows:check(prev,rows)
    denom=sums['possible_lineup_player_minutes']
    report={'season':2026,'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'source':'ESPN/hoopR play-by-play and independent official ESPN starters/minutes',
      'scope':'RESEARCH_ONLY_NOT_APPROVED_FOR_PLAYER_EVALUATION',
      **{k:round(v,3) for k,v in sums.items()},
      'fraction_periods_lineup_valid':round(sums['periods_lineup_valid']/max(1,sums['periods_total']),4),
      'fraction_lineup_minutes_internally_valid':round(sums['internal_valid_lineup_player_minutes']/max(1,denom),4),
      'fraction_lineup_minutes_independently_verified':round(sums['official_verified_lineup_player_minutes']/max(1,denom),4),
      'failure_reasons':dict(reasons),
      'note':'Partial-period minutes are validated as not exceeding official full-game minutes; this is weaker than full-game minute equality.'}
    with open(p/'rapm_fullseason_official_lineup_summary.json','w') as f:json.dump(report,f,indent=2)
    with open(p/'rapm_fullseason_official_lineup_games.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    print('INDEPENDENT FULL-SEASON QA',json.dumps({k:report[k] for k in
      ('games_with_official_box','games_with_verified_minutes','fraction_lineup_minutes_internally_valid',
       'fraction_lineup_minutes_independently_verified','fraction_periods_lineup_valid')},indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--pbp',default='rapm_input/pbp.csv')
    ap.add_argument('--box',default='rapm_input/box.csv')
    ap.add_argument('--output-dir',default='research_qa');ap.add_argument('--max-games',type=int,default=0)
    a=ap.parse_args();audit(a.pbp,a.box,a.output_dir,a.max_games)
