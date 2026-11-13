#!/usr/bin/env python3
"""Refresh source snapshots and build the local static scouting board."""
import argparse, hashlib, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from blueprint.model import parse,evaluate,VERSION,SUCCESS_SEASONS,ROLES,LABELS
ROOT=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--season',type=int,default=2027,help='Season ending year')
    ap.add_argument('--as-of',required=True,help='User-facing snapshot date, YYYY-MM-DD')
    ap.add_argument('--refresh',action='store_true',help='Fetch current season, retaining previous snapshots')
    args=ap.parse_args()
    datetime.strptime(args.as_of,'%Y-%m-%d')
    rawdir=ROOT/'data/raw'; rawdir.mkdir(parents=True,exist_ok=True)
    years=sorted(set(SUCCESS_SEASONS+[args.season-1,args.season]))
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
    result={'version':VERSION,'as_of':args.as_of,'season':args.season,'target_season':args.season+1,
            'source':meta,'players':players,'profiles':profiles,'roles':ROLES,'labels':LABELS,
            'teams':len(set(p['team'] for p in players)),
            'limits':['Descriptive prototype; transfer outcomes not yet validated.',
                      'Fit is resemblance, not predicted performance or recruiting availability.',
                      'Current roster is empty by design; eligibility and portal status are unverified.',
                      'Box-score defensive proxies do not measure scheme execution or film traits.']}
    out=ROOT/'web';out.mkdir(exist_ok=True)
    payload=json.dumps(result,separators=(',',':'),allow_nan=False).replace('</','<\\/')
    (out/'data.js').write_text('window.BLUEPRINT='+payload+';\n')
    history=ROOT/'data/grades';history.mkdir(exist_ok=True)
    compact={'as_of':args.as_of,'version':VERSION,'source_hash':meta['sha256'],
             'players':[{k:p[k] for k in ['id','name','team','fit','quality','confidence']} for p in players]}
    (history/f'{args.as_of}-{meta["sha256"][:10]}.json').write_text(json.dumps(compact))
    print(json.dumps({'players':len(players),'teams':result['teams'],'profiles':{k:p['count'] for k,p in profiles.items()},'output':str(out/'index.html')},indent=2))
if __name__=='__main__':main()
