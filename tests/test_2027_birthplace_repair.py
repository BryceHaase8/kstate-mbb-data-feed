#!/usr/bin/env python3
"""Offline fail-closed guards: roster birthplace-only repair."""
import copy, importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("birthfix", Path(__file__).resolve().parents[1]/"scripts/repair_roster_birthplaces_2027.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class BirthplaceTest(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(mod.get_city("Marseille NA"),"Marseille")
        self.assertEqual(mod.get_city("Chicago IL"),"")
        self.assertEqual(mod.clean("NA"),"")

    def test_country_is_verified_by_espn_id(self):
        def fake_open(req,timeout=18):
            from io import BytesIO
            class R:
                def __enter__(self):
                    return BytesIO(json.dumps({"id":"5311523","birthPlace":{"city":"Marseille","country":"France"}}).encode())
                def __exit__(self,*args): pass
            return R()
        with patch.object(mod.urllib.request,"urlopen",side_effect=fake_open):
            pid,value,error=mod.resolve("5311523","Marseille")
        self.assertEqual((pid,value["display"],error),("5311523","Marseille, France",None))

    def test_wrong_id_is_rejected(self):
        def fake_open(req,timeout=18):
            from io import BytesIO
            class R:
                def __enter__(self):
                    return BytesIO(b'{"id":"999","birthPlace":{"city":"Marseille","country":"France"}}')
                def __exit__(self,*args): pass
            return R()
        with patch.object(mod.urllib.request,"urlopen",side_effect=fake_open):
            _,value,error=mod.resolve("5311523","Marseille")
        self.assertIsNone(value)
        self.assertEqual(error,"ESPN_ID_MISMATCH")

    def test_patch_changes_birthplace_only_and_repeats_safely(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); qa=root/"qa.json"
            payload={"schemaVersion":3,"rosterSeason":2027,"players":[
                ["5311523","Ilias Kamardine","145","G","6-5","195 lbs",1,"Marseille NA",0],
                ["111","US Player","145","G","6-4","170",2,"Chicago IL",0]]}
            file=root/"roster_2027_fast_ready.json"
            file.write_text(json.dumps(payload))
            register=root/"register.json"
            register.write_text(json.dumps({"schemaVersion":1,"season":2027,"byESPNId":{
                "5311523":{"city":"Marseille","country":"France","state":"",
                    "display":"Marseille, France","source":"ESPN_CORE_V2_ATHLETE_ID"}
            }}))
            before=copy.deepcopy(payload)
            with patch.object(mod,"ROOT",root),patch.object(mod,"PRIMARY",file),patch.object(mod,"REGISTRY",register),patch.object(mod,"QA",qa):
                report=mod.patch()
                self.assertEqual(report["correctedPlayers"],1)
                updated=json.loads(file.read_text())
                self.assertEqual(updated["players"][0][7],"Marseille, France")
                self.assertEqual(updated["players"][1],before["players"][1])
                report2=mod.patch()
                self.assertEqual(report2["correctedPlayers"],0)
                self.assertEqual(json.loads(file.read_text()),updated)
if __name__=="__main__":unittest.main()
