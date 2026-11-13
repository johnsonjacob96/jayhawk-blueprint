#!/usr/bin/env python3
"""Learn production/competition translation from CBBD, independent of Torvik.
Chronological folds tune candidates; final fit uses every observed outcome.
"""
import json,hashlib
from pathlib import Path
import numpy as np
from blueprint import independent as I
from train_outcomes import metrics
ROOT=Path(__file__).resolve().parent

def dataset():
    seasons={y:I.load(y) for y in range(2014,2027)};rows=[];audit=[]
    for origin in range(2015,2026):
        s=seasons[origin];old=I.unique_players(seasons[origin-1]);future=I.unique_players(seasons[origin+1]);eligible=0;missing=0;context=0
        for p in I.unique_players(s).values():
            if (p['m']['minute_share'] or 0)<20 or not p['games'] or p['m']['porpag'] is None:continue
            eligible+=1;q=future.get(p['athleteId'])
            if not q or I.name_key(q['name'])!=I.name_key(p['name']) or q['m']['porpag'] is None or not q['games']:
                missing+=1;continue
            prior=old.get(p['athleteId'])
            if prior and I.name_key(prior['name'])!=I.name_key(p['name']):prior=None
            x,c=I.inputs(p,prior,s,seasons[origin-1],q['teamId'])
            if x is None:context+=1;continue
            rows.append({'id':p['athleteId'],'name':p['name'],'year':origin+1,'target':q['m']['porpag'],'carry':p['m']['porpag'],
                         'transfer':p['teamId']!=q['teamId'],'ku':q['team']=='Kansas','step_up':c['gap']>=5 and p['teamId']!=q['teamId'],
                         'source_team':p['team'],'destination_team':q['team'],'destination_minutes_share':q['m']['minute_share'],
                         'x':x,'context':c})
        audit.append({'origin_season':origin,'eligible':eligible,'unobserved_return':missing,'missing_destination_context':context})
    return rows,audit

def fit(rows,variant,penalty):
    keys=['porpag','minute_share','transfer'] if variant=='production' else sorted(k for k in rows[0]['x'] if variant=='translation' or not k.startswith('level:'))
    x=np.array([[r['x'][k] for k in keys] for r in rows]);y=np.array([r['target'] for r in rows])
    means=x.mean(axis=0);scales=x.std(axis=0);scales[scales<1e-8]=1
    z=(x-means)/scales;c=np.linalg.solve(z.T@z+penalty*np.eye(len(keys)),z.T@(y-y.mean()))/scales
    return {'variant':variant,'penalty':penalty,'features':keys,'means':means.tolist(),'coefficients':c.tolist(),
            'intercept':float(y.mean()-means@c),'training_rows':len(rows),'trained_through':max(r['year'] for r in rows)}

def groups(rows,preds):
    out={}
    for key,fn in [('all',lambda r:True),('transfers',lambda r:r['transfer']),('step_up',lambda r:r['step_up']),('kansas_transfers',lambda r:r['ku'] and r['transfer'])]:
        idx=[i for i,r in enumerate(rows) if fn(r)];out[key]=metrics([rows[i] for i in idx],[preds[i] for i in idx])
    return out

def main():
    rows,audit=dataset();candidates=[];predictions={}
    for variant in ['production','efficiency','translation']:
        for penalty in [10.,100.,1000.]:
            checked=[];preds=[]
            for year in range(2020,2027):
                train=[r for r in rows if r['year']<year];test=[r for r in rows if r['year']==year]
                model=fit(train,variant,penalty);checked.extend(test);preds.extend(I.predict(r['x'],model) for r in test)
            item={'variant':variant,'penalty':penalty,'metrics':groups(checked,preds)};candidates.append(item);predictions[(variant,penalty)]=preds
            print(json.dumps(item),flush=True)
    baseline=min([c for c in candidates if c['variant']=='production'],key=lambda c:c['metrics']['transfers']['mae'])
    available=[c for c in candidates if c['metrics']['transfers']['mae']<=baseline['metrics']['transfers']['mae'] and c['metrics']['step_up']['mae']<=baseline['metrics']['step_up']['mae']]
    winner=min(available,key=lambda c:c['metrics']['transfers']['mae'])
    model=fit(rows,winner['variant'],winner['penalty']);model.update(version='independent-1',provider='CollegeBasketballData',target='next-season CBBD PORPAG conditional on observed D-I return',early_season_validated=False,
        outcome_reference=sorted(r['target'] for r in rows))
    # Continuous individual KU outcomes remain visible. No blanket season label
    # or inherited Torvik-model offset is applied to a new metric/provider.
    ku=[r for r in rows if r['ku'] and r['transfer']]
    ku_audit=[{'name':r['name'],'season':r['year'],'source_team':r['source_team'],'actual':r['target'],
               'fitted':round(I.predict(r['x'],model),3),'minutes_share':r['destination_minutes_share']} for r in ku]
    report={'version':model['version'],'provider':model['provider'],'training_rows':len(rows),'trained_through':model['trained_through'],
            'check_years':list(range(2020,2027)),'selected':winner,'baseline':baseline,'candidates':candidates,'audit':audit,'ku_transfers':ku_audit,
            'source_sha256':{f'{y}/{k}':hashlib.sha256((ROOT/f'data/cbbd/national/{y}/{k}.json').read_bytes()).hexdigest() for y in range(2014,2027) for k in ['players','teams','ratings']},
            'status':'Chronological tuning, not an independent accuracy test; early-season inputs unvalidated',
            'limits':['All completed matched outcomes enter final fitting; no permanent holdout.',
                      'Only unique same-provider athlete ID and matching normalized name transitions; unobserved returns excluded, not failures.',
                      'Per-100 counts use estimated on-court possessions, not substitution tracking.',
                      'League strength uses origin-season mean adjusted net efficiency; no future destination ratings.',
                      'Step-up audit subgroup: transfer into a league at least 5 adjusted-net points/100 stronger. Model uses continuous gap.',
                      'Conference context is not an individual opponent-by-opponent schedule adjustment.',
                      'PORPAG is an offensive production proxy, not comprehensive defensive impact.',
                      'Combined recommendation is an explicit 80% projected production percentile / 20% KU resemblance preference, not a trained success probability.']}
    (ROOT/'independent-model.json').write_text(json.dumps(model,indent=2)+'\n');(ROOT/'independent-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('SELECTED',json.dumps(winner),flush=True)

if __name__=='__main__':main()
