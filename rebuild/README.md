# Jayhawk Blueprint rebuild

Kansas-specific college basketball evaluation with an empty starting roster. Current evidence: 2026–27. Planning horizon: 2027–28. The owner explicitly chose **zero assumed returners** on 2026-11-13; evaluate the whole national pool, not only announced transfers.

## Run

No Python packages, browser keys, or build framework are required.

```sh
python3 rebuild/build.py --season 2027 --as-of 2026-11-13
python3 -m http.server 8000 --directory rebuild/web
```

To fetch a fresh current-season snapshot, supply the actual Chicago date and `--refresh`. Cached data cannot be silently relabeled with a new date. Open `rebuild/web/index.html` directly for an offline preview, or serve the directory. Roster/watchlist storage is per browser and origin. CSV export preserves selections outside that browser.

```sh
cd rebuild
python3 -m unittest discover -s tests -v
python3 validate.py
```

`validate.py` requires historical raw files for each fold; it reports available coverage. Do not infer exhaustive transfer coverage from its joined records.

## What changed from the original

The original `index.html` is preserved in `legacy/index.html`. It used embedded Synergy data, manual KU benchmarks and position weights, hard-coded roster needs, three name-specific score overrides, conference-tier translation assumptions and a nonlinear ceiling lift. It had a useful conceptual separation between quality, fit, translation and confidence, but historical calibration was explicitly a future hook.

This version derives profile medians from actual KU player-season statistics. Six explicit, overlapping role rules identify historical examples. Benchmarks are empirical; role gates, equal feature weighting and shrinkage strengths are still provisional modeling choices. No manual name overrides, roster need bonus, recruitment probability, or predicted KU production is included.

## Model contract

- Reference cohort: KU rotation players (≥20% minutes and ≥15 games) in 2008, 2012, 2018, 2020 and 2022. This is an initial deep-run/elite-season cohort, not every successful KU team. 2018 represents on-court results including later vacated results. 2020 is included despite the canceled tournament.
- Normalize features to national rotation-player percentiles within each season; derive role centers using historical KU medians. This reduces era scale differences but does not remove all era, competition or role confounding.
- Fit: equal-weight RMS distance in the role's feature space, expressed as a percentile against current rotation players in the role's broad height band. Scores measure resemblance, not success probability. Better-than-profile values can reduce resemblance.
- Quality: shrinkage-adjusted national percentile of PORPAG; separate from fit. This is a production proxy, not a next-year impact projection.
- Current-season evidence shrinks toward the prior season using exact provider ID **and** exact name. No fuzzy name joins. Prior evidence is discounted by 0.65, then population median fills remaining uncertainty.
- Exposure prior: 75 three-point attempts, 50 free throws, 100 two-point attempts, 300 estimated minutes otherwise. Estimated minutes = games × 40 × minute share; approximation excludes overtime and missed team games. Priors are explicit tuning choices, not learned constants.
- Confidence: mean evidence weight, not a calibrated uncertainty interval. Historical cohort size is shown separately. Missing attempts remain missing; zero makes are zero.
- One player may match several roles. All national players remain visible; no player is assumed eligible, interested, available or entering the portal. Six archetypes are options, not six mandatory lineup positions.
- Roster builder: blank by default; roles and minutes are explicit user choices. Regulation budget is 200 player-minutes; exceeding it is visibly flagged. Changing the roster does not change base player grades.

## Data and refresh

Public source: `https://barttorvik.com/getadvstats.php?year=YYYY` (season-ending year). Source schema was inspected on 2026-11-13: 78 columns. The parser validates season, IDs, count consistency and minute-share units, and rejects duplicate IDs. It does not assume every published column is mapped or validated. On the initial run there were 4,534 player records across 364 teams. This is feed coverage, not an assertion of complete roster coverage.

`data/raw/` holds current cached payloads and provenance/hash sidecars. Refreshes preserve dated source payloads in `data/snapshots/`. `data/grades/` holds dated compact grade exports. Rebuilding is deterministic for fixed source bytes and model version. Files under `web/` are deployable static output. No secret is embedded in the application.

GitHub Actions refreshes daily at 12:15 UTC (6:15 a.m. CST / 7:15 a.m. CDT) and supports manual execution. It preserves compressed grade snapshots in the repository and raw-source artifacts for 90 days. A failed refresh does not publish a newly dated stale board. `data.js` keeps its source snapshot date visible. Automated schedule execution and upstream source uptime are not guaranteed.

## Initial validation

The rolling-origin diagnostic matched 4,318 observed national school changes, including 16 incoming Kansas players, with prior minute share ≥20%. Historical profiles strictly preceded each origin season. No destination-minute threshold was applied.

| Diagnostic | KU fit similarity vs next PORPAG | Prior PORPAG vs next PORPAG |
|---|---:|---:|
| National Spearman correlation | 0.258 | 0.471 |
| Kansas (n=16) | 0.294 | 0.329 |

This is an association diagnostic using full-season, unshrunk inputs, **not validation of the live early-season scoring pipeline**. Missing destination records are excluded, role coverage varies by fold, school changes are not a complete transfer registry, and the KU sample is tiny. It does not establish added predictive value from fit. See `validation-report.json` for rows and limitations.

## Next research priorities

1. Expand success definitions to regular-season adjusted strength and deeper KU cohorts; use all other KU seasons as controls. Test sensitivity to era and cohort choice.
2. Rebuild national transfer labels including unmatched, injured, redshirted and non-rotation outcomes with explicit missingness. Use stable IDs and source-team checks.
3. Fit a regularized next-year impact model using prior production, age/class, role, competition and destination context; use rolling-season validation against prior-production baselines.
4. Backtest November/December snapshots using only information available at those dates. Tune shrinkage and report uncertainty calibration.
5. Add licensed Synergy play-type volume and efficiency when accessible. Box-score defense does not establish scheme/film fit.
6. Turn accumulated daily grade snapshots into version-aware trend views and add roster complementarity tests. Do not substitute a weighted roster average for a team-win forecast.

## Design and assets

KU blue, crimson, warm neutral canvas; locally hosted NCAA Kansas Jayhawks display font for headings/titles; system sans-serif for data. `ui-ux-pro-max` searches selected the data-dense dashboard pattern. The marketing/gateway portion of the broad search was rejected as irrelevant.

- Jayhawk image: https://a.espncdn.com/i/teamlogos/ncaa/500/2305.png
- Display typeface: NCAA Kansas Jayhawks / The Sports Fonts, https://famfonts.com/kansas-jayhawks/ (download: https://famfonts.com/zips/kansas-jayhawks.zip). Personal research use; no endorsement claimed.
- Historical cohort context: https://kuathletics.com/documents/download/2024/5/7/G1_KUMBB-Omaha-1.pdf
- Current season: https://kuathletics.com/sports/mens-basketball/schedule
