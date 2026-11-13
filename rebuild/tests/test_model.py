import unittest
from blueprint.model import percentile,blend,distance,parse,fit_profiles,assess,evaluate,role_eligible,FEATURES
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
 def test_recent_comparisons_included_without_changing_benchmarks(self):
  def player(name,year):
   return {**{k:20 for k in FEATURES+['porpag']},'name':name,'id':name,
           'team':'Kansas','season':year,'height_inches':78,'games':30,
           'minutes_share':70,'three_a':50}
  old=[player('Benchmark A',2008),player('Benchmark B',2008)]
  original=fit_profiles({2008:old},before=2027)['organizer']
  expanded=fit_profiles({2008:old,2024:[player('Recent A',2024)],
                         2025:[player('Recent B',2025)],2026:[player('Recent C',2026)],
                         2027:[player('Future',2027)]},before=2027)['organizer']
  self.assertEqual(original['center'],expanded['center'])
  self.assertEqual(len(expanded['members']),2)
  self.assertEqual({p['season'] for p in expanded['comparison_members']},{2008,2024,2025,2026})
 def test_nearest_comparison_can_come_from_recent_season(self):
  def member(name,year,height=78,usage=20):
   return {'name':name,'season':year,'height_inches':height,'height':'6-6','usage':usage,'three_rate':30,'v':{k:.2 for k in FEATURES}}
  profile={'features':['ast'],'center':{'ast':.8},'members':[],
           'comparison_members':[member('Wrong size',2008,85),member('Wrong job',2008,78,35),member('Recent KU player',2026)]}
  candidate={'height_inches':78,'usage':20,'three_rate':30}
  scores,comps=assess({k:.2 for k in FEATURES},{'organizer':profile},candidate)
  self.assertAlmostEqual(scores['organizer'],40)
  self.assertEqual([c['name'] for c in comps['organizer']],['Recent KU player'])
  self.assertFalse(comps['organizer'][0]['benchmark'])
  self.assertEqual(assess({k:.2 for k in FEATURES},{'organizer':profile},candidate,confidence=10)[1]['organizer'],[])
 def test_role_bounds_include_edges_and_reject_missing_height(self):
  self.assertFalse(role_eligible({'height_inches':73},'connector'))
  self.assertFalse(role_eligible({'height_inches':76},'stretch'))
  self.assertTrue(role_eligible({'height_inches':77},'connector'))
  self.assertTrue(role_eligible({'height_inches':80},'stretch'))
  self.assertFalse(role_eligible({'height_inches':None},'organizer'))
 def test_evaluation_keeps_absolute_match_and_only_eligible_roles(self):
  def player(name,h,year,three=30):
   return {**{k:20 for k in FEATURES+['porpag']},'name':name,'id':name,
           'team':'Kansas','season':year,'height_inches':h,'height':'6-1',
           'games':30,'minutes_share':70,'three_a':50,'three_m':15,'two_a':100,'fta':50,
           'estimated_minutes':840,'usage':25,'ast':25,'three_rate':three,
           'conference':'B12','class':'Jr','position':'Stretch 4' if h and h>=80 else 'G'}
  history=[player(str(i),h,2008,t) for i,(h,t) in enumerate([(78,30)]*3+[(82,30)]*3+[(82,10)]*3)]
  guard=player('Guard',73,2027);guard['ast']=90
  big=player('Big',84,2027,10);big['ast']=5
  missing=player('Missing height',None,2027)
  absent=player('No appearances',78,2027);absent['games']=0
  outputs,_=evaluate({2008:history,2027:[guard,big,missing,absent]},2027)
  g,b,m,a=outputs
  self.assertIsNone(g['fit']['connector']);self.assertIsNone(g['fit']['stretch'])
  self.assertIn(g['best_role'],['organizer','scorer'])
  self.assertLess(g['fit']['organizer'],99)
  for p in outputs:
   for role,score in p['fit'].items():
    if score is not None:self.assertEqual(score,p['raw_similarity'][role])
  self.assertIn(b['best_role'],['anchor','stretch'])
  self.assertIsNone(m['best_role']);self.assertIsNone(a['best_role'])
if __name__=='__main__':unittest.main()
