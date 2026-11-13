# Jayhawk Blueprint rebuild

Kansas-specific college basketball evaluation with an empty starting roster. Current evidence: 2026–27. Planning horizon: 2027–28. The owner explicitly chose **zero assumed returners** on 2026-11-13; evaluate the whole national pool, not only announced transfers.

## Current model — v0.4.0

The live production predictor now uses **CBBD only**, independently of Torvik inputs. Torvik still supplies KU historical resemblance, the board universe and the separately labeled current-quality filter. SportsDataverse NCAA league-wide RAPM provides a second, retrospective impact view. These providers may share underlying game data; they are not independent statistical replications.

- **KU grade:** 80% predicted-production percentile + 20% role resemblance. Explicit scouting preference, not empirically learned weights or a success probability. Production percentiles use the completed-outcome reference in `independent-model.json`.
- **Per possession:** points, assists, turnovers, rebounds, steals and blocks per 100 estimated on-court possessions. Denominator = team possessions × player minutes / team clock minutes. True shooting/eFG/usage retain their own denominators. This is not exact substitution tracking.
- **Moving up:** continuous origin-season source/destination conference net-strength gap and interactions with usage/efficiency. No future destination ratings. Model selected on chronological 2020–2026 folds; final fit uses every matched outcome through 2026. No permanent holdout. Early-season performance remains unvalidated.
- **Evidence:** CBBD values shrink with possessions/(possessions+500), with same-ID/name prior-season evidence discounted to 65%. Raw per-100 values are shown separately from blended model inputs.
- **Comparisons:** size within 2 inches, usage within 7 points, three-point attempt share within 20 points, all-feature RMS ≤0.25, evidence ≥25; no duplicate player names or forced three matches. Gates use prior-season usage/shot mix until 300 estimated current minutes when prior evidence exists.
- **Bigs:** Svi is no longer a spacing-big benchmark. Only source positions Stretch 4/PF/C/C qualify for that historical role. Fewer than 3 distinct benchmark players prevents grading; the remaining one-player spacing cohort is reference-only. Anchor candidates require an interior shot pattern, using the same prior/current basis.
- **Additional impact evidence:** SportsDataverse's 2026 RAPM file contains 4,974 rows. Official NCAA→ESPN aliases join to CBBD's ESPN source ID with season bounds, unique identities and confidence 1.0. Current build: 2,562 matched players. No 2027 file is currently published. Missing and prior-season evidence are labeled; RAPM does not enter grades until incremental predictive value is tested.
- **Coverage:** 4,365 / 4,534 verified Torvik→CBBD current matches; 169 remain unmatched and get no production grade. Player-name joins require verified team context. No fuzzy fallback. Source-specific confidence and dates remain visible.

Chronological model-selection metrics (CBBD PORPAG): transfers n=4,080, MAE 0.9282 → 0.8550; moving-up transfers n=1,142, MAE 0.9724 → 0.8456. Only 16 KU transfers are checked. These are tuning metrics, not an independent test. The old Torvik KU offset is not applied to a different target. See `independent-report.json`; rebuild with `python3 rebuild/train_independent.py` after fetching historical CBBD data.

The older v0.2/v0.3 model sections below are retained as development history; their accuracy claims and calibration do not describe v0.4.

## Run

Daily scoring needs no third-party Python packages, browser keys, or build framework. Research retraining uses NumPy; the CBBD predictor feed uses a server-side credential.

