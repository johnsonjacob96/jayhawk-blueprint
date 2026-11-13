"""Transparent, descriptive KU role similarity. Scores are not outcome probabilities."""
from __future__ import annotations
from bisect import bisect_left, bisect_right
from collections import Counter
from math import sqrt, isfinite
from statistics import median
import re

VERSION = '0.1.0'
SUCCESS_SEASONS = [2008, 2012, 2018, 2020, 2022]
# 2018 is on-court performance, including subsequently vacated results.
COL = {'name':0,'team':1,'conference':2,'games':3,'minutes_share':4,'ortg':5,
       'usage':6,'ts':8,'orb':9,'drb':10,'ast':11,'tov':12,'ftm':13,'fta':14,
       'two_m':16,'two_a':17,'three_m':19,'three_a':20,'blk':22,'stl':23,
       'class':25,'height':26,'porpag':28,'season':31,'id':32,'position':64}
FEATURES = ['usage','ast','tov','three_rate','three_pct','ft_pct','two_pct','orb','drb','blk','stl']
LABELS = {'usage':'Usage','ast':'Assist rate','tov':'Turnover rate','three_rate':'3-point attempt share',
          'three_pct':'3-point accuracy','ft_pct':'Free-throw accuracy','two_pct':'2-point accuracy',
          'orb':'Offensive rebounding','drb':'Defensive rebounding','blk':'Block rate','stl':'Steal rate'}
ROLES = {
 'organizer': {'label':'Lead organizer','short':'Organizer','features':['usage','ast','tov','three_rate','three_pct','ft_pct','stl']},
 'scorer': {'label':'Scoring guard','short':'Scorer','features':['usage','ast','tov','three_rate','three_pct','two_pct','ft_pct']},
 'wing': {'label':'Shooting wing','short':'Wing','features':['three_rate','three_pct','ft_pct','two_pct','stl','drb']},
 'connector': {'label':'Connecting forward','short':'Connector','features':['ast','tov','usage','two_pct','drb','stl']},
 'stretch': {'label':'Spacing big','short':'Stretch big','features':['three_rate','three_pct','ft_pct','drb','orb','blk']},
 'anchor': {'label':'Interior anchor','short':'Anchor','features':['two_pct','three_rate','orb','drb','blk','tov']},
}

def number(v):
    if isinstance(v,bool): return None
    try:
        n=float(v)
        return n if isfinite(n) else None
    except (ValueError,TypeError): return None

def ratio(m,a):
    return 100*m/a if a and m is not None else None

def parse(rows, season):
    """Fail closed on mixed seasons, duplicate source IDs, invalid count/percentage units."""
    out=[]; seen=set()
    for row in rows:
        if not isinstance(row,list) or len(row)<65: raise ValueError('Unsupported Torvik schema')
        p={k:row[i] for k,i in COL.items()}
        if number(p['season'])!=season: raise ValueError('Source season mismatch')
        if p['id'] is None: raise ValueError('Missing player ID')
        p['id']=str(p['id'])
        if p['id'] in seen: raise ValueError('Duplicate player ID: '+p['id'])
        seen.add(p['id'])
        for k in COL:
            if k not in {'name','team','conference','class','height','id','position'}: p[k]=number(p[k])
        for k in ['games','minutes_share','ftm','fta','two_m','two_a','three_m','three_a']:
            if p[k] is None or p[k]<0: raise ValueError('Invalid '+k)
        for m,a in [('ftm','fta'),('two_m','two_a'),('three_m','three_a')]:
            if p[m]>p[a]: raise ValueError('Makes exceed attempts')
        if p['minutes_share']>100: raise ValueError('Unexpected minute-share units')
        h=re.match(r"(\d+)[-'’](\d+)",str(p['height']))
        p['height_inches']=12*int(h[1])+int(h[2]) if h else None
        p['three_pct']=ratio(p['three_m'],p['three_a'])
        p['ft_pct']=ratio(p['ftm'],p['fta'])
        p['two_pct']=ratio(p['two_m'],p['two_a'])
        p['three_rate']=ratio(p['three_a'],p['two_a']+p['three_a'])
        # Exposure approximation only: misses team games not played and overtime.
        p['estimated_minutes']=p['games']*40*p['minutes_share']/100
        out.append(p)
    return out

def distribution(players):
    return {k:sorted(p[k] for p in players if p.get(k) is not None and p['minutes_share']>=20 and p['games']>0)
            for k in FEATURES+['porpag']}

def percentile(value, values):
    if value is None or not values: return None
    return (bisect_left(values,value)+bisect_right(values,value))/(2*len(values))

def vector(p, dist):
    return {k:percentile(p.get(k),dist[k]) for k in FEATURES+['porpag']}

def exposure(p,k):
    n=p.get({'three_pct':'three_a','ft_pct':'fta','two_pct':'two_a'}.get(k,'estimated_minutes')) or 0
    prior={'three_pct':75,'ft_pct':50,'two_pct':100}.get(k,300)
    return n/(n+prior)

