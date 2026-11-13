#!/usr/bin/env python3
"""Refresh source snapshots and build the local static scouting board."""
import argparse, hashlib, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from blueprint.model import parse,evaluate,VERSION,SUCCESS_SEASONS,ROLES,LABELS,distribution,percentile
from blueprint import independent as I, external as E
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
    artifact_path=ROOT/'independent-model.json'
    artifact=json.loads(artifact_path.read_text())
    if artifact['trained_through']>=args.season:raise ValueError('Training includes input season')
    report=json.loads((ROOT/'independent-report.json').read_text())
    national=I.load(args.season);previous=I.load(args.season-1)
    matches,team_map=I.crosswalk(seasons[args.season],national)
    prior=I.unique_players(previous)
    ku=[r['teamId'] for r in national['ratings'].values() if r['team']=='Kansas']
    if len(ku)!=1:raise ValueError('Ambiguous Kansas destination')
    external_current=E.load(args.season);external_prior=E.load(args.season-1)
    for output in players:
        output.update(projection=None,impact=None,efficiency=None,external_impact=None,source_match=False)
        p=matches.get(output['id'])
        if p:
            output['source_match']=True
            output['external_impact']=E.evidence(p,args.season,external_current,external_prior)
            output['efficiency']={k:round(v,2) if v is not None else None for k,v in p['m'].items()}
            output['efficiency']['estimated_possessions']=round(p['poss'],1) if p['poss'] else None
            old=prior.get(p['athleteId'])
            if old and I.name_key(old['name'])!=I.name_key(p['name']):old=None
            values,context=I.inputs(p,old,national,previous,ku[0])
            if values and (p['m']['minute_share'] or 0)>=20 and p['games']>0:
                value=I.predict(values,artifact)
                output['impact']=round(100*percentile(value,artifact['outcome_reference']),1)
                contributions=[{'feature':k,'contribution':round((values[k]-artifact['means'][i])*c,3)} for i,(k,c) in enumerate(zip(artifact['features'],artifact['coefficients']))]
                output['projection']={'porpag':round(value,3),'provider':'CBBD','context':context,
                                      'drivers':sorted(contributions,key=lambda d:abs(d['contribution']),reverse=True)[:4],
                                      'status':'Experimental: November inputs have not been validated'}
        output['grade']={r:I.combined(output['impact'],output['fit'][r],profiles[r]['supported']) for r in ROLES}
    outcome_summary={'version':artifact['version'],'trained_through':artifact['trained_through'],
                     'model_sha256':hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                     'training_rows':artifact['training_rows'],'variant':report['selected']['variant'],
                     'test_years':report['check_years'],'test':report['selected']['metrics'],
                     'baseline':report['baseline']['metrics'],'ku_transfers':report['ku_transfers'],
                     'early_season_validated':False,'target':artifact['target'],
                     'reference_count':len(artifact['outcome_reference']),
                     'status':report['status'],'kansas_adjustment':False}
    source_audit={'matched':len(matches),'unmatched':len(players)-len(matches),'team_mappings':len(team_map),
                  'external_matches':sum(p['external_impact'] is not None for p in players),
                  'rapm_seasons':sorted({p['external_impact']['season'] for p in players if p['external_impact']}),
                  'national':{k:json.loads((ROOT/f'data/cbbd/national/{args.season}/{k}.meta.json').read_text()) for k in ['players','teams','ratings']},
                  'rapm_availability':json.loads((E.ROOT/'availability.json').read_text()) if (E.ROOT/'availability.json').exists() else None}
    source_audit['external_files']={p.name:json.loads(p.read_text()) for p in E.ROOT.glob('*.meta.json')}
    manifest={str(p.relative_to(ROOT/'data')):json.loads(p.read_text())['sha256'] for p in (ROOT/'data').glob('raw/*.meta.json')}
    for y in [args.season-1,args.season]:
        manifest.update({str(p.relative_to(ROOT/'data')):json.loads(p.read_text())['sha256'] for p in (ROOT/f'data/cbbd/national/{y}').glob('*.meta.json')})
    manifest.update({str(p.relative_to(ROOT/'data')):json.loads(p.read_text())['sha256'] for p in E.ROOT.glob('*.meta.json')})
    source_audit['input_manifest']=manifest
    source_fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    source_audit['input_sha256']=source_fingerprint
    result={'version':VERSION,'as_of':args.as_of,'season':args.season,'target_season':args.season+1,
            'outcomes':outcome_summary,'source_audit':source_audit,
            'history_seasons':[y for y in years if y<args.season],
            'source':meta,'players':players,'profiles':profiles,'roles':ROLES,'labels':LABELS,
            'teams':len(set(p['team'] for p in players)),
            'limits':['Model selected with chronological full-season checks; not an independent test. November forecasts remain experimental.',
                      'KU grade = 80% projected production percentile + 20% role resemblance; a preference index, not a success probability.',
                      'Current roster is empty by design; eligibility and portal status are unverified.',
                      'Box-score defensive proxies do not measure scheme execution or film traits.']}
    out=ROOT/'web';out.mkdir(exist_ok=True)
    payload=json.dumps(result,separators=(',',':'),allow_nan=False).replace('</','<\\/')
    (out/'data.js').write_text('window.BLUEPRINT='+payload+';\n')
    history=ROOT/'data/grades';history.mkdir(exist_ok=True)
    compact={'as_of':args.as_of,'version':VERSION,'source_hash':source_fingerprint,'input_manifest':manifest,
             'outcome_model_hash':outcome_summary['model_sha256'],
             'players':[{k:p[k] for k in ['id','name','team','fit','grade','quality','confidence','impact','projection','external_impact']} for p in players]}
    (history/f'{args.as_of}-{source_fingerprint[:10]}-v{VERSION}-{outcome_summary["model_sha256"][:8]}.json').write_text(json.dumps(compact))
    print(json.dumps({'players':len(players),'teams':result['teams'],'profiles':{k:p['count'] for k,p in profiles.items()},'output':str(out/'index.html')},indent=2))
if __name__=='__main__':main()
