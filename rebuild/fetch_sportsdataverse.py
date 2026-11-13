#!/usr/bin/env python3
"""Fetch published NCAA league-wide RAPM and official ID aliases; no credentials."""
import argparse,csv,gzip,hashlib,io,json,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'data/sportsdataverse'
BASE='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/'
def fetch(tag,name):
    ROOT.mkdir(parents=True,exist_ok=True)
    url=BASE+tag+'/'+name
    with urllib.request.urlopen(url,timeout=60) as response:raw=response.read()
    rows=list(csv.DictReader(io.StringIO((gzip.decompress(raw) if name.endswith('.gz') else raw).decode())))
    if not rows:raise ValueError('Empty source')
    if tag=='ncaa_mbb_rapm':
        year=int(name.split('_')[-1].split('.')[0])
        if any(int(r['season'])!=year or r['estimand']!='league' for r in rows):raise ValueError('Wrong season or estimand')
        if len({r['player_id'] for r in rows})!=len(rows):raise ValueError('Duplicate NCAA player IDs')
    metadata={'provider':'SportsDataverse / NCAA','url':url,'fetched_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(rows)}
    archive=ROOT/'snapshots'/metadata['sha256'];archive.mkdir(parents=True,exist_ok=True)
    if not (archive/name).exists():
        (archive/name).write_bytes(raw);(archive/(name+'.meta.json')).write_text(json.dumps(metadata,indent=2))
    (ROOT/name).write_bytes(raw);(ROOT/(name+'.meta.json')).write_text(json.dumps(metadata,indent=2))
    return metadata
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--season',type=int,default=2027);a=ap.parse_args()
    # Check the public release index; never substitute another season silently.
    req=urllib.request.Request('https://api.github.com/repos/sportsdataverse/sportsdataverse-data/releases/tags/ncaa_mbb_rapm',headers={'User-Agent':'Jayhawk-Blueprint'})
    with urllib.request.urlopen(req,timeout=30) as response:release=json.load(response)
    names={x['name'] for x in release['assets']};available=[]
    for y in [a.season-1,a.season]:
        name=f'ncaa_mbb_rapm_{y}.csv.gz'
        if name in names:print(json.dumps(fetch('ncaa_mbb_rapm',name)));available.append(y)
    print(json.dumps(fetch('mbb_groups','mbb_player_aliases.csv')))
    (ROOT/'availability.json').write_text(json.dumps({'requested_season':a.season,'available_seasons':available,'checked_at':datetime.now(timezone.utc).isoformat()}))
