# Data sources for Kansas evaluation

Verified 2026-11-13. Priority is incremental scouting value and reliable access. No new subscription was purchased. Official API/CLI access was checked first; the existing CBBD key was verified and placed in macOS Keychain for unattended use.

| Priority / source | What it adds | Access and current status |
|---|---|---|
| 1. [CollegeBasketballData](https://api.collegebasketballdata.com/getting-started) | Dated player game logs for early-season tests; actual minutes; opponent context; shot breakdowns, portal records and recent lineups | Existing key verified. Daily Kansas game logs connected; five historical KU reference seasons fetched. National season stats now power production grades (v0.4). |
| 2. [EvanMiya](https://evanmiya.com/how-it-works) | Offensive/defensive player impact accounting for other players on the floor; skill projections and opponent-adjusted lineup analysis | Best next independent benchmark for defense and role translation. Prior project has account configuration, but usable export/API access has not been verified. Use supported licensed exports; no public API confirmed. |
| 3. [KenPom official API](https://kenpom.com/register-api.php) | Team strength, schedule difficulty, tempo, four factors and historical/preseason context | Listed $145/year including web access. Existing website credentials do not establish API access. No API purchase/key verified. Published endpoints are primarily team/context data, not a player-impact feed. |
| Foundation. [Bart Torvik](https://barttorvik.com/playerstat.php?year=2027) | Broad historical/current player rates, production, role comparisons and transfer-outcome training | Supplies role profiles and current-quality context; no longer supplies the production predictor. Positional schema is checked; source hashes and snapshots retained. Public endpoint failed on GitHub-hosted runners, so the existing Mac job fetches and Pages publishes the result. |

CBBD's [published tiers](https://collegebasketballdata.com/api-tiers) currently provide 1,000 calls/month free, 5,000 for $1/month, and 30,000 for $5/month, sharing a quota with college football. The connected one-team daily fetch is about 31 calls/month; national season-wide endpoints need only three additional calls/day, about 124 total calls/month including Kansas logs. No per-team national crawl is needed. The actual account tier was not inferred from old code comments.

CBBD [availability documentation](https://api.collegebasketballdata.com/data-availability) lists broad player boxes from 2005, shot coordinates from 2019 with gaps, and usable lineup coverage from 2024. Those newer lineups cannot reconstruct the 2008/2012/2018/2020/2022 championship-era role profiles. Basketball seasons use ending years; portal cycles follow their own calendar. The portal endpoint's parameter is `year`, per its [operation reference](https://api.collegebasketballdata.com/api/recruiting); do not assume portal year equals destination basketball season. Provider athlete IDs also require a checked crosswalk before combining datasets.

## Expanded external search — verified beyond the existing stack

The owner explicitly rejected limiting research to providers already used. This search checked public documentation and actual access, not merely familiar brand names.

| Newly investigated source | Incremental value for KU | Verified access / decision |
|---|---|---|
| [SportsDataverse NCAA engine](https://hoopr.sportsdataverse.org/articles/college-basketball-rapm-model.html) | Possessions with ten players on the floor; league-wide offensive/defensive RAPM; teammate/opponent context | Public GitHub release downloads verified. Loaded 4,974 rows from 2026 and the official NCAA→ESPN alias table. Added to player details, with explicit season and possession count. Daily job checks for the current-season release. |
| [Hoop Explorer](https://hoop-explorer.com/) | Rim/midrange/three-point distributions, inferred play styles, on/off analysis, lineup and RAPM views | Normal browser loaded current 2026–27 player leaderboard and shot splits. Homepage documents exports; an automated export pipeline has not been verified. Current default view is high-tier only, so do not mistake that for national coverage. Candidate for style enrichment; not connected yet. |
| [CBB Analytics API](https://rest.cbbanalytics.com/docs) | Player/team possession and chance stats, lineup/on-off endpoints, assisted/unassisted and zone efficiency | Official v3 documentation loaded in browser. Boxes from 2011–12; play-by-play from 2018–19. Requires vendor-issued API key; no existing access or API price verified. Best next commercial source to investigate for possession and shot-profile features. |
| [ShotQuality](https://shotquality.com/) | Shot difficulty, defensive pressure and expected scoring rather than makes alone | Current official product describes college-basketball coverage, defender proximity and API access by request. Commercial access, historical coverage and redistribution terms not verified; no account or purchase made. Potentially the strongest complementary shot-quality signal, subject to access and validation. |
| [HD Intelligence](https://www.hdintelligence.com/services) | Transfer evaluation, lineup analysis and roster-construction services | Official service descriptions verified. No downloadable research feed or public API verified. Team-service offering, lower priority for this pipeline. |
| [Noah Basketball](https://www.noahbasketball.com/about) | Shooting arc/depth/consistency from tracked shots | Official team/facility tracking offering verified. No national player feed available to us verified; cannot assume installed-team coverage spans the player pool. |

**Provenance matters:** Hoop Explorer identifies NCAA/CBBD game data and KenPom/Torvik context. SportsDataverse's NCAA engine derives its possession data from NCAA records. More websites do not necessarily mean independent underlying observations. Add new measurements and methods, not repeated votes from the same boxes.

SportsDataverse [published releases](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_rapm) cover league RAPM ending years 2011–2026; the current-season 2027 file is absent. The application never relabels 2026 as current. Within-team RAPM is not interchangeable with league-wide RAPM. Standard-error columns documented in the model card were absent from the downloaded file; no confidence intervals are invented. Retrospective impact is displayed separately from the predictive grade.

SportsDataverse also publishes [box plus-minus](https://hoopr.sportsdataverse.org/articles/college-basketball-player-value-model.html), including current-season data. It is box-derived, not possession-derived RAPM; its documented coefficients fit 2025–26 data. It is not a point-in-time historical feature without leakage controls, and tiny-minute estimates are unstable. Not added as another automatic grade vote.

**Model priorities from this search:** use shot mix and creation context to distinguish rim finishers, post scorers, cutters and actual spacing bigs; use lineup-adjusted defensive evidence beyond steals/blocks; test those additions against the current transfer baseline. Commercial-feed access remains unresolved, not silently substituted with fabricated measurements.

## Observed CBBD coverage

Fresh Kansas `/games/players` requests returned the following. A usable game here means at least one player has positive recorded minutes; this is a minimum check, not a guarantee of complete boxes.

| Ending season | Returned game rows | Rows with recorded player minutes |
|---|---:|---:|
| 2008 | 40 | 40 |
| 2012 | 39 | 31 |
| 2018 | 38 | 38 |
| 2020 | 32 | 31 |
| 2022 | 41 | 40 |
| 2027, through Nov. 13 | 3 | 3 |

The 2020 March 12 row has no players. It must not count as a played game or zero production. Eight returned 2012 game rows also lack player boxes. Completeness must be reconciled against schedules before using these logs to judge historical early-season model accuracy. Current Kansas observations include games dated Nov. 3, 7 and 11 UTC. Cache metadata records fetch time, source URL and content hash.

The [CBBD terms](https://collegebasketballdata.com/terms) permit private caching, model training and derived outputs, while restricting raw-data redistribution and exposed API keys. Raw responses remain in ignored local storage; the public app exposes selected derived efficiency metrics and model outputs, not bulk raw responses.

## What changes the model next

1. Reconcile game coverage and identity mappings, then build national November/December/January input snapshots. Compare those forecasts against later production; tune shrinkage only on development years.
2. Add game-level opponent context and actual minutes, testing the incremental gain over the current conference-context model. Use known pregame/as-of ratings, never final-season ratings in early snapshots.
3. Audit portal-origin cohorts, including unmatched destinations, to measure selection bias. Missing observations stay unknown until resolved.
4. Compare against a separately sourced impact metric such as EvanMiya BPR. This helps test defensive value beyond blocks, steals and offensive production.
5. Test more historical KU seasons and lineup combinations after coverage is established. The failed Kansas adjustment is evidence to gather better data, not a reason to add a discretionary KU bonus.

[Synergy/Sportradar](https://developer.sportradar.com/basketball/reference/synergy-basketball-faqs) offers valuable possession/play-type context, but the owner's prior Synergy integration was shelved because of fragile authentication. Do not revive that integration as this task's dependency. If existing licensed exports become available, they could add pick-and-roll, cuts, spot-ups and post-up context. Published API history is generally only the latest two or three seasons, so it cannot replace the older KU historical corpus. No Synergy integration or purchase was initiated.
