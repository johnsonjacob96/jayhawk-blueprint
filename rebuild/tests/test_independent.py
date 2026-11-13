import csv,gzip,json,tempfile,unittest
from pathlib import Path
from blueprint.independent import per100,metrics,combined,crosswalk,inputs
from blueprint.external import load,evidence
class IndependentTests(unittest.TestCase):
 def test_clock_minutes_possession_denominator(self):
  p={'minutes':20,'points':10,'assists':0,'fieldGoals':{'made':4,'attempted':8},'threePointFieldGoals':{'made':2,'attempted':4},'freeThrows':{'attempted':0}}
  m,poss=metrics(p,{'totalMinutes':40,'teamStats':{'possessions':70}})
  self.assertEqual(poss,35);self.assertAlmostEqual(m['points100'],1000/35)
  self.assertEqual(m['assists100'],0);self.assertIsNone(m['blocks100']);self.assertEqual(m['efg'],62.5)
  with self.assertRaises(ValueError):metrics({'minutes':45},{'totalMinutes':40,'teamStats':{'possessions':70}})
 def test_missing_exposure_and_value_are_not_zero(self):
  self.assertIsNone(per100(10,0));self.assertIsNone(per100(None,100));self.assertEqual(per100(0,100),0)
 def test_grade_rewards_production_and_requires_both(self):
  self.assertGreater(combined(90,75),combined(50,95));self.assertIsNone(combined(None,90));self.assertIsNone(combined(90,90,False))
 def test_crosswalk_never_joins_name_alone(self):
  torvik=[{'id':'1','name':'John Smith','team':'Kansas'}]
  season={'players':[{'athleteId':1,'name':'John Smith','teamId':2}],'ratings':{1:{'team':'Kansas'},2:{'team':'Duke'}}}
  self.assertEqual(crosswalk(torvik,season)[0],{})
 def test_external_season_identity_and_ambiguity(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);fields=['source','athlete_id_source','valid_from','valid_to','match_confidence','source_player_id','athlete_id']
   aliases=[dict(zip(fields,['ncaa','espn','2026','2026','1','11','101'])),dict(zip(fields,['ncaa','espn','2025','2025','1','11','999']))]
   with (root/'mbb_player_aliases.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(aliases)
   row={'season':2026,'player_id':'11','player':'One','team':'Kansas','orapm':2,'drapm':3,'rapm_net':5,'off_poss':900,'def_poss':900,'estimand':'league'}
   with gzip.open(root/'ncaa_mbb_rapm_2026.csv.gz','wt') as f:
    w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
   data=load(2026,root);self.assertEqual(set(data),{'101'});self.assertEqual(data['101']['net'],5)
   self.assertEqual(load(2027,root),{})
   self.assertEqual(evidence({'athleteSourceId':'101'},2027,{},data)['season'],2026)
   aliases.append({**aliases[0],'athlete_id':'102'})
   with (root/'mbb_player_aliases.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(aliases)
   self.assertEqual(load(2026,root),{})
if __name__=='__main__':unittest.main()
