#!/usr/bin/env python3
"""Offline policy/identity QA; does not invoke the private NIL model."""
import ast
import json
import math
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ANCHOR=ROOT/'public/stock_watch/preseason_2027.json'
STAGED=ROOT/'public/stock_watch/v4_preseason_2027_candidate.json'
ARCHIVE=ROOT/'public/stock_watch/preseason_2027_legacy_2026_10_24.json'
ENGINE=ROOT/'scripts/nil_model/nil_season_engine.py'
COMPOSE=ROOT/'scripts/nil_model/compose_v4_2027_candidate.py'
FALLBACKS=("4848644","4895795","5081348","5101798","5164560","5174319",
"5175797","5175921","5176224","5183293","5193438","5221332","5238203",
"5240527","5241773","5243336","5243379","5252606","5311610","5311767",
"5311888","5311913","5311932","5312047","5312051","5312312","5312320",
"5312654","5312920","5312922","5313054","5313072","5313078","5313127",
"5313383","5313575","5313660","5313700","5313756","5313860","5314359",
"5314478","5314625","5314648","5314703","5314757","5314796","5314857",
"5315593","5315594","5317337","5325995")

def isolated_function(path,name,context):
    module=ast.parse(path.read_text())
    candidate=[x for x in module.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name]
    if len(candidate)!=1:raise ValueError("Function missing or duplicated: "+name)
    exec(compile(ast.Module(body=candidate,type_ignores=[]),str(path),"exec"),context)
    return context[name]

class PreseasonIntegrationQA(unittest.TestCase):
    def test_source_is_valid_python(self):
        for source in (ENGINE,COMPOSE):
            ast.parse(source.read_text())
    def test_full_ESPN_id_set_preserved(self):
        previous=json.loads(ANCHOR.read_text())
        backup=json.loads(ARCHIVE.read_text())
        staged=json.loads(STAGED.read_text())
        self.assertEqual(previous,backup,"Legacy rollback copy changed")
        self.assertEqual(len(staged['byESPNId']),3051)
        self.assertEqual(set(previous['byESPNId']),set(staged['byESPNId']))
        self.assertEqual(staged['baselineVersion'],'V4_VERIFIED_WITH_EXPLICIT_EXISTING_FALLBACKS_2026_10_27')
        self.assertEqual(sum(staged['byESPNId'][k]!=v for k,v in previous['byESPNId'].items()),2999)
        for pid in FALLBACKS:
            self.assertEqual(staged['byESPNId'][pid],previous['byESPNId'][pid],pid)
        self.assertEqual(staged['byESPNId']['5176309'],2381092)
        self.assertEqual(staged['byESPNId']['5241334'],296117)
        self.assertEqual(staged['byESPNId']['5240585'],87689)
        self.assertEqual(staged['byESPNId']['5176308'],75829)
        self.assertEqual(staged['byESPNId']['5243370'],20000)
        self.assertEqual(staged['byESPNId']['5313432'],20000)
    def test_no_absolute_repricing_through_auxiliary_model(self):
        c={'math':math,'FLOOR':20000,'num':lambda x:float(x),'clamp':lambda x,a,b:max(a,min(b,x))}
        f=isolated_function(ENGINE,'relative_v4_update',c)
        self.assertEqual(f(900000,600000,600000,.91),900000)
        self.assertEqual(f(900000,900000,600000,0.),900000)
        self.assertTrue(1200000<f(900000,900000,600000,.91)<1400000)
        with self.assertRaises(ValueError):
            f(900000,8000000,600000,.20)
    def test_preseason_reference_context_is_same_target_team(self):
        c={'num':lambda x:float(x or 0),
          'stabilized_virtual_season':lambda prior,second,year:({'teamId':'old','season':year},.2)}
        f=isolated_function(ENGINE,'comparable_virtual_reference',c)
        obj=f({'gp':30,'minutes':800},2027,'new-team')
        self.assertEqual(obj['teamId'],'new-team')
        self.assertEqual(obj['season'],2027)

if __name__=="__main__": unittest.main()
