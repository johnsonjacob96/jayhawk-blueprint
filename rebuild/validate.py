"""Rolling-origin diagnostic. Never trains on the evaluated destination season.
This is an association check, not a calibrated transfer projection or causal test.
"""
import json,math
from pathlib import Path
from statistics import mean
from blueprint.model import parse,distribution,vector,fit_profiles,assess,percentile
ROOT=Path(__file__).resolve().parent

def spearman(rows,x,y):
 if len(rows)<3:return None
 xs=sorted(r[x] for r in rows);ys=sorted(r[y] for r in rows)
 a=[percentile(r[x],xs) for r in rows];b=[percentile(r[y],ys) for r in rows]
 am=mean(a);bm=mean(b);den=math.sqrt(sum((v-am)**2 for v in a)*sum((v-bm)**2 for v in b))
 return round(sum((u-am)*(v-bm) for u,v in zip(a,b))/den,3) if den else None

def main():
 seasons={int(p.stem):parse(json.loads(p.read_text()),int(p.stem)) for p in (ROOT/'data/raw').glob('*.json') if p.stem.isdigit() and int(p.stem)<=2026}
 outcomes=[];national=[]
 for year in sorted(seasons):
  if year-1 not in seasons:continue
  profiles=fit_profiles(seasons,before=year-1)
  if len(profiles)<4:continue
  prev={p['id']:p for p in seasons[year-1]};dist=distribution(seasons[year-1])
  for p in seasons[year]:
   old=prev.get(p['id'])
   if not old or p['name']!=old['name'] or p['team']==old['team'] or old['minutes_share']<20:continue
   v=vector(old,dist);scores,_=assess(v,profiles)
   r={'name':p['name'],'destination_season':year,'origin':old['team'],'destination':p['team'],
      'available_profiles':len(profiles),'fit':round(max(scores.values()),2),
      'prior_quality':old['porpag'],'outcome_quality':p['porpag'],'outcome_minutes':p['minutes_share']}
   national.append(r)
   if p['team']=='Kansas':outcomes.append(r)
 report={'method':'Rolling-origin end-of-season profile diagnostic (not an early-season backtest). KU reference seasons strictly precede the origin season. No destination-minute filter.',
         'limitations':['Matches only players appearing in both source seasons; missing destinations and players without records are not observed failures.',
                        'Observed school changes are not an exhaustive official transfer registry.',
                        'Quality uses prior raw PORPAG; fit uses unshrunk full-season features. This does not validate the live early-season shrinkage.',
                        'Role coverage varies by historical fold. Small KU sample; correlations are descriptive only.'],
         'kansas':{'n':len(outcomes),'fit_vs_outcome':spearman(outcomes,'fit','outcome_quality'),
                   'prior_quality_vs_outcome':spearman(outcomes,'prior_quality','outcome_quality'),'records':outcomes},
         'national':{'n':len(national),'fit_vs_outcome':spearman(national,'fit','outcome_quality'),
                     'prior_quality_vs_outcome':spearman(national,'prior_quality','outcome_quality')},
         'verdict':'Keep descriptive fit separate from quality. Do not ship fit as a validated forecast.'}
 (ROOT/'validation-report.json').write_text(json.dumps(report,indent=2,allow_nan=False));print(json.dumps({k:v for k,v in report.items() if k in ['national','verdict']}));print('Kansas',len(outcomes),report['kansas']['fit_vs_outcome'],report['kansas']['prior_quality_vs_outcome'])
if __name__=='__main__':main()