def blend(p, previous, dist, previous_dist):
    """Same-provider ID AND exact name required; unmatched players use population median."""
    now=vector(p,dist)
    old=vector(previous,previous_dist) if previous else {}
    values={}; confidences=[]
    for k in FEATURES+['porpag']:
        r=exposure(p,k) if now[k] is not None else 0
        old_r=exposure(previous,k)*0.65 if previous and old.get(k) is not None else 0
        prior=old_r*old.get(k,0.5)+(1-old_r)*0.5 if old.get(k) is not None else 0.5
        values[k]=r*(now[k] if now[k] is not None else 0.5)+(1-r)*prior
        confidences.append(r+(1-r)*old_r)
    return values,round(100*sum(confidences)/len(confidences))

def qualifies(p,role):
    h=p['height_inches']; a=p.get('ast'); u=p.get('usage'); t=p.get('three_rate')
    if h is None: return False
    if role=='organizer': return h<=79 and a is not None and a>=20
    if role=='scorer': return h<=80 and u is not None and u>=22
    if role=='wing': return 76<=h<=82 and t is not None and t>=25
    if role=='connector': return 77<=h<=82 and a is not None and a>=12
    if role=='stretch': return h>=80 and t is not None and t>=15 and p['three_a']>=30
    if role=='anchor': return h>=80 and t is not None and t<15
    return False

def fit_profiles(seasons, before=None):
    """Profiles use only historical cohorts; no target or future-season data."""
    years=[y for y in SUCCESS_SEASONS if y in seasons and (before is None or y<before)]
    profiles={}
    for role,settings in ROLES.items():
        members=[]
        for y in years:
            dist=distribution(seasons[y])
            for p in seasons[y]:
                if p['team']=='Kansas' and p['games']>=15 and p['minutes_share']>=20 and qualifies(p,role):
                    members.append({**p,'v':vector(p,dist)})
        if len(members)<2: continue
        keys=settings['features']
        center={k:median(m['v'][k] for m in members if m['v'][k] is not None) for k in keys}
        profiles[role]={'label':settings['label'],'features':keys,'center':center,'members':members,
                        'raw_medians':{k:median(m[k] for m in members if m[k] is not None) for k in keys}}
    return profiles

def distance(v, target, keys):
    available=[k for k in keys if v.get(k) is not None and target.get(k) is not None]
    if not available: return 1.0
    return sqrt(sum((v[k]-target[k])**2 for k in available)/len(available))

def assess(v,profiles):
    scores={}; comps={}
    for role,profile in profiles.items():
        scores[role]=max(0,100*(1-distance(v,profile['center'],profile['features'])))
        nearest=sorted(profile['members'],key=lambda m:distance(v,m['v'],profile['features']))[:3]
        comps[role]=[{'name':m['name'],'season':int(m['season']),'similarity':round(100*(1-distance(v,m['v'],profile['features'])),1)} for m in nearest]
    return scores,comps

def evaluate(seasons,target):
    profiles=fit_profiles(seasons,before=target)
    if len(profiles)!=len(ROLES): raise ValueError('Insufficient historical profile coverage')
    current=seasons[target]; dist=distribution(current)
    prev={p['id']:p for p in seasons.get(target-1,[])}
    pdist=distribution(seasons.get(target-1,[]))
    outputs=[]
    for p in current:
        old=prev.get(p['id'])
        if old and old['name']!=p['name']: old=None
        v,confidence=blend(p,old,dist,pdist)
        raw,comps=assess(v,profiles)
        outputs.append({'id':p['id'],'name':p['name'],'team':p['team'],'conference':p['conference'],
                        'class':p['class'],'height':p['height'],'position':p['position'],
                        'games':int(p['games']),'confidence':confidence,'quality':round(v['porpag']*100),
                        'prior_team':old['team'] if old else None,'prior_season':target-1 if old else None,
                        'raw_similarity':raw,'comparisons':comps,'features':{k:round(v[k]*100,1) for k in FEATURES},
                        'stats':{k:p[k] for k in FEATURES+['minutes_share','porpag','three_a','three_m']},
                        'portal_status':'Not assessed','eligibility':'Unverified','fit':{}})
    # Percentile is descriptive rank among the source's active players, not probability.
    for role in profiles:
        bounds={'organizer':(0,79),'scorer':(0,80),'wing':(76,82),'connector':(77,82),'stretch':(80,100),'anchor':(80,100)}
        lo,hi=bounds[role]
        eligible={p['id'] for p in current if p['height_inches'] is not None and lo<=p['height_inches']<=hi and p['minutes_share']>=20}
        ranks=sorted(p['raw_similarity'][role] for p in outputs if p['games']>0 and p['id'] in eligible)
        for p in outputs:
            p['fit'][role]=round(100*percentile(p['raw_similarity'][role],ranks),1) if p['games']>0 else None
            p['raw_similarity'][role]=round(p['raw_similarity'][role],1)
    for p in outputs:
        p['best_role']=max(p['fit'],key=lambda r:p['fit'][r] if p['fit'][r] is not None else -1)
    summary={r:{'label':p['label'],'count':len(p['members']),'seasons':sorted(set(int(m['season']) for m in p['members'])),
                'center':{k:round(v*100,1) for k,v in p['center'].items()},
                'raw_medians':{k:round(v,1) for k,v in p['raw_medians'].items()},
                'members':[{'name':m['name'],'season':int(m['season'])} for m in p['members']]} for r,p in profiles.items()}
    return outputs,summary
