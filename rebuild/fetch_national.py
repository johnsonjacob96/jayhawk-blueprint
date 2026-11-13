#!/usr/bin/env python3
"""Cache CBBD national inputs privately; three bulk requests per season."""
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from fetch_cbbd import api_key
ROOT=Path(__file__).resolve().parent
ENDPOINTS={'players':'stats/player/season','teams':'stats/team/season','ratings':'ratings/adjusted'}

def validate(rows,year,kind):
    if not isinstance(rows,list) or not rows: raise ValueError('Empty national '+kind)
    keys=set()
    for r in rows:
        if r.get('season')!=year: raise ValueError('National season mismatch')
        key=(r.get('athleteId'),r.get('teamId')) if kind=='players' else r.get('teamId')
        if key in keys: raise ValueError('Duplicate national identity')
        keys.add(key)
    if len(rows)<(3000 if kind=='players' else 300):raise ValueError('Incomplete national '+kind)
    return rows

def fetch(year,refresh=False):
    folder=ROOT/'data/cbbd/national'/str(year);folder.mkdir(parents=True,exist_ok=True)
    key=None
    for kind,endpoint in ENDPOINTS.items():
        path=folder/(kind+'.json');meta=folder/(kind+'.meta.json')
        if path.exists() and meta.exists() and not refresh:continue
        key=key or api_key();url=f'https://api.collegebasketballdata.com/{endpoint}?season={year}'
        with urlopen(Request(url,headers={'Authorization':'Bearer '+key}),timeout=90) as response:raw=response.read()
        rows=validate(json.loads(raw),year,kind)
        now=datetime.now(timezone.utc);stamp=now.strftime('%Y%m%dT%H%M%S%fZ')
        metadata={'provider':'CollegeBasketballData','season':year,'kind':kind,'url':url,
                  'fetched_at':now.isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(rows)}
        archive=folder/'snapshots';archive.mkdir(exist_ok=True)
        (archive/f'{stamp}-{kind}.json').write_bytes(raw)
        (archive/f'{stamp}-{kind}.meta.json').write_text(json.dumps(metadata))
        path.write_bytes(raw);meta.write_text(json.dumps(metadata))
        print(f'CBBD {year} {kind}: {len(rows)} records',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--season',type=int);ap.add_argument('--history',action='store_true');ap.add_argument('--refresh',action='store_true');a=ap.parse_args()
    for y in range(2014,2027) if a.history else [a.season or 2027]:fetch(y,a.refresh)