```sh
python3 rebuild/fetch_national.py --season 2026
python3 rebuild/fetch_national.py --season 2027 --refresh
python3 rebuild/fetch_sportsdataverse.py --season 2027
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

This version derives profile medians from actual KU player-season statistics. Six explicit, overlapping role rules identify historical examples. Benchmarks are empirical; role gates, equal feature weighting and shrinkage strengths are still provisional modeling choices. There are no manual name overrides, roster-need bonuses or recruitment probabilities. v0.2 adds a separate experimental production projection; its outcome test and limits are documented below.

## Model contract

- Reference cohort: KU rotation players (≥20% minutes and ≥15 games) in 2008, 2012, 2018, 2020 and 2022. This is an initial deep-run/elite-season cohort, not every successful KU team. 2018 represents on-court results including later vacated results. 2020 is included despite the canceled tournament.
- Normalize features to national rotation-player percentiles within each season; derive role centers using historical KU medians. This reduces era scale differences but does not remove all era, competition or role confounding.
- Role match: 100 × (1 − equal-weight RMS distance) in the role's percentile feature space. No second percentile transform. Current players must meet the role's broad height band; missing height/no games leaves them unrated. Scores measure resemblance, not success probability. Better-than-profile values can reduce resemblance.
- Quality: shrinkage-adjusted national percentile of PORPAG; separate from fit. This is a production proxy, not a next-year impact projection.
- Current-season evidence shrinks toward the prior season using exact provider ID **and** exact name. No fuzzy name joins. Prior evidence is discounted by 0.65, then population median fills remaining uncertainty.
- Exposure prior: 75 three-point attempts, 50 free throws, 100 two-point attempts, 300 estimated minutes otherwise. Estimated minutes = games × 40 × minute share; approximation excludes overtime and missed team games. Priors are explicit tuning choices, not learned constants.
- Confidence: mean evidence weight, not a calibrated uncertainty interval. Historical cohort size is shown separately. Missing attempts remain missing; zero makes are zero.
- One player may match several roles. All national players remain visible; no player is assumed eligible, interested, available or entering the portal. Six archetypes are options, not six mandatory lineup positions.
- Roster builder: blank by default; roles and minutes are explicit user choices. Regulation budget is 200 player-minutes; exceeding it is visibly flagged. Changing the roster does not change base player grades.

## Data and refresh

### Cloudflare hosting

Cloudflare Pages is a second public host for the same root export. Deploy with `bash rebuild/deploy_cloudflare.sh`; it stages an explicit public-file allowlist into ignored `_site/` and uses the existing Wrangler OAuth login. No API token is copied into CI or the repository. `wrangler.jsonc` selects project `jayhawk-blueprint`, production branch `main`.

The daily Mac refresh publishes to Cloudflare after committing/pushing the generated snapshot. GitHub Actions continues publishing GitHub Pages. Cloudflare uses direct uploads, so a GitHub push alone does not immediately deploy there: manual code releases should run the deploy script, and the daily refresh also picks up changes. Both refreshes require the existing Mac/network/authentication. Stable asset filenames revalidate on reload. Browser-local watchlists and rosters are separate on each hostname.

### Source snapshots

Public source: `https://barttorvik.com/getadvstats.php?year=YYYY` (season-ending year). Source schema was inspected on 2026-11-13: 78 columns. The parser validates season, IDs, count consistency and minute-share units, and rejects duplicate IDs. It does not assume every published column is mapped or validated. On the initial run there were 4,534 player records across 364 teams. This is feed coverage, not an assertion of complete roster coverage.

`data/raw/` holds current cached payloads and provenance/hash sidecars. Refreshes preserve dated source payloads in `data/snapshots/`. `data/grades/` holds dated compact grade exports. Rebuilding is deterministic for fixed source bytes and model version. Files under `web/` are deployable static output. No secret is embedded in the application.

A macOS LaunchAgent (`com.jarvis.jayhawk-blueprint-refresh`) runs `rebuild/refresh.sh` daily at 6:15 a.m. machine-local time (currently Central). It fetches data using the existing public endpoint, saves source payloads locally, commits compressed grade history, and pushes through existing GitHub CLI/git authentication. GitHub Actions then publishes the verified static export. The source returned HTTP 403 from GitHub-hosted runners, so cloud ingestion is not enabled. Refresh requires this Mac and its network/authentication to be available; the last successful snapshot date stays visible when a refresh fails. The refresh refuses to run across tracked uncommitted changes. Source payload retention is local; compressed grade snapshots are committed to the repository.

## Initial validation

The rolling-origin diagnostic matched 4,318 observed national school changes, including 16 incoming Kansas players, with prior minute share ≥20%. Historical profiles strictly preceded each origin season. No destination-minute threshold was applied.

| Diagnostic | KU fit similarity vs next PORPAG | Prior PORPAG vs next PORPAG |
|---|---:|---:|
| National Spearman correlation | 0.258 | 0.471 |
| Kansas (n=16) | 0.294 | 0.329 |

This is an association diagnostic using full-season, unshrunk inputs, **not validation of the live early-season scoring pipeline**. Missing destination records are excluded, role coverage varies by fold, school changes are not a complete transfer registry, and the KU sample is tiny. It does not establish added predictive value from fit. See `validation-report.json` for rows and limitations.

## Next research priorities

1. Backtest newly verified SportsDataverse lineup/possession features and obtain shot-pattern context from the external sources in [data-sources.md](data-sources.md).
2. Expand success definitions to regular-season adjusted strength and deeper KU cohorts; use all other KU seasons as controls. Test sensitivity to era and cohort choice.
2. Rebuild national transfer labels including unmatched, injured, redshirted and non-rotation outcomes with explicit missingness. Use stable IDs and source-team checks.
3. Extend the v0.2 learned impact model to true early-season snapshots, richer opponent context and independently measured defensive impact. Preserve time-ordered baseline comparisons.
4. Backtest November/December snapshots using only information available at those dates. Tune shrinkage and report uncertainty calibration.
5. Add licensed Synergy play-type volume and efficiency when accessible. Box-score defense does not establish scheme/film fit.
6. Turn accumulated daily grade snapshots into version-aware trend views and add roster complementarity tests. Do not substitute a weighted roster average for a team-win forecast.

