#!/usr/bin/env python3
"""OFFLINE, never-published real-model stress test of 2026-27 update readiness.

Uses the saved public factual snapshot and real encrypted production scorer
inside Actions. Inserts explicitly SIMULATED 2026-27 games into a TEMP copy.
Scores ESPN IDs from every first-year category plus a returning D-I player,
and exercises Stock Watch on a TEMP copy. Absolutely no source data writeback.
"""
import copy,datetime,json,math,pathlib,shutil,sys,tempfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from nil_season_engine import run,past_seasons,STATS,MAKES
from record_stock_history import record

ROOT=pathlib.Path(__file__).resolve().parents[2]
def read(x):return json.loads(pathlib.Path(x).read_text())
def write(x,v):pathlib.Path(x).write_text(json.dumps(v,separators=(',',':'))+'\n')
def fake_season(gp,mpg,team_id,position,style='neutral',old=None):
 minutes=gp*mpg
 if old and old.get('minutes') and old.get('gp'):
  old_minutes=float(old['minutes'])
  row={'season':2027,'seasonLabel':'2026-27','gp':gp,'minutes':minutes,
       'teamId':str(team_id),'position':position or old.get('position'),'gs':gp*min(1,float(old.get('gs') or 0)/max(1,float(old['gp'])))}
  for k in STATS+MAKES+('fgm',):
   row[k]=float(old.get(k) or 0)*minutes/old_minutes
 else:
  rates={'pts':24 if style=='breakout' else 12 if style=='low' else 17,
         'reb':7 if style=='breakout' else 4.5,'ast':5 if style=='breakout' else 3,
         'stl':1.0,'blk':.4,'tov':1.6,'pf':2.3,'oreb':1.1,'dreb':5.9 if style=='breakout' else 3.4,
         'two_pa':13 if style=='breakout' else 7,'three_pa':6 if style=='breakout' else 4,
         'fta':4 if style=='breakout' else 2.7}
  row={'season':2027,'seasonLabel':'2026-27','gp':gp,'minutes':minutes,
       'teamId':str(team_id),'position':position,'gs':int(gp*(.8 if mpg>=28 else .25))}
  for k,v in rates.items():row[k]=v*minutes/30
  row['two_pm']=row['two_pa']*(.58 if style=='breakout' else .51)
  row['three_pm']=row['three_pa']*(.40 if style=='breakout' else .34)
  row['ftm']=row['fta']*.75
  row['fgm']=row['two_pm']+row['three_pm']
  row['pts']=2*row['two_pm']+3*row['three_pm']+row['ftm']
  row['fga']=row['two_pa']+row['three_pa']
 row['fga']=row['two_pa']+row['three_pa']
 row['fgm']=row['two_pm']+row['three_pm']
 row['pts']=2*row['two_pm']+3*row['three_pm']+row['ftm']
 row['ppg']=row['pts']/gp
 row['rpg']=row['reb']/gp
 row['apg']=row['ast']/gp
 row['mpg']=mpg
 row['two_pt_pct']=row['two_pm']/max(.01,row['two_pa'])
 row['three_pt_pct']=row['three_pm']/max(.01,row['three_pa'])
 row['ft_pct']=row['ftm']/max(.01,row['fta'])
 row['fg_pct']=row['fgm']/max(.01,row['fga'])
 row['efg_pct']=(row['fgm']+.5*row['three_pm'])/max(.01,row['fga'])
 row['ts_pct']=row['pts']/(2*(row['fga']+.44*row['fta']))
 return row

