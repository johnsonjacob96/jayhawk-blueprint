#!/usr/bin/env python3
"""Refresh source snapshots and build the local static scouting board."""
import argparse, hashlib, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from blueprint.model import parse,evaluate,VERSION,SUCCESS_SEASONS,ROLES,LABELS,distribution,percentile
from blueprint.outcomes import inputs,predict,explain
ROOT=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--season',type=int,default=2027,help='Season ending year')
    ap.add_argument('--as-of',required=True,help='User-facing snapshot date, YYYY-MM-DD')
    ap.add_argument('--refresh',action='store_true',help='Fetch current season, retaining previous snapshots')
    args=ap.parse_args()
    datetime.strptime(args.as_of,'%Y-%m-%d')
    rawdir=ROOT/'data/raw'; rawdir.mkdir(parents=True,exist_ok=True)
    # Comparisons cover every completed KU season, not only benchmark teams.
    years=list(range(min(SUCCESS_SEASONS),args.season+1))
    for y in years:
        path=rawdir/f'{y}.json'; meta=rawdir/f'{y}.meta.json'
        if not path.exists() or (args.refresh and y==args.season):
            url=f'https://barttorvik.com/getadvstats.php?year={y}'
            with urllib.request.urlopen(url,timeout=30) as response: raw=response.read()
            rows=json.loads(raw);parse(rows,y)
            if len(rows)<1000: raise ValueError('Incomplete national source')
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            archive=ROOT/'data/snapshots'/str(y);archive.mkdir(parents=True,exist_ok=True)
            (archive/f'{stamp}.json').write_bytes(raw)
            metadata={'season':y,'source':url,'as_of':args.as_of,'fetched_at':stamp,
                      'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(rows)}
            (archive/f'{stamp}.meta.json').write_text(json.dumps(metadata))
            path.write_bytes(raw);meta.write_text(json.dumps(metadata))
    seasons={y:parse(json.loads((rawdir/f'{y}.json').read_text()),y) for y in years}
    meta=json.loads((rawdir/f'{args.season}.meta.json').read_text())
    if meta['as_of']!=args.as_of: raise ValueError('Cached date differs; use --refresh (never relabel stale data)')
    players,profiles=evaluate(seasons,args.season)
    artifact_path=ROOT/'outcome-model.json'
    artifact=json.loads(artifact_path.read_text())
    if artifact['trained_through']>=args.season:
        raise ValueError('Outcome artifact includes target input season; retrain with an earlier cutoff')
    report=json.loads((ROOT/'outcome-report.json').read_text())
    current={p['id']:p for p in seasons[args.season]}
    previous={p['id']:p for p in seasons[args.season-1]}
    dist=distribution(list(current.values())); pdist=distribution(list(previous.values()))
    ku_conferences={p['conference'] for p in current.values() if p['team']=='Kansas'}
    if len(ku_conferences)!=1: raise ValueError('Kansas conference context missing or ambiguous')
    ku_conference=next(iter(ku_conferences))
    for output in players:
        p=current[output['id']]; prior=previous.get(p['id'])
        if prior and prior['name']!=p['name']: prior=None
        eligible=p['minutes_share']>=20 and p['games']>0 and 'source:'+p['conference'] in artifact['features']
        output['projection']=None;output['impact']=None
        if eligible:
            values=inputs(p,prior,dist,pdist,ku_conference)
            output['projection']={'porpag':round(predict(values,artifact),3),
                                  'drivers':explain(values,artifact),
                                  'status':'Experimental: early-season inputs not validated'}
    reference=sorted(p['projection']['porpag'] for p in players if p['projection'])
    for p in players:
        if p['projection']:p['impact']=round(100*percentile(p['projection']['porpag'],reference),1)
    selected=report['selected']['variant']
    outcome_summary={'version':artifact['version'],'trained_through':artifact['trained_through'],
                     'model_sha256':hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                     'training_rows':artifact['training_rows'],'variant':selected,
                     'test_years':report['test_years'],'test':report['test'][selected],
                     'baseline':report['test']['production'],'carry_forward':report['test']['carry_forward'],
                     'early_season_validated':False,'target':artifact['target'],
                     'reference_count':len(reference),'kansas_adjustment':selected=='kansas'}
    result={'version':VERSION,'as_of':args.as_of,'season':args.season,'target_season':args.season+1,
            'outcomes':outcome_summary,
            'history_seasons':[y for y in years if y<args.season],
            'source':meta,'players':players,'profiles':profiles,'roles':ROLES,'labels':LABELS,
            'teams':len(set(p['team'] for p in players)),
            'limits':['Outcome model tested on full-season historical inputs; early-season projections remain experimental.',
                      'Fit is resemblance, not predicted performance or recruiting availability.',
                      'Current roster is empty by design; eligibility and portal status are unverified.',
                      'Box-score defensive proxies do not measure scheme execution or film traits.']}
    out=ROOT/'web';out.mkdir(exist_ok=True)
    payload=json.dumps(result,separators=(',',':'),allow_nan=False).replace('</','<\\/')
    (out/'data.js').write_text('window.BLUEPRINT='+payload+';\n')
    history=ROOT/'data/grades';history.mkdir(exist_ok=True)
    compact={'as_of':args.as_of,'version':VERSION,'source_hash':meta['sha256'],
             'outcome_model_hash':outcome_summary['model_sha256'],
             'players':[{k:p[k] for k in ['id','name','team','fit','quality','confidence','impact','projection']} for p in players]}
    (history/f'{args.as_of}-{meta["sha256"][:10]}-v{VERSION}-{outcome_summary["model_sha256"][:8]}.json').write_text(json.dumps(compact))
    print(json.dumps({'players':len(players),'teams':result['teams'],'profiles':{k:p['count'] for k,p in profiles.items()},'output':str(out/'index.html')},indent=2))
if __name__=='__main__':main()