## Design and assets

KU blue, crimson, warm neutral canvas; locally hosted NCAA Kansas Jayhawks display font for headings/titles; system sans-serif for data. `ui-ux-pro-max` searches selected the data-dense dashboard pattern. The marketing/gateway portion of the broad search was rejected as irrelevant.

- Jayhawk image: https://a.espncdn.com/i/teamlogos/ncaa/500/2305.png
- Display typeface: NCAA Kansas Jayhawks / The Sports Fonts, https://famfonts.com/kansas-jayhawks/ (download: https://famfonts.com/zips/kansas-jayhawks.zip). Personal research use; no endorsement claimed.
- Historical cohort context: https://kuathletics.com/documents/download/2024/5/7/G1_KUMBB-Omaha-1.pdf
- Current season: https://kuathletics.com/sports/mens-basketball/schedule

## Outcome model v0.2 (2026-11-13)

Fit remains historical KU resemblance. **Impact** is a separately displayed research estimate of next-season PORPAG. Since v0.3 the board shows PORPAG units, with a secondary percentile rank in details/exports among currently active players with at least 20% minute share and a source conference represented in training. It is conditional on appearing in the next Division I season, not eligibility or portal availability. The current roster never enters either grade.

`train_outcomes.py` fits ridge regression using 29,873 observed consecutive-season transitions, with origin seasons 2010–2025. Only origin players with >=20% minutes and valid production enter. Player joins require the same Torvik ID and exact name. Missing next-season records are excluded, not assigned zero; the audit counts 18,898 such origin records. This includes graduation, professional departures, sit-outs, coverage/identity gaps and other unknown reasons; it is not a transfer failure count.

Predictors: the same 11 evidence-blended statistical percentiles used for fit, blended PORPAG percentile, height, class, whether the player changes schools, and source/destination conference indicators. Training uses the destination school's conference from the **origin** season, never its future rating or outcome. Live inference uses Kansas's current conference. Conference context is not game-level opponent adjustment. Features are standardized using training rows only; coefficient magnitudes are regularized. A separate Kansas intercept/skill-interaction candidate receives stronger effective shrinkage because its rare indicators are not standardized upward.

Selection used rolling destination-season validation for 2020–2023, choosing penalties from 10, 100, 1000 by transfer mean absolute error. Kansas adjustments had to improve both national-transfer and Kansas validation error. The selected national skills model (penalty 1000) was frozen with training outcomes through 2023 and evaluated once on 2024–2026. The Kansas adjustment did not pass the development gate. After reporting that test, the selected specification was refit through 2026 for the deployed artifact. The final-test results do not describe an independent test of that later refit.

| Frozen-model test, 2024–2026 | Transfers (n=2,412): MAE | Rank correlation | KU transfers (n=11): MAE |
|---|---:|---:|---:|
| Carry forward raw PORPAG | 0.9866 | 0.4849 | 1.5135 |
| Fitted prior-production-only model | 0.9431 | 0.4951 | 1.3798 |
| Learned skills + context | 0.8984 | 0.5341 | 1.1461 |

The selected model reduced transfer MAE by 4.7% versus the fitted baseline, with improvement in each test year, and 8.9% versus carry-forward. A 2,000-replicate paired player-cluster bootstrap gives a descriptive 95% interval of 0.029–0.060 PORPAG for MAE improvement over the fitted baseline. It does not cover all era/conference uncertainty. KU's 11 held-out transfers are too few to establish reliable program-specific calibration; the model overpredicted them by 0.734 PORPAG on average.

**Full-season test only.** Current November forecasts use the existing early-season blending, which this test does not validate. They are labeled experimental in the board, player details and CSV. This predicts a production proxy, not team wins, true defensive impact or individual success probability. Features are correlated: a small or negative partial shooting coefficient does not mean shooting is undesirable. Displayed contributions are associations relative to training means, not causal effects or percentages summing to 100.

Reproduce with NumPy available:

```bash
python3 rebuild/train_outcomes.py
python3 rebuild/build.py --season 2027 --as-of 2026-11-13
cd rebuild
python3 -m unittest discover -s tests -v
```

Training requires the private cached Torvik seasons 2008–2026 in `rebuild/data/raw/`. `outcome-report.json` records source hashes, coverage audit, tuning folds, frozen-test results and limitations. `outcome-model.json` contains portable coefficients; daily scoring uses only Python's standard library. Dated grade filenames now include both model version and coefficient hash, retaining separate experiments on the same source snapshot.

## Supplemental game-log corpus

