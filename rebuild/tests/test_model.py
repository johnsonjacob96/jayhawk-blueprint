import unittest
from blueprint.model import percentile,blend,distance,parse,fit_profiles,FEATURES
class ModelTests(unittest.TestCase):
 def test_ties_and_true_zero(self):
  self.assertEqual(percentile(0,[0,0,1,2]),.25)
  self.assertIsNone(percentile(None,[0,1]))
 def test_small_sample_shrinks(self):
  p={k:100 for k in FEATURES+['porpag']};p.update(estimated_minutes=10,three_a=2,fta=2,two_a=2)
  dist={k:[0,25,50,75,100] for k in FEATURES+['porpag']}
  v,c=blend(p,None,dist,dist)
  self.assertLess(v['three_pct'],.52);self.assertLess(c,10)
  p.update(estimated_minutes=1000,three_a=200,fta=200,two_a=400)
  v2,c2=blend(p,None,dist,dist)
  self.assertGreater(v2['three_pct'],v['three_pct']);self.assertGreater(c2,c)
 def test_prior_evidence_discounted(self):
  p={k:0 for k in FEATURES+['porpag']};p.update(estimated_minutes=0,three_a=0,fta=0,two_a=0)
  old={**p,**{k:100 for k in FEATURES+['porpag']},'estimated_minutes':2000,'three_a':200,'fta':200,'two_a':400}
  dist={k:[0,25,50,75,100] for k in FEATURES+['porpag']}
  v,c=blend(p,old,dist,dist)
  self.assertGreater(v['ast'],.5);self.assertLess(c,65)
 def test_distance_identity(self):
  self.assertEqual(distance({'a':.8},{'a':.8},['a']),0)
 def test_wrong_season_rejected(self):
  row=[0]*78;row[31]=2026
  with self.assertRaisesRegex(ValueError,'season'):parse([row],2027)
 def test_future_profiles_excluded(self):
  self.assertEqual(fit_profiles({2022:[]},before=2022),{})
if __name__=='__main__':unittest.main()
