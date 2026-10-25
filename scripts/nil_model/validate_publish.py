#!/usr/bin/env python3
"""Fail-closed sanity checks before publishing NIL prices (optional old snapshot)."""
import argparse,json,math,pathlib,statistics

def check(new_path,manifest_path,prior_path=None):
 n=json.loads(pathlib.Path(new_path).read_text());audit=json.loads(pathlib.Path(manifest_path).read_text());
 assert n.get('schemaVersion')==1 and n.get('model')=='NIL Estimation Model' and n.get('season')==2027 and n.get('policyVersion')==2 and 'bayesian-v2' in n.get('release','')
 assert n.get('release')==audit.get('release') and n.get('generatedAt','')[:10]==audit.get('asOf')
 rows=n.get('byESPNId') or {};assert len(rows)==n.get('playerCount') and len(rows)>=1000
 for id,r in rows.items():
  assert id.isdigit() and r.get('season')==2027 and math.isfinite(float(r['value'])) and 20000<=r['value']<=20000000
  assert r.get('status') in {'UPDATED','PRESEASON_BASELINE','NEW_PLAYER_PROVISIONAL','MISSING_CURRENT_TEAM_CONTEXT'}
  assert 0<=float(r.get('weight',0))<1.0
 assert audit.get('sha256',{}).get('model') and audit.get('sha256',{}).get('factual')
 prior=None
 if prior_path and pathlib.Path(prior_path).exists():
  prior=json.loads(pathlib.Path(prior_path).read_text());o=prior.get('byESPNId',{})
  shared=set(o)&set(rows)
  assert len(shared)>=min(1000,len(o)*.8),'Major model ID coverage loss'
  med_shift=statistics.median(abs(math.log(rows[k]['value']/o[k]['value'])) for k in shared)
  if med_shift>.20:raise ValueError(f'ALERT: national median daily price log-shift {med_shift:.3f}>.20')
  print('Shared players',len(shared),'median daily abs log price movement',round(med_shift,4))
 print('PASS: NIL source validation',len(rows),'players, rollback retained')
 return True

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--new',required=True);p.add_argument('--manifest',required=True);p.add_argument('--previous');a=p.parse_args();check(a.new,a.manifest,a.previous)
