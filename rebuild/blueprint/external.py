"""Strict, season-scoped NCAA → ESPN identity join for external impact evidence."""
import csv,gzip,json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'data/sportsdataverse'
def load(year,root=ROOT):
    path=root/f'ncaa_mbb_rapm_{year}.csv.gz'
    if not path.exists():return {}
    aliases=defaultdict(set)
    with (root/'mbb_player_aliases.csv').open() as f:
        for r in csv.DictReader(f):
            if r['source']=='ncaa' and r['athlete_id_source']=='espn' and int(r['valid_from'])<=year<=int(r['valid_to']) and float(r['match_confidence'])>=1:
                aliases[r['source_player_id']].add(r['athlete_id'])
    out=defaultdict(list)
    with gzip.open(path,'rt') as f:
        for r in csv.DictReader(f):
            if int(r['season'])!=year or r['estimand']!='league':raise ValueError('External season/estimand mismatch')
            ids=aliases[r['player_id']]
            if len(ids)!=1:continue
            out[next(iter(ids))].append({'season':year,'team':r['team'],'name':r['player'],'offensive':round(float(r['orapm']),2),'defensive':round(float(r['drapm']),2),'net':round(float(r['rapm_net']),2),'offensive_possessions':int(r['off_poss']),'defensive_possessions':int(r['def_poss']),'source':'SportsDataverse NCAA league RAPM','minimum_sample':min(int(r['off_poss']),int(r['def_poss']))>=800})
    return {k:v[0] for k,v in out.items() if len(v)==1}
def evidence(player,year,current,previous):
    # ESPN source identity comes from CBBD, never CBBD's internal athlete ID.
    key=str(player.get('athleteSourceId',''))
    result=current.get(key) or previous.get(key)
    if result and result['season'] not in [year,year-1]:raise ValueError('Unexpected external evidence year')
    return result
