#!/usr/bin/env python3
"""Time-ordered outcome experiment. NumPy is needed for training, not refreshes.

Selection: rolling validation destination seasons 2020–2023; one fixed final
test on 2024–2026. Primary metric: transfer MAE in next-season PORPAG units.
The original frozen test excludes its outcomes during fitting. Final training
uses all outcomes through 2026. Later KU calibration uses 2020–2026 chronological
tuning, documented separately; no permanent outcome holdout is kept.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from blueprint.model import parse, distribution, FEATURES
from blueprint.outcomes import inputs, predict, shrunk_residual

ROOT = Path(__file__).resolve().parent
VALIDATION = (2020, 2021, 2022, 2023)
TEST = (2024, 2025, 2026)
PENALTIES = (10., 100., 1000.)

def dataset():
    seasons = {y: parse(json.loads((ROOT / f'data/raw/{y}.json').read_text()), y)
               for y in range(2008, 2027)}
    distributions = {y: distribution(ps) for y, ps in seasons.items()}
    rows = []; audit = []
    for origin in range(2010, 2026):
        old = {p['id']: p for p in seasons[origin-1]}
        future = {p['id']: p for p in seasons[origin+1]}
        conferences = {p['team']: p['conference'] for p in seasons[origin]}
        eligible = matched = missing_context = 0
        for p in seasons[origin]:
            if p['minutes_share'] < 20 or p['games'] <= 0 or p['porpag'] is None:
                continue
            eligible += 1
            q = future.get(p['id'])
            if not q or q['name'] != p['name'] or q['porpag'] is None:
                continue
            matched += 1
            # Prior-year destination conference is available before the outcome.
            dest_conf = conferences.get(q['team'])
            if not dest_conf:
                missing_context += 1
                continue
            prior = old.get(p['id'])
            if prior and prior['name'] != p['name']:
                prior = None
            rows.append({'year': origin+1, 'id': p['id'], 'name': p['name'],
                         'source_team': p['team'], 'destination_team': q['team'],
                         'destination_minutes_share': q['minutes_share'],
                         'transfer': p['team'] != q['team'], 'ku': q['team'] == 'Kansas',
                         'target': q['porpag'], 'carry': p['porpag'],
                         'x': inputs(p, prior, distributions[origin], distributions[origin-1], dest_conf, q['team'])})
        audit.append({'origin_season': origin, 'eligible_origins': eligible,
                      'matched_next_season': matched, 'unobserved_next_season': eligible-matched,
                      'missing_prior_destination_context': missing_context})
    hashes = {str(y): hashlib.sha256((ROOT/f'data/raw/{y}.json').read_bytes()).hexdigest() for y in seasons}
    return rows, audit, hashes

def names_for(rows, variant):
    if variant == 'production':
        return ['porpag']
    keys = set(k for r in rows for k in r['x'] if not k.startswith('ku'))
    if variant == 'kansas':
        keys |= {'ku'} | {'ku:'+k for k in FEATURES+['porpag']}
    return sorted(keys)

def fit(rows, variant, penalty):
    names = names_for(rows, variant)
    x = np.array([[r['x'].get(k, 0.) for k in names] for r in rows])
    y = np.array([r['target'] for r in rows])
    means = x.mean(axis=0)
    scales = x.std(axis=0); scales[scales < 1e-8] = 1.
    # Do not scale rare Kansas indicators to unit variance: shrink their small
    # sample adjustments more heavily than well-supported national effects.
    for i, k in enumerate(names):
        if k.startswith('ku'):
            scales[i] = 1.
    z = (x - means) / scales
    coefficients = np.linalg.solve(z.T @ z + penalty * np.eye(len(names)), z.T @ (y-y.mean())) / scales
    return {'variant': variant, 'penalty': penalty, 'features': names,
            'means': means.tolist(), 'coefficients': coefficients.tolist(),
            'intercept': float(y.mean()-means@coefficients), 'training_rows': len(rows),
            'trained_through': max(r['year'] for r in rows)}

def rank(values):
    order = np.argsort(values, kind='stable'); result = np.empty(len(values))
    start = 0
    while start < len(values):
        end = start+1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        result[order[start:end]] = (start+end-1)/2
        start = end
    return result

def metrics(rows, predictions):
    if not rows: return {'n': 0}
    y = np.array([r['target'] for r in rows]); p = np.array(predictions)
    error = p-y
    rho = float(np.corrcoef(rank(y), rank(p))[0, 1]) if len(y)>2 and len(set(p))>1 else None
    return {'n': len(y), 'mae': round(float(np.abs(error).mean()), 4),
            'rmse': round(float(np.sqrt((error**2).mean())), 4),
            'bias': round(float(error.mean()), 4), 'spearman': round(rho, 4) if rho is not None else None}

def groups(rows, predictions):
    result = {}
    for name, select in [('all', lambda r: True), ('transfers', lambda r: r['transfer']),
                         ('kansas', lambda r: r['ku']), ('kansas_transfers', lambda r: r['ku'] and r['transfer'])]:
        idx = [i for i, r in enumerate(rows) if select(r)]
        result[name] = metrics([rows[i] for i in idx], [predictions[i] for i in idx])
    return result

def choose(validation):
    """Selection is deliberately unable to inspect final-test results."""
    best = {}
    for variant in ('production', 'skills', 'kansas'):
        best[variant] = min((r for r in validation if r['variant'] == variant),
                            key=lambda r: r['metrics']['transfers']['mae'])
    # Kansas adjustments must improve BOTH national transfers and KU rows on
    # development folds. The small KU sample still cannot establish causality.
    national = min([best['production'], best['skills']], key=lambda r: r['metrics']['transfers']['mae'])
    ku = best['kansas']
    if (ku['metrics']['transfers']['mae'] < national['metrics']['transfers']['mae']
        and ku['metrics']['kansas']['mae'] < national['metrics']['kansas']['mae']):
        return ku, best
    return national, best

def calibrate_transfers(rows, production):
    """Exploratory KU transfer calibration; no permanent outcome holdout.

    Each chronological check fits only earlier outcomes. The checks are also
    used to select shrinkage, so they are tuning evidence, not an untouched test.
    Retain the national skill model and shrink the KU mean residual toward zero.
    """
    strengths = (5., 10., 25., 50., 100.)
    checks = []
    for year in range(2020, 2027):
        train = [r for r in rows if r['year'] < year]
        test = [r for r in rows if r['year'] == year and r['ku'] and r['transfer']]
        if not test:
            continue
        model = fit(train, production['variant'], production['penalty'])
        past = [r for r in train if r['ku'] and r['transfer']]
        residuals = [r['target'] - predict(r['x'], model) for r in past]
        for r in test:
            checks.append((r, predict(r['x'], model), residuals))
    tested = [r for r, _, _ in checks]
    baseline = metrics(tested, [p for _, p, _ in checks])
    candidates = [{'prior_strength': k,
                   'metrics': metrics(tested, [p + shrunk_residual(residuals, k)
                                             for _, p, residuals in checks])} for k in strengths]
    winner = min(candidates, key=lambda c: c['metrics']['mae'])
    enabled = winner['metrics']['mae'] < baseline['mae'] and winner['metrics']['rmse'] < baseline['rmse']
    strength = winner['prior_strength']
    ku = [r for r in rows if r['ku'] and r['transfer']]
    # Remove any previous calibration before rebuilding it (idempotent).
    base = {k: v for k, v in production.items() if k != 'ku_transfer_calibration'}
    residuals = [r['target'] - predict(r['x'], base) for r in ku]
    offset = shrunk_residual(residuals, strength) if enabled else 0.
    audit = [{'id': r['id'], 'name': r['name'], 'season': r['year'],
              'source_team': r['source_team'], 'prior_porpag': round(r['carry'], 3),
              'ku_porpag': round(r['target'], 3), 'ku_minutes_share': r['destination_minutes_share'],
              'base_fitted_porpag': round(predict(r['x'], base), 3),
              'residual': round(residual, 3)} for r, residual in zip(ku, residuals)]
    artifact = {'offset': offset, 'prior_strength': strength, 'training_rows': len(ku),
                'trained_through': max(r['year'] for r in ku), 'enabled': enabled}
    check_rows = [{'id': r['id'], 'season': r['year'], 'name': r['name'],
                   'trained_through': r['year'] - 1, 'prior_ku_transfers': len(residuals),
                   'actual': r['target'], 'base_prediction': p,
                   'adjusted_prediction': p + shrunk_residual(residuals, strength)}
                  for r, p, residuals in checks]
    report = {**artifact, 'method': 'mean KU incoming-transfer residual, shrunk toward zero',
              'check_years': list(range(2020, 2027)), 'baseline': baseline,
              'selected_check': winner['metrics'], 'candidates': candidates,
              'checks': check_rows, 'players': audit,
              'validation_status': 'Exploratory chronological tuning; not an independent test',
              'limitations': ['Only 16 matched KU incoming transfers; not a causal effect of Kansas.',
                             'Shared offset calibrates production level; it does not improve within-year player ordering.',
                             'Player audit residuals use the final fitted model and are not out-of-sample errors.',
                             'All individual outcomes count equally, including low-minute KU outcomes. No team-season success labels.',
                             'No outcome is assigned to unmatched or absent players. November inputs remain unvalidated.']}
    return artifact, report

def main():
    rows, audit, hashes = dataset()
    validation = []
    for variant in ('production', 'skills', 'kansas'):
        for penalty in PENALTIES:
            pooled = []; estimates = []
            for year in VALIDATION:
                train = [r for r in rows if r['year'] < year]
                test = [r for r in rows if r['year'] == year]
                model = fit(train, variant, penalty)
                pooled.extend(test); estimates.extend(predict(r['x'], model) for r in test)
            validation.append({'variant': variant, 'penalty': penalty, 'metrics': groups(pooled, estimates)})
    selected, best = choose(validation)
    train = [r for r in rows if r['year'] < min(TEST)]
    heldout = [r for r in rows if r['year'] in TEST]
    tests = {'carry_forward': groups(heldout, [r['carry'] for r in heldout])}
    frozen = {}
    for variant, choice in best.items():
        model = fit(train, variant, choice['penalty']); frozen[variant] = model
        tests[variant] = groups(heldout, [predict(r['x'], model) for r in heldout])
    variant = selected['variant']
    production = fit(rows, variant, selected['penalty'])
    production.update({'version': 'outcomes-1', 'target': 'next-season PORPAG, conditional on observed D-I return',
                       'selection_years': list(VALIDATION), 'test_years': list(TEST),
                       'selected_before_test': True, 'early_season_validated': False})
    report = {'version': 'outcomes-1', 'target': production['target'], 'origin_rotation_floor': 20,
              'selection_years': list(VALIDATION), 'test_years': list(TEST),
              'training_rows': len(rows), 'selected': {'variant': variant, 'penalty': selected['penalty']},
              'validation': validation, 'test': tests, 'audit': audit, 'source_sha256': hashes,
              'limitations': ['Observed consecutive D-I seasons only: no outcome is assigned to missing players.',
                             'Players may recur across chronological folds; these are not independent person-level trials.',
                             'End-of-season inputs only. Early-season blended forecasts remain unvalidated.',
                             'PORPAG is a production proxy, not team wins or scheme defense.',
                             'Prior-year destination conference is context, not game-level opponent adjustment.',
                             'Historical role similarity is separate from the outcome model.',
                             'Kansas-only samples are small; predictive coefficients are not causal effects.']}
    report['test_by_year'] = {}
    for year in TEST:
        subset = [r for r in heldout if r['year'] == year]
        report['test_by_year'][str(year)] = {
            name: groups(subset, [predict(r['x'], frozen[name]) for r in subset])
            for name in ('production', variant)}
    # Paired bootstrap by player ID retains repeated seasons within a player.
    transfers = [r for r in heldout if r['transfer']]
    errors = {}
    for r in transfers:
        a = abs(predict(r['x'], frozen['production'])-r['target'])
        b = abs(predict(r['x'], frozen[variant])-r['target'])
        errors.setdefault(r['id'], []).append(a-b)
    sums = np.array([sum(v) for v in errors.values()])
    counts = np.array([len(v) for v in errors.values()])
    rng = np.random.default_rng(20261113); improvements = []
    for _ in range(2000):
        idx = rng.integers(0, len(sums), len(sums))
        improvements.append(float(sums[idx].sum()/counts[idx].sum()))
    report['paired_transfer_mae_improvement'] = {
        'comparison': 'calibrated production baseline minus selected model',
        'player_clusters': len(sums), 'bootstrap_replicates': 2000,
        'percentile_95_interval': np.percentile(improvements, [2.5, 97.5]).tolist(),
        'note': 'Descriptive player-cluster bootstrap; three held-out seasons do not capture all era uncertainty.'}
    calibration, calibration_report = calibrate_transfers(rows, production)
    production['version'] = report['version'] = 'outcomes-2'
    production['base_selected_before_test'] = True
    production['selected_before_test'] = False
    production['ku_transfer_calibration'] = calibration
    report['ku_transfer_calibration'] = calibration_report
    report['test_scope'] = 'Original national model only; excludes the later exploratory KU transfer calibration'
    (ROOT/'outcome-model.json').write_text(json.dumps(production, indent=2)+'\n')
    (ROOT/'outcome-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'selected': report['selected'], 'rows': len(rows), 'test': tests}, indent=2))

if __name__ == '__main__': main()
