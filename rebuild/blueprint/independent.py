"""CBBD-derived possession efficiency and learned transfer translation.

Torvik is not used by this predictor. On-court possessions are estimated from
team possessions × player minutes / team clock minutes, not substitution logs.
"""
import json,re,unicodedata
from pathlib import Path
from statistics import median,mean
from collections import Counter,defaultdict
from .model import number,percentile
ROOT=Path(__file__).resolve().parents[1]
RATE_FIELDS={'points100':'points','assists100':'assists','turnovers100':'turnovers','steals100':'steals','blocks100':'blocks'}
METRICS=list(RATE_FIELDS)+['rebounds100','orb100','ortg','usage','efg','ts','three_rate','ft_rate','porpag','minute_share']

def name_key(value):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().lower())

def per100(value,possessions):
    n=number(value)
    return 100*n/possessions if n is not None and possessions and possessions>0 else None

def metrics(p,team):
    clock=number(team.get('totalMinutes'));poss=number(team.get('teamStats',{}).get('possessions'))
    minutes=number(p.get('minutes'))
    exposure=poss*minutes/clock if clock and poss and minutes is not None else None
    # Reject incompatible clock-minute denominators rather than invent exposure.
    if clock is not None and (clock<0 or (minutes is not None and minutes>clock+1)):raise ValueError('Invalid player/team minutes')
    result={k:per100(p.get(field),exposure) for k,field in RATE_FIELDS.items()}
    result.update(rebounds100=per100(p.get('rebounds',{}).get('total'),exposure),orb100=per100(p.get('rebounds',{}).get('offensive'),exposure))
    fga=number(p.get('fieldGoals',{}).get('attempted'));fgm=number(p.get('fieldGoals',{}).get('made'))
    threes=number(p.get('threePointFieldGoals',{}).get('made'));three_a=number(p.get('threePointFieldGoals',{}).get('attempted'))
    fta=number(p.get('freeThrows',{}).get('attempted'));points=number(p.get('points'))
    result.update(ortg=number(p.get('offensiveRating')),usage=number(p.get('usage')),
                  efg=100*(fgm+.5*threes)/fga if fga and fgm is not None and threes is not None else None,
                  ts=100*points/(2*(fga+.44*fta)) if fga is not None and fta is not None and (fga+.44*fta)>0 and points is not None else None,
                  three_rate=100*three_a/fga if fga and three_a is not None else None,
                  ft_rate=100*fta/fga if fga and fta is not None else None,
                  porpag=number(p.get('PORPAG')),minute_share=100*minutes/clock if clock and minutes is not None else None)
    return result,exposure

def prepare(players,teams,ratings):
    teams={t['teamId']:t for t in teams};ratings={r['teamId']:r for r in ratings}
    conf=defaultdict(list)
    for r in ratings.values():conf[r['conference']].append(r['netRating'])
    conf={k:mean(v) for k,v in conf.items()}
    out=[];excluded=[]
    for p in players:
        if p['teamId'] not in ratings or p['teamId'] not in teams:continue
        invalid=any(not 0 <= (p.get(k,{}).get('made') or 0) <= (p.get(k,{}).get('attempted') or 0) for k in ['fieldGoals','twoPointFieldGoals','threePointFieldGoals','freeThrows'])
        if invalid:
            excluded.append({'id':p['athleteId'],'reason':'Invalid shooting counts'});continue
        try:values,poss=metrics(p,teams[p['teamId']])
        except ValueError:
            excluded.append({'id':p['athleteId'],'reason':'Invalid minutes'});continue
        out.append({**p,'m':values,'poss':poss,'league':ratings[p['teamId']]['conference']})
    reference={k:median([p['m'][k] for p in out if p['m'][k] is not None and (p['m']['minute_share'] or 0)>=20]) for k in METRICS}
    return {'players':out,'teams':teams,'ratings':ratings,'conferences':conf,'medians':reference,'excluded':excluded}