`fetch_cbbd.py --season 2027 --team Kansas` stores timestamped CollegeBasketballData responses privately under ignored `rebuild/data/cbbd/`. It validates season/team, duplicate identities and shooting counts; it counts empty/unplayed game rows separately. Event-time slicing requires a timezone-aware cutoff. Retrospective data can include later source corrections, so these are not proven historical publication-time snapshots.

Authentication: `CBD_API_KEY` or the macOS Keychain service `jayhawk-blueprint.cbbd`, account `api`. Never put the key or raw response corpus in the public repo. The daily 6:15 Central job adds one Kansas request (~31/month) alongside the national Torvik refresh. A supplemental fetch failure is logged; it does not block independently sourced public grades. **Historical note: superseded in v0.4, where national CBBD data powers projections.** Source research, availability and coverage issues: [data-sources.md](data-sources.md).

## Kansas history comparisons v0.2.1

The owner clarified that the missing 2024–2026 seasons were in Kansas DNA comparisons, not impact-model training. Historical comparisons now include qualifying KU rotation players from **every completed source season, 2008–2026**. The page defaults to recent seasons 2024, 2025 and 2026 and offers individual-season or all-season browsing. Player detail comparisons search this expanded pool too; comparison rows show the season and whether it belongs to the selected benchmark cohort. Kansas DNA lists observed PORPAG alongside comparisons so resemblance is not mistaken for equivalent production.

The ideal-role benchmark medians still use the explicitly selected 2008, 2012, 2018, 2020 and 2022 teams. They are labeled separately from the broader comparison pool. Adding comparisons does not recalculate the benchmark centers. Historical role eligibility remains >=15 games and >=20% minutes, plus the published role rule. No current/future season enters comparisons. Some season/role combinations legitimately have no qualifying player; the UI explains that state.

The daily builder now loads all source seasons from 2008 onward, caching completed seasons locally and refreshing the active season only. Tests cover inclusion of 2024–2026, exclusion of the current season, preservation of benchmark centers and selection of a recent player as the nearest comparison. The impact model continues using all 29,873 matched training outcomes through 2026.

## Role scores and individual KU outcomes — v0.3.0

The owner flagged excessive 99.9/100 scores and clarified that recent KU teams must not be treated as uniformly bad. Two distinct changes:

1. **Fix role scoring.** Previously, absolute similarity was stretched to a current-pool percentile, then each player's highest of six ranks was shown. Height bands defined the reference pool but did not restrict candidates, so a 6′1″ player could receive a 100 connecting-forward score. The displayed match is now the original absolute resemblance, and a shared height guard restricts roles. No arbitrary ceiling is applied. On the same 2026-11-13 snapshot, the maximum eligible match is 95.9, with zero scores ≥99.9. Default-board top scores previously included 16 players ≥99.9. Projected production now displays PORPAG, with ranks explicitly secondary.
2. **Learn from individual KU transfers.** All 16 matched incoming transfers contribute equally to an experimental, shrunk mean-residual calibration. Actual-minus-national-fitted production can be positive or negative; no team-season labels or destination-minutes floor are applied. Eleven observations are from 2024–2026. Kansas DNA shows the recent individual outcomes, fitted national estimates, residuals and minute shares, with earlier transfers expandable. Fitted residuals are explanatory training evidence, not independent prediction errors.

The national ridge model remains unchanged. Incoming KU estimates receive `sum(actual − national_fitted) / (n + prior_strength)`. The 16 residuals total −13.269 PORPAG; selected prior strength 5 gives an offset of **−0.63186 PORPAG**. Current KU players receive no incoming-transfer adjustment. This calibrates the shared production level and does not change the within-year ordering of incoming candidates; it is not proof that Kansas causes a production loss or that every transfer disappoints.

Shrinkage strengths 5/10/25/50/100 were compared using chronological checks for destination seasons 2020–2026. Each fold trains the national model and KU residuals using earlier outcomes only. Across 15 checked KU transfers, the selected adjustment reduced MAE 1.1668 → 1.1136 and RMSE 1.3636 → 1.2280; overprediction bias fell 0.8714 → 0.5130. Pooled cross-year rank correlation worsened 0.6536 → 0.3821 as annual offsets changed. These same checks selected the strength, so **this is exploratory tuning evidence, not an independent test**. The sample is too small for reliable trait-specific KU effects. A recheck of the original broad KU intercept/skill-interaction candidate over 2020–2026 still did not pass the selection gate; it remains disabled.

The earlier 2024–2026 national-model test is retained and labeled as applying to the base model only, excluding this new calibration. Final national fitting and KU calibration use all matched outcomes through 2026; nothing is permanently held out. `train_outcomes.py` reproduces both artifacts. Daily refresh uses the exported calibration without NumPy or model retraining. Model version and coefficient hash distinguish old percentile histories from new match histories; do not interpret that version break as player improvement/decline.
