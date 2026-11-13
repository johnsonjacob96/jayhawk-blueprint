"""Portable inference for a learned, conditional next-season production model.

No recruiting/eligibility assumption: estimates are conditional on appearing in
the next D-I season. Full-season backtests do not validate November forecasts.
"""
from math import isfinite
from .model import FEATURES, blend

def inputs(player, previous, dist, previous_dist, destination_conference, destination='Kansas'):
    v, _ = blend(player, previous, dist, previous_dist)
    values = dict(v)
    values['height'] = (player.get('height_inches') or 78) / 12
    values['transfer'] = float(player['team'] != destination)
    for label in ['Fr', 'So', 'Jr', 'Sr']:
        values['class:' + label] = float(player['class'] == label)
    values['source:' + player['conference']] = 1.
    values['destination:' + destination_conference] = 1.
    values['ku'] = float(destination == 'Kansas')
    for k in FEATURES + ['porpag']:
        values['ku:' + k] = values['ku'] * (v[k] - .5)
    return values

def predict(values, artifact):
    result = artifact['intercept']
    for k, coefficient in zip(artifact['features'], artifact['coefficients']):
        result += values.get(k, 0.) * coefficient
    result += ku_transfer_adjustment(values, artifact)
    if not isfinite(result):
        raise ValueError('Non-finite outcome estimate')
    return result

def ku_transfer_adjustment(values, artifact):
    """Shared translation adjustment, not a player/season success label."""
    calibration = artifact.get('ku_transfer_calibration', {})
    return calibration.get('offset', 0.) if values.get('ku') == 1 and values.get('transfer') == 1 else 0.

def shrunk_residual(residuals, prior_strength):
    if prior_strength <= 0:
        raise ValueError('Calibration prior must be positive')
    return sum(residuals) / (len(residuals) + prior_strength)

def explain(values, artifact, limit=4):
    """Associations relative to the training mean, not causal trait effects."""
    contributions = [(k, (values.get(k, 0.) - mean) * c)
                     for k, mean, c in zip(artifact['features'], artifact['means'], artifact['coefficients'])]
    return [{'feature': k, 'contribution': round(v, 3)}
            for k, v in sorted(contributions, key=lambda x: abs(x[1]), reverse=True)[:limit]]