def load(year):
    folder=ROOT/'data/cbbd/national'/str(year)
    return prepare(*(json.loads((folder/(k+'.json')).read_text()) for k in ['players','teams','ratings']))

def unique_players(season):
    counts=Counter(p['athleteId'] for p in season['players'])
    return {p['athleteId']:p for p in season['players'] if counts[p['athleteId']]==1}

def inputs(p,prior,season,previous,destination_id):
    values={};weights=[]
    for k in METRICS:
        current=p['m'][k];r=(p['poss'] or 0)/((p['poss'] or 0)+500) if current is not None else 0
        old=prior['m'][k] if prior else None
        old_r=.65*(prior['poss'] or 0)/((prior['poss'] or 0)+500) if prior and old is not None else 0
        center=season['medians'][k]
        base=old_r*old+(1-old_r)*center if old is not None else center
        values[k]=r*(current if current is not None else center)+(1-r)*base
        weights.append(r+(1-r)*old_r)
    source=season['ratings'].get(p['teamId']);dest=season['ratings'].get(destination_id)
    if not source or not dest:return None,None
    source_strength=season['conferences'][source['conference']];destination_strength=season['conferences'][dest['conference']]
    gap=destination_strength-source_strength
    values['transfer']=float(p['teamId']!=destination_id)
    values['level:source']=source_strength;values['level:destination']=destination_strength
    values['level:gap']=gap;values['level:up']=max(0,gap)
    values['level:up_usage']=max(0,gap)*(values['usage']-20)/20
    values['level:up_efficiency']=max(0,gap)*(values['ortg']-100)/20
    return values,{'source_conference':source['conference'],'destination_conference':dest['conference'],
                   'source_strength':round(source_strength,2),'destination_strength':round(destination_strength,2),
                   'gap':round(gap,2),'evidence':round(mean(weights)*100)}

def predict(values,model):
    return model['intercept']+sum(values.get(k,0)*c for k,c in zip(model['features'],model['coefficients']))

def combined(production_score,fit,supported=True):
    if production_score is None or fit is None or not supported:return None
    # Explicit scouting preference, not a learned success probability.
    return round(.8*production_score+.2*fit,1)

def crosswalk(torvik,season):
    """Unique normalized name AND verified team mapping; no fuzzy player joins.

    Team aliases are inferred only from >=3 uniquely named shared players with
    >=90% agreement, and must be one-to-one. Ambiguity remains unmatched.
    """
    by_name=defaultdict(list)
    for p in season['players']:by_name[name_key(p['name'])].append(p)
    tc=Counter(name_key(p['name']) for p in torvik);votes=defaultdict(Counter)
    for p in torvik:
        key=name_key(p['name']);matches=by_name[key]
        if tc[key]==1 and len(matches)==1:votes[p['team']][matches[0]['teamId']]+=1
    mapping={}
    for team,v in votes.items():
        tid,count=v.most_common(1)[0]
        if count>=3 and count/sum(v.values())>=.9:mapping[team]=tid
    duplicate=Counter(mapping.values());mapping={k:v for k,v in mapping.items() if duplicate[v]==1}
    # Exact team names can also establish context without an inferred alias.
    exact=defaultdict(list)
    for tid,t in season['ratings'].items():exact[name_key(t['team'])].append(tid)
    for p in torvik:
        ids=exact[name_key(p['team'])]
        if len(ids)==1 and p['team'] not in mapping and ids[0] not in mapping.values():mapping[p['team']]=ids[0]
    matches={}
    for p in torvik:
        rows=[q for q in by_name[name_key(p['name'])] if q['teamId']==mapping.get(p['team'])]
        if len(rows)==1:matches[p['id']]=rows[0]
    counts=Counter(q['athleteId'] for q in matches.values())
    matches={k:q for k,q in matches.items() if counts[q['athleteId']]==1}
    return matches,mapping