def main():
 public=ROOT/'public'
 factual=read(public/'portal_factual_data.json')
 frozen=read(public/'stock_watch/preseason_2027.json')['byESPNId']
 roster=read(ROOT/'data/roster_2027_advanced.json')['players']
 roster_map={str(row[0]):(str(row[2]),str(row[3] or 'G')) for row in roster}
 teamctx_path=pathlib.Path(sys.argv[1])
 assert teamctx_path.exists(),teamctx_path
 ctx=read(teamctx_path)
 supported={str(t.get('espnTeamId')) for t in ctx['teams']}
 rookies=['5185443','5345014','5458831','5312303','5142731']
 assert all(pid in frozen and pid in roster_map for pid in rookies)
 assert all(roster_map[pid][0] in supported for pid in rookies)
 returning=[]
 for pid,entry in factual['players'].items():
  if pid not in frozen or pid not in roster_map or roster_map[pid][0] not in supported:continue
  old=next((s for s in entry.get('seasons',[]) if int(s.get('season') or 0)==2026
            and float(s.get('gp') or 0)>=18 and float(s.get('minutes') or 0)>=400),None)
  if old:returning.append((pid,old))
 assert returning,'No verified returner for real model synthetic test'
 veteran_id,old_vet=returning[0]
 ids=rookies+[veteran_id]
 exposures={}
 with tempfile.TemporaryDirectory(prefix='synthetic_nil_2027_') as td:
  tmp=pathlib.Path(td)
  stock=tmp/'stock_watch'
  shutil.copytree(public/'stock_watch',stock)
  assert not read(stock/'manifest_2027.json')['dates']
  for stage,day,gp,mpg in [
   ('game1','2026-11-10',1,30),
   ('game10','2026-12-10',10,30),
   ('game30','2027-03-05',30,30)]:
   src=copy.deepcopy(factual)
   src['latestSeason']=2027
   src['generatedAt']=day+'T12:00:00Z'
   for i,pid in enumerate(ids):
    team_id,pos=roster_map[pid]
    cur_mpg=6 if pid=='5312303' else mpg
    if pid==veteran_id:
     entry=src['players'][pid]
     cur=fake_season(gp,cur_mpg,team_id,pos,old=old_vet)
    else:
     entry=src['players'].setdefault(pid,{'seasons':[],'latest':None})
     # First-year athletes still have zero older college box appearances.
     seasons=[s for s in entry.get('seasons',[]) if int(s.get('season') or 0)<2027]
     if any(int(s.get('gp') or 0)>0 for s in seasons):
      raise AssertionError('Non-newcomer fixture: '+pid)
     cur=fake_season(gp,cur_mpg,team_id,pos,'breakout' if pid=='5458831' else 'neutral')
    entry['seasons']=[x for x in entry.get('seasons',[]) if int(x.get('season') or 0)!=2027]+[cur]
    entry['latest']=cur
   team=copy.deepcopy(ctx)
   team['retrievedAtUTC']=day+'T06:00:00Z'
   source_file=tmp/(stage+'_factual.json')
   team_file=tmp/(stage+'_teams.json')
   out=tmp/(stage+'_model.json')
   write(source_file,src);write(team_file,team)
   run(str(source_file),str(ROOT/'scripts/nil_model/source_data/torvik_team_context.json'),
       str(team_file),day,str(out),.50,None,str(public/'stock_watch/preseason_2027.json'))
   predicted=read(out)['byESPNId']
   exposures[stage]={}
   for pid in ids:
    row=predicted[pid]
    assert row['status']=='UPDATED',(stage,pid,row)
    assert row['games']==gp and row['minutes']==gp*(6 if pid=='5312303' else 30),(stage,pid,row)
    assert row['preseason']==frozen[pid]
    assert row['referenceOnly'] is not None
    assert 0<row['weight']<1
    assert row['updateMethod']==('HISTORICAL_RELATIVE_V4' if pid==veteran_id else 'COLD_START_RELATIVE_V1')
    assert row['priorSeason'] is None if pid!=veteran_id else row['priorSeason']==2026
    assert 20000<=row['value']<=20000000
    if stage=='game1':
     assert abs(math.log(row['value']/frozen[pid]))<math.log(1.15),(stage,pid,row)
    exposures[stage][pid]={'price':row['value'],'weight':row['weight']}
   hist=record(out,stock)
   assert hist['appended'] and hist['updated']>=len(ids),(stage,hist)
  for pid in ids:
   weights=[exposures[k][pid]['weight'] for k in ('game1','game10','game30')]
   assert weights[0]<weights[1]<weights[2],(pid,weights)
   if pid!='5312303':
    assert weights[2]>.90,(pid,weights)
   else:
    assert weights[2]>.70,(pid,weights)
  assert len(read(stock/'manifest_2027.json')['dates'])==3
  assert not read(public/'stock_watch/manifest_2027.json')['dates']
 print(json.dumps({'status':'PASS','playersSimulated':ids,
                   'groups':['high-market international','NBL professional','youth U21',
                             'prior college redshirt','HS freshman','returning D-I'],
                   'stages':exposures,'protectedPreseason':True,'stockHistoryIsolated':True}))

if __name__=='__main__':
 if len(sys.argv)!=2:raise SystemExit('Provide verified 2027 team JSON path')
 main()
