#!/usr/bin/env python3
"""Fail-closed national NIL publish guard with one-time versioned V4 migration."""
import argparse,datetime,json,math,pathlib,statistics

def load(path):
 return json.loads(pathlib.Path(path).read_text())

def check(new,old,source,anchor=None,legacy=None,history=None,rookies=None,v4=None,others=None,approved=None,pre_rebase=None,top100=None,pre_top100=None,staff_review=None,pre_staff=None,unranked=None,pre_unranked=None):
 n,o,f=load(new),load(old),load(source)
 if n.get('season')!=2027 or n.get('policyVersion')!=3:
  raise ValueError('Unexpected NIL model policy')
 if n.get('factualGeneratedAt')!=f.get('generatedAt'):
  raise ValueError('NIL predictions were not scored from current factual snapshot')
 if int(f.get('latestSeason') or 0)>2027:
  raise ValueError('Invalid ESPN factual season')
 rows=n.get('byESPNId') or {};older=o.get('byESPNId') or {}
 common=set(rows)&set(older)
 if len(common)<min(2700,int(.90*len(older))) or len(rows)<int(.90*len(older)):
  raise ValueError('Major ESPN athlete identity loss')
 asof=datetime.date.fromisoformat(n['generatedAt'][:10])
 stamp=datetime.date.fromisoformat(f['generatedAt'][:10])
 if stamp>asof:raise ValueError('Future ESPN factual data')
 current=sum(r.get('status')=='UPDATED' for r in rows.values())
 if int(f.get('latestSeason') or 0)<2027 and current:
  raise ValueError('Preseason feed invented in-season player updates')
 # The 2026-10-27 V4 baseline migration may be applied ONE TIME only,
 # against the verified archived previous baseline and EMPTY stock history.
 migration=o.get('policyVersion')==2 and n.get('policyVersion')==3
 ignored=set()
 if migration:
  if not anchor or not legacy or not history or not rookies or not v4 or not others:
   raise ValueError('V4 baseline migration must provide three rollback/QA files')
  a,b,h=load(anchor),load(legacy),load(history)
  q,v,t=load(rookies),load(v4),load(others)
  arows=a.get('byESPNId') or {};brows=b.get('byESPNId') or {}
  if a.get('baselineVersion')!='V4_3052_HS_1420_ROSTER_EXISTING_1538_2026_10_27' or a.get('season')!=2027:
   raise ValueError('Unverified V4 migration version')
  vrows=v.get('byESPNId') or {}
  qrows=q.get('byESPNId') or {}
  trows=t.get('byESPNId') or {}
  methods=t.get('methodByESPNId') or {}
  if (len(vrows)!=3052 or len(qrows)!=1420 or len(trows)!=1538 or len(arows)!=6010 or
      a.get('playerCount')!=6010 or not set(brows).issubset(vrows) or
      set(vrows)&set(qrows) or set(vrows)&set(trows) or set(qrows)&set(trows) or
      set(arows)!=set(vrows)|set(qrows)|set(trows)):
   raise ValueError('Frozen baseline did not retain exact 3052 V4 + 1420 freshmen + 1538 preserved roster identities')
  if any(arows[pid]!=price for part in (vrows,qrows,trows) for pid,price in part.items()):
   raise ValueError('Full release anchor disagrees with its component originals')
  if (set(vrows)-set(brows)!={'5281366'} or vrows.get('5281366')!=791196):
   raise ValueError('K-State Timo Malovec original V4 ESPN identity was not preserved')
  if v.get('baselineVersion')!='V4_FROZEN_SITE_V771_3052_2026_10_27' or q.get('baselineVersion')!='ROOKIE_HS_SITE_V771_ESPN_ID_2026_10_27':
   raise ValueError('Incorrect component baseline version')
  if (t.get('baselineVersion')!='CURRENT_ROSTER_EXISTING_PRICE_GAP_2026_10_27' or
      set(methods)!=set(trows) or
      sum(x=='SITE_UNMODELED_PROVISIONAL_50000' for x in methods.values())!=805 or
      sum(x=='LEGACY_MODEL_PRESEASON_PRESERVED' for x in methods.values())!=733 or
      any(trows[pid]!=50000 for pid,kind in methods.items() if kind=='SITE_UNMODELED_PROVISIONAL_50000')):
   raise ValueError('Roster-only 805 unmodeled and 733 legacy-provenance prices changed')
  if b.get('asOf')!='2026-10-24' or b.get('playerCount')!=3051:
   raise ValueError('Archived legacy snapshot is not the original frozen feed')
  if (h.get('dates') or []) or (h.get('months') or []):
   raise ValueError('Cannot migrate a preseason baseline after game-history snapshots exist')
  if h.get('baselineAsOf')!=a.get('asOf') or a.get('asOf')!='2026-10-27':
   raise ValueError('Unverified Stock Watch baseline date')
  if int(f.get('latestSeason') or 0)>=2027 or current:
   raise ValueError('Migration requires a genuine preseason factual stage')
  if any(pid not in rows or rows[pid].get('preseason')!=expected or rows[pid].get('value')!=expected or rows[pid].get('status')!='PRESEASON_BASELINE' for pid,expected in arows.items()):
   raise ValueError('Candidate does not publish the exact 3052 V4 frozen prices')
  if any(pid in older and older[pid].get('preseason')!=value for pid,value in brows.items()):
   raise ValueError('Original live NIL values do not agree with archived v2 anchors')
  ignored=set(arows)
  if any(rows[pid]['value']!=older[pid]['value'] for pid in common-ignored):
   raise ValueError('Non-V4 prices moved during explicit baseline migration')
 else:
  if int(f.get('latestSeason') or 0)<2027:
   moved={pid for pid in common if rows[pid]['value']!=older[pid]['value']}
   if moved:
    # A versioned, exact-ID staff-reviewed opening correction is permitted
    # BEFORE the first game only, never as fictitious Stock Watch movement.
    if not anchor or not history:
     raise ValueError('Preseason price moved without documented opening correction')
    if unranked and pre_unranked:
     # Exact, versioned 4th release cohort. Never reprice an unrelated ID
     # or fabricate pre-game Stock Watch appreciation.
     q,b,a,h=load(unranked),load(pre_unranked),load(anchor),load(history)
     changed=q.get('byESPNId') or {}
     source=q.get('previousByESPNId') or {}
     methods=q.get('provenanceByESPNId') or {}
     ranks=q.get('teamRankByESPNId') or {}
     previous=b.get('byESPNId') or {}
     now=a.get('byESPNId') or {}
     protection=set((load(approved).get('byESPNId') or {}) if approved else ())
     protection|=set((load(top100).get('byESPNId') or {}) if top100 else ())
     protection|=set((load(staff_review).get('byESPNId') or {}) if staff_review else ())
     if (q.get('playerCount')!=1835 or len(changed)!=1835 or
         not set(changed)==set(source)==set(methods)==set(ranks) or
         set(changed)&protection or set(moved)!=set(changed) or
         len(previous)!=6057 or len(now)!=6057 or set(previous)!=set(now) or
         any(previous.get(pid)!=val for pid,val in source.items()) or
         any(now.get(pid)!=(changed[pid] if pid in changed else val)
             for pid,val in previous.items()) or
         any(methods[pid] not in ('UNRANKED_SCHOOL_PRIOR_2026','SITE_UNMODELED_PROVISIONAL_50000')
             or not 1<=ranks[pid]<=365 or
             changed[pid]!=int(round((5000+45000*((365-ranks[pid])/364)**1.35)/100)*100)
             for pid in changed) or
         any(pid not in common or older[pid]['value']!=source[pid] or
             rows[pid]['value']!=changed[pid] or rows[pid].get('preseason')!=changed[pid] or
             rows[pid].get('anchorType')!=(
                 'UNRANKED_HS_TEAM_SLIDING_2027' if methods[pid]=='UNRANKED_SCHOOL_PRIOR_2026'
                 else 'ROSTER_UNMODELED_TEAM_SLIDING_2027')
             for pid in changed) or
         (h.get('dates') or []) or (h.get('months') or []) or
         h.get('baselineAsOf')!=a.get('asOf') or
         int(f.get('latestSeason') or 0)>=2027):
      raise ValueError('Unverified 1835-player unranked opening rebase or artificial Stock Watch movement')
     ignored=set(moved) # Already individually validated opening REBASE, never daily movement.
     print('APPROVED 5K-50K OPENING PRIOR REBASE: 1835 exact IDs; 4222 prices protected')
    elif staff_review and pre_staff:
     # Third frozen checkpoint: 16 staff-reviewed ESPN IDs, no synthetic
     # 2026-27 game movement. A prior college redshirt is an explicit
     # staff-priced exception, not an overseas-pro classification.
     q,b,a,h=load(staff_review),load(pre_staff),load(anchor),load(history)
     updated=q.get('byESPNId') or {}
     source=q.get('sourceBaselineByESPNId') or {}
     previous=b.get('byESPNId') or {}
     now=a.get('byESPNId') or {}
     approved12=(load(approved).get('byESPNId') or {}) if approved else {}
     if (q.get('playerCount')!=16 or len(updated)!=16 or
         set(updated)!=set(source) or set(updated)&set(approved12) or
         len(previous)!=6057 or set(now)!=set(previous) or
         set(moved)!=set(updated) or
         any(previous.get(pid)!=price for pid,price in source.items()) or
         any(now.get(pid)!=(updated[pid] if pid in updated else price)
             for pid,price in previous.items()) or
         any(pid not in common or older[pid]['value']!=source[pid] or
             rows[pid]['value']!=updated[pid] or rows[pid].get('preseason')!=updated[pid] or
             rows[pid].get('anchorType')!=(
                 'INTERNATIONAL_PREVIOUS_COLLEGE_REDSHIRT_STAFF_REVIEWED'
                 if pid=='5312303' else 'INTERNATIONAL_STAFF_REVIEWED_PRESEASON')
             for pid in updated) or
         (h.get('dates') or []) or (h.get('months') or []) or
         h.get('baselineAsOf')!=a.get('asOf') or
         int(f.get('latestSeason') or 0)>=2027):
      raise ValueError('Staff 16 opening rebase changed unrelated prices or created false stock movement')
     print('APPROVED STAFF OPENING REBASE: 16 exact ESPN IDs; other 6041 unchanged; no Stock Watch movement')
    elif top100 and pre_top100:
     # Distinct second opening cohort after the original 12 staff-reviewed
     # prices. No player outside the 22 validated ESPN identities may move.
     v,b,a,h=load(top100),load(pre_top100),load(anchor),load(history)
     change=v.get('byESPNId') or {};previous=v.get('sourceBaselineByESPNId') or {}
     back=b.get('byESPNId') or {};now=a.get('byESPNId') or {}
     original=(load(pre_rebase).get('byESPNId') or {}) if pre_rebase else {}
     staff=(load(approved).get('byESPNId') or {}) if approved else {}
     if (len(change)!=22 or set(change)!=set(previous) or
         len(back)!=6057 or len(now)!=6057 or set(now)!=set(back) or
         set(moved)!=set(change) or set(change)&set(staff) or
         len(staff)!=12 or len(original)!=6057 or
         any(back.get(pid)!=price for pid,price in previous.items()) or
         any(now.get(pid)!=(change[pid] if pid in change else price) for pid,price in back.items()) or
         any(back.get(pid)!=price for pid,price in staff.items()) or
         any(older[pid]['value']!=previous[pid] or
             rows[pid]['value']!=change[pid] or rows[pid].get('preseason')!=change[pid] or
             rows[pid].get('anchorType')!='INTERNATIONAL_NONCOLLEGE_RESEARCH_PRIOR'
             for pid in change) or
         (h.get('dates') or []) or (h.get('months') or []) or
         h.get('baselineAsOf')!=a.get('asOf') or
         int(f.get('latestSeason') or 0)>=2027):
      raise ValueError('Unverified 22-ID noncollege opening rebase or unrelated price movement')
     print('VERIFIED RESEARCH OPENING PRIOR: 22 sourced ESPN IDs, staff 12 preserved, zero Stock Watch history')
    else:
     if not approved or not pre_rebase:
      raise ValueError('Preseason price moved without documented immutable opening correction')
     q,b,a,h=load(approved),load(pre_rebase),load(anchor),load(history)
     proposed=q.get('byESPNId') or {}
     original=q.get('sourceBaselineByESPNId') or {}
     preserved=b.get('byESPNId') or {}
     anchored=a.get('byESPNId') or {}
     if (len(proposed)!=12 or set(proposed)!=set(original) or set(moved)!=set(proposed) or
         b.get('playerCount')!=6057 or a.get('playerCount')!=6057 or
         set(preserved)!=set(anchored) or (h.get('dates') or []) or (h.get('months') or []) or
         h.get('baselineAsOf')!=a.get('asOf') or
         any(pid not in preserved or preserved[pid]!=original[pid] for pid in proposed) or
         any(anchored[pid]!=(proposed[pid] if pid in proposed else price) for pid,price in preserved.items()) or
         any(older[pid]['value']!=original[pid] or rows[pid]['value']!=proposed[pid] or
             rows[pid].get('preseason')!=proposed[pid] or
             rows[pid].get('anchorType')!='INTERNATIONAL_PRO_PRESEASON_REVIEWED'
             for pid in proposed)):
      raise ValueError('Unverified international preseason correction or non-reviewed player modified')
     print('APPROVED PRESEASON CORRECTION: 12 verified ESPN IDs; no Stock Watch dates')
 changes=[abs(math.log(rows[k]['value']/older[k]['value'])) for k in common-ignored]
 median=statistics.median(changes) if changes else 0.
 if median>=.12:raise ValueError('Suspicious day-to-day NIL price drift outside baseline migration')
 very_large=sum(x>math.log(4) for x in changes)
 if very_large>max(6,int(len(common)*.005)):
  raise ValueError('Too many fourfold day-to-day price changes')
 if len(rows)>20000:raise ValueError('Implausibly many players')
 print(json.dumps({'players':len(rows),'shared':len(common),'updated':current,
  'v4BaselineMigration':migration,'v4MigrationIDs':len(ignored),
  'dailyMedianLogShift':round(median,4),'dailyOver4x':very_large}))
 return True

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for arg in ('new','old','source'):p.add_argument('--'+arg,required=True)
 for arg in ('anchor','legacy','history','rookies','v4','others','approved','pre-rebase','top100','pre-top100','staff-review','pre-staff','unranked','pre-unranked'):p.add_argument('--'+arg)
 a=p.parse_args()
 check(a.new,a.old,a.source,a.anchor,a.legacy,a.history,a.rookies,a.v4,a.others,a.approved,a.pre_rebase,a.top100,a.pre_top100,a.staff_review,a.pre_staff,a.unranked,a.pre_unranked)
