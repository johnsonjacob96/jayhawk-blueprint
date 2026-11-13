#!/usr/bin/env python3
"""Private, dated game-log corpus for future point-in-time model validation.

One request per team/season. Raw licensed responses stay under ignored data/.
This source does NOT yet enter public grades. No unofficial login scraping.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

def api_key():
    key = os.environ.get('CBD_API_KEY')
    if not key and Path('/usr/bin/security').exists():
        result = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s',
                                 'jayhawk-blueprint.cbbd', '-a', 'api', '-w'],
                                capture_output=True, text=True)
        if result.returncode == 0: key = result.stdout.strip()
    if not key: raise RuntimeError('CBD_API_KEY or the Jayhawk CBBD Keychain entry is required')
    return key

def validate(rows, season, team):
    if not isinstance(rows, list) or not rows: raise ValueError('Empty game-log response')
    seen = set()
    for game in rows:
        if game.get('season') != season or game.get('team') != team:
            raise ValueError('Game-log season/team mismatch')
        if game['gameId'] in seen: raise ValueError('Duplicate game ID')
        seen.add(game['gameId'])
        datetime.fromisoformat(game['startDate'].replace('Z', '+00:00'))
        ids = set()
        for p in game['players']:
            if p['athleteId'] in ids: raise ValueError('Duplicate athlete ID within game')
            ids.add(p['athleteId'])
            for field in ('fieldGoals', 'twoPointFieldGoals', 'threePointFieldGoals', 'freeThrows'):
                shot = p.get(field)
                if shot and shot.get('made') is not None and shot.get('attempted') is not None:
                    if not 0 <= shot['made'] <= shot['attempted']: raise ValueError('Invalid shooting counts')
    return rows

def as_of(rows, cutoff):
    """Use games strictly before a timezone-aware cutoff; no future game leakage.

    A retrospective source can include later corrections. This is event-time
    slicing, not proof of what the vendor had published on that historical day.
    """
    if cutoff.tzinfo is None: raise ValueError('Timezone-aware cutoff required')
    return [g for g in rows if datetime.fromisoformat(g['startDate'].replace('Z', '+00:00')) < cutoff]

def observed_games(rows):
    """Empty/scheduled/canceled rows are not played games or zero production."""
    return [g for g in rows if any((p.get('minutes') or 0) > 0 for p in g['players'])]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--team', default='Kansas')
    args = ap.parse_args()
    url = 'https://api.collegebasketballdata.com/games/players?' + urlencode({'season': args.season, 'team': args.team})
    request = Request(url, headers={'Authorization': 'Bearer '+api_key()})
    with urlopen(request, timeout=45) as response: raw = response.read()
    rows = validate(json.loads(raw), args.season, args.team)
    now = datetime.now(timezone.utc); stamp = now.strftime('%Y%m%dT%H%M%S%fZ')
    slug = ''.join(c.lower() if c.isalnum() else '-' for c in args.team)
    folder = ROOT/'data/cbbd'/slug/str(args.season); folder.mkdir(parents=True, exist_ok=True)
    observed = observed_games(rows)
    metadata = {'provider': 'CollegeBasketballData', 'url': url, 'fetched_at': now.isoformat(),
                'season': args.season, 'team': args.team, 'returned_games': len(rows),
                'observed_games': len(observed), 'unusable_game_rows': len(rows)-len(observed),
                'last_observed_game': max((g['startDate'] for g in observed), default=None), 'sha256': hashlib.sha256(raw).hexdigest(),
                'used_in_grades': False}
    (folder/f'{stamp}.json').write_bytes(raw)
    (folder/f'{stamp}.meta.json').write_text(json.dumps(metadata, indent=2))
    (folder/'latest.json').write_bytes(raw)
    (folder/'latest.meta.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata))

if __name__ == '__main__': main()
