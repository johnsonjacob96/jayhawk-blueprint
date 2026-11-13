import json
from pathlib import Path
import unittest
from datetime import datetime, timezone
from blueprint.outcomes import inputs, predict, explain, shrunk_residual
from blueprint.model import FEATURES
from fetch_cbbd import validate, as_of, observed_games

ROOT = Path(__file__).resolve().parents[1]

class OutcomeTests(unittest.TestCase):
    def test_inference_and_contributions(self):
        model = {'intercept': 1., 'features': ['ast', 'tov'], 'coefficients': [2., -1.], 'means': [.5, .5]}
        self.assertAlmostEqual(predict({'ast': .8, 'tov': .2}, model), 2.4)
        self.assertEqual(explain({'ast': .8, 'tov': .2}, model),
                         [{'feature': 'ast', 'contribution': .6}, {'feature': 'tov', 'contribution': .3}])

    def test_context_changes_without_using_roster_or_future_stats(self):
        p = {k: 20 for k in FEATURES+['porpag']}
        p.update(team='Test', conference='MAC', height_inches=78, **{'class':'Jr'},
                 estimated_minutes=1000, three_a=100, fta=100, two_a=100)
        d = {k: [0, 10, 20, 30] for k in FEATURES+['porpag']}
        a = inputs(p, None, d, d, 'B12', 'Kansas')
        b = inputs(p, None, d, d, 'MAC', 'Test')
        self.assertEqual(a['transfer'], 1.)
        self.assertEqual(b['transfer'], 0.)
        self.assertEqual(a['ast'], b['ast'])
        self.assertNotIn('destination:MAC', a)
        self.assertEqual(a['destination:B12'], 1.)

    def test_artifact_time_boundaries_and_kansas_gate(self):
        model = json.loads((ROOT/'outcome-model.json').read_text())
        report = json.loads((ROOT/'outcome-report.json').read_text())
        self.assertLess(max(report['selection_years']), min(report['test_years']))
        self.assertEqual(model['trained_through'], 2026)
        self.assertFalse(model['early_season_validated'])
        self.assertEqual(len(model['features']), len(model['coefficients']))
        self.assertEqual(model['variant'], report['selected']['variant'])
        if model['variant'] != 'kansas':
            self.assertFalse(any(k.startswith('ku') for k in model['features']))
        self.assertGreater(report['test']['skills']['transfers']['n'], 2000)

    def test_positive_and_negative_individual_outcomes_both_calibrate(self):
        self.assertEqual(shrunk_residual([2., -2.], 5), 0.)
        self.assertGreater(shrunk_residual([2., -1.], 5), 0.)
        self.assertLess(shrunk_residual([1., -2.], 5), 0.)
        self.assertEqual(shrunk_residual([], 5), 0.)
        with self.assertRaises(ValueError): shrunk_residual([1.], 0)

    def test_calibration_only_applies_to_incoming_ku_transfers(self):
        model = {'intercept': 2., 'features': [], 'coefficients': [],
                 'ku_transfer_calibration': {'offset': -.6}}
        self.assertAlmostEqual(predict({'ku':1., 'transfer':1.}, model), 1.4)
        self.assertEqual(predict({'ku':1., 'transfer':0.}, model), 2.)
        self.assertEqual(predict({'ku':0., 'transfer':1.}, model), 2.)

    def test_recent_outcomes_and_low_minutes_retained_in_calibration(self):
        report = json.loads((ROOT/'outcome-report.json').read_text())['ku_transfer_calibration']
        self.assertEqual(report['training_rows'], len(report['players']))
        recent = [r for r in report['players'] if r['season'] >= 2024]
        self.assertEqual(len(recent), 11)
        self.assertEqual({r['season'] for r in recent}, {2024,2025,2026})
        self.assertTrue(any(r['ku_minutes_share'] < 20 for r in recent))
        self.assertTrue(any(r['residual'] > 0 for r in recent))
        self.assertTrue(any(r['residual'] < 0 for r in recent))
        for r in report['checks']:
            self.assertLess(r['trained_through'], r['season'])

    def test_game_cutoff_rejects_future_and_naive_time(self):
        games = [{'startDate': '2025-11-01T20:00:00Z'}, {'startDate': '2025-12-01T20:00:00Z'}]
        cutoff = datetime(2025, 11, 15, tzinfo=timezone.utc)
        self.assertEqual(as_of(games, cutoff), games[:1])
        with self.assertRaises(ValueError): as_of(games, datetime(2025, 11, 15))

    def test_source_mismatch_and_duplicate_games_rejected(self):
        game = {'gameId': 1, 'season': 2027, 'team': 'Kansas', 'players': [], 'startDate': '2026-11-01T20:00:00Z'}
        with self.assertRaisesRegex(ValueError, 'mismatch'): validate([game], 2026, 'Kansas')
        with self.assertRaisesRegex(ValueError, 'Duplicate'): validate([game, game], 2027, 'Kansas')

    def test_unplayed_or_missing_box_scores_not_zero_outcomes(self):
        games = [{'players': []}, {'players': [{'minutes': 0}]}, {'players': [{'minutes': 31}]}]
        self.assertEqual(observed_games(games), games[2:])

if __name__ == '__main__': unittest.main()
