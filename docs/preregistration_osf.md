# Preregistration — OSF

> **Document prepared for the OSF "OSF Preregistration" (v4) form. Content of this document is the authoritative registration record; the form fields map onto it section by section.**
> Once the registration is frozen, this document must not be modified anymore; any change after the final test has been consulted must be disclosed as a post hoc deviation.

---

## 1. Study Information

- **Title:** Laya as a Real-Time Probabilistic Decision Engine for Football: A Preregistered Multi-Agent Evaluation Protocol
- **Registration type:** Preregistered protocol — no data have been collected and no final test results have been inspected at the time of registration.
- **Authors:** Steve Djoumessi Mba — Independent Researcher (no institutional affiliation at time of registration)
- **Affiliation(s):** Independent Researcher
- **Email for correspondence:** 138932932+steve-dev-55@users.noreply.github.com
  (GitHub no-reply address preserving author privacy; replace with a
  personal address on the OSF form if preferred)
- **Date of registration:** 2026-09-27
- **Version of the study protocol:** 2.0.0 (French original authoritative; English adaptation available in the repository)
- **Persistent identifiers:**
  - Repository (code, MIT): https://github.com/steve-dev-55/laya-football-evaluation
  - This preregistration: https://doi.org/10.17605/OSF.IO/TPSQB (public, accepted 2026-09-26)
  - Preprint: [ARXIV ID — optional at registration time]
- **Existing registrations of this study:** none. This is the first registration of this study.

### Summary

This study evaluates Laya, a typed multilingual AI decision engine, as a real-time probabilistic forecaster of football match outcomes. For each included match, predictive distributions are elicited at fixed snapshots (pre-match; minutes 15, 30, 45, 60, 75, 85) and event-driven snapshots (immediately after each goal, red card, penalty, and substitution), over four targets: the final 1X2 result, the grouped final score (17 buckets), total corners (0–20, 21+), and total yellow cards (0–12, 13+). Point-in-time integrity is enforced and audited (automated leakage tests on 100% of snapshots). Laya is compared against baselines receiving identical information at identical cutoffs, under a strict temporal split, with inference clustered by match.

---

## 2. Hypotheses

All hypotheses below are **confirmatory**. They were written before any analysis of the final test set. Any analysis not listed here is **exploratory** and will be reported as such.

| ID | Theme | Hypothesis |
|----|-------|------------|
| **H1** | Temporal progression | The 1X2 log loss decreases as the cutoff moves from pre-match to 85 minutes. |
| **H2** | Calibration | Laya's calibration, measured by ECE and log loss, is better than that of the historical-frequency baseline at identical information. |
| **H3** | Event reaction | After a goal, the probability of the corresponding winning team increases on average, all else equal. |
| **H4** | Robustness | Semantically equivalent paraphrases do not strongly modify the predictive distribution. |
| **H5** | Counts | For corners and yellow cards, Laya's performance is compared **separately** against (a) a historical-mean baseline and (b) an adapted count model (Poisson or negative binomial). |

**Directionality:** H1, H3, H4 are directional as stated; H2 and H5 are superiority comparisons (Laya better than the named baseline for H2; two separate two-sided comparisons for H5).

---

## 3. Design

### 3.1 System under test

Laya, used through its SDK (typed tasks `choice` and `score`, multilingual variant). Package version, checkpoint hash, router configuration, and inference parameters are pinned in the frozen experiment manifest before execution. Announced (unverified) architectural characteristics are not treated as experimental facts.

### 3.2 Targets

| Target | Type | Support | Tail |
|---|---|---|---|
| 1X2 final result | derived from score distribution | home / draw / away | — |
| Grouped final score | `choice` | 16 exact scores (0–0 … 3–3) + `other` | `other` |
| Total corners | `score` | 0…20 | 21+ |
| Total yellow cards | `score` | 0…12 | 13+ |

Marginal goal tasks (home 0–7, 8+; away 0–7, 8+) are auxiliary and never recombined into a joint distribution.

### 3.3 Snapshots

- **Fixed cutoffs (seconds):** [0, 900, 1800, 2700, 3600, 4500, 5100] (pre-match, 15', 30', 45', 60', 75', 85'), created only if the match is still in progress at that instant.
- **Event-driven snapshots:** immediately after each goal, red card, penalty (awarded or taken), and substitution.

### 3.4 Information tiers

- **Tier A (pre-match):** form, available standings, head-to-head, authorized odds, pre-match context.
- **Tier B (minimal live):** A + score, cards, corners, dismissals, available events.
- **Tier C (full live):** B + shots, shots on target, possession, xG — where genuinely available at the cutoff.

Tiers are states of the same match; they are never treated as independent observations.

### 3.5 Point-in-time integrity (central rule)

At cutoff t, no artifact transmitted to Laya, no baseline feature, and no model-selection parameter may depend on information posterior to t for live data, or posterior to the pre-match cutoff for historical data. Enforcement: deterministic serialization; forbidden fields excluded by construction; three automated tests on **100% of snapshots** (no future events; no final fields; pre-match sources strictly before the pre-match cutoff); one negative injection test; manual audit of ≥5% of snapshots stratified by competition, season, cutoff, and event type.

---

## 4. Sampling Plan

- **Primary source (frozen):** StatsBomb Open Data — https://github.com/statsbomb/open-data, frozen at commit `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` (2026-09-07), license CC BY-NC-SA 4.0 (non-commercial scientific use). Field coverage required by the protocol (goals, cards, corners, substitutions, per-shot xG via `shot.statsbomb_xg`, possession, per-event timestamps) was verified by structural inspection. No secondary completion source; final scores are cross-checked against official public standings during the quality audit (protocol §3.2).
- **Competitions and seasons (frozen; amendment A1 from the initial big-5 plan, documented before registration — no competition offers three complete consecutive seasons in any open source):** three complete seasons, ten competitions, **2 403 matches** —
  - **2015/16 (men):** Premier League (380), La Liga (380), Serie A (380), Ligue 1 (377/380 present in source; 0.8% source-level missingness, below the 10% blocking threshold);
  - **2021/22 (men):** Indian Super League (115, incl. playoffs);
  - **2023/24 (women):** Liga F (240), NWSL 2023 calendar season (137, incl. playoffs), FA Women's Super League (132), Frauen Bundesliga (132), Serie A Women (130).
  Full per-competition table: `docs/frozen_corpus.json`.
- **Foreknowledge disclosure:** before registration, the author accessed only (a) match counts per competition-season and (b) the structural event-type inventory of one sample match per corpus block (field verification); no outcome-level data were observed or analyzed.
- **Target sample size:** 2 403 included matches (power objective, not a quota). **Power analysis (frozen, `docs/power_analysis.json`, `scripts/power_analysis.py`):** primary endpoint = 1X2 log loss, paired per-match difference, match-clustered percentile bootstrap (≥ 2 000 replicates), Holm–Bonferroni family m = 6 comparisons, α = 0.05. Planning assumptions: per-snapshot paired-difference SD σ_d = 0.15, intra-match correlation ρ = 0.30, K = 12 snapshots/match, n_test ≈ 1 200 (50% chronological test split). Results: **minimum detectable effect at 80% power = 0.0090** log-loss units (90% power: 0.0102); power = 0.888 for Δ = 0.01, > 0.99 for Δ ≥ 0.015; sensitivity across σ_d ∈ [0.10, 0.20], ρ ∈ [0.20, 0.50], K ∈ [8, 16]: MDE₈₀ ∈ [0.0060, 0.0120]. Monte-Carlo validation of the exact test procedure (300 sims × 2 000 replicates) agrees with the analytic noncentral-t computation within MC error; a mirror validation against the repository's `bootstrap_difference` implementation is included.
- **Inclusion:** finished and officially validated matches; no extra time; final score, events, and statistics available; timestamps precise enough for cutoffs; resolved team identities.
- **Exclusion (logged):** stopped/postponed/replayed/abandoned matches; extra time or shootouts; score–event inconsistencies; missing non-imputable targets; impossible timestamps; unresolved duplicates; post-match-only aggregates where live snapshots are required. Excluded matches are never replaced after consulting results.
- **Split (amendment A2, documented before registration):** strictly chronological 50/50 split **within each competition-season** — training = first chronological half, final test = second half (never used for any model choice); same-day matches stay in the same block. (The initial season-level split — train 2021-22 + 2022-23, test 2023-24 — is confounded by the amended corpus A1, whose seasons cover different populations; the per-competition chronological split preserves protocol §11.1 and eliminates domain-transfer bias for the baselines, each trained on earlier matches of its own competition.)

---

## 5. Variables

- **Outcomes (targets):** final 1X2; final score bucket (17 categories); total corners; total yellow cards. Conventions: goals (including penalties and own goals) count for the benefiting team over 90 minutes plus stoppage; shootout goals excluded; bench/staff cards excluded; second-yellow convention with preregistered sensitivity analysis.
- **Predictors (information tiers):** as defined in §3.4, with every variable carrying provenance and availability time.
- **Covariates for stratification:** competition, season, cutoff, tier, snapshot type.
- **Missing data:** never imputed from final statistics or realized outcomes; allowed representations are `null`, documented uniform omission (identical across systems), or a preregistered `unavailable` category. Missingness rates reported per variable/source/competition/season/cutoff.

---

## 6. Statistical Analysis Plan

### 6.1 Primary metrics (per target, frozen)

| Target | Primary metric |
|---|---|
| 1X2 | log loss (multiclass, clipping floor 1e-15) |
| Score buckets | log loss over the 17 categories |
| Corners | discrete CRPS |
| Yellow cards | discrete CRPS |

### 6.2 Secondary metrics

1X2: multiclass Brier, RPS (ordered classes), top-class accuracy, ECE (fixed bins + quantile-binning sensitivity), reliability curves, breakdowns by cutoff/competition/season/tier. Score buckets: multiclass Brier, RPS under a coherent order, top-bucket accuracy, calibration of frequent buckets and of `other`. Counts: MAE/RMSE of the expected value only if tail-compatible, discrete log score, Poisson/NB deviance, coverage (50/80/95%) and mean interval width, randomized PIT, tail mass.

### 6.3 Model comparison and inference

- Per-match contribution differences computed once per metric and model pair.
- **Stratified bootstrap clustered by match** (clusters = matches; all snapshots of a resampled match carried along), ≥2,000 replications.
- Report: mean difference, 95% CI, effect size.
- **Multiplicity:** Holm–Bonferroni within preregistered families of tests — **four families, one per target (1X2, score buckets, corners, yellow cards), each containing the six comparisons Laya vs each baseline**; frozen in `experiment_manifest.json` (decision `holm_bonferroni_families`, agents/evaluator.py `COMPARISON_FAMILIES`).
- A non-significant result is never interpreted as equivalence.

### 6.4 Robustness and event-reaction analyses (secondary)

Paraphrase set (versioned): mean absolute probability change, Jensen–Shannon, total variation, expected-value change, top-class flip rate, log-loss change. Format variants (field order, names, compact/indented, FR/EN if multilingual, descriptive dictionary). Event reactions within a predefined window, expected directions: home goal → P(1) up; away goal → P(2) up; home red card → P(1) down, P(2) possibly up; penalty → effect consistent with the benefiting team when the outcome is not posterior to the cutoff. Near-identical snapshot screening (oscillations, unexplained class changes, excessive concentration). Determinism audit: k=5 identical requests on ≥10% of snapshots (variance, flip rate, log-loss variation).

### 6.5 Baselines

Identical information at identical cutoffs. Minimal: uniform; historical frequency (per competition/season); current-score persistence (converted by a preregistered rule); count persistence. Statistical: independent/bivariate Poisson, Dixon–Coles, Poisson/NB for counts, multinomial logistic regression for 1X2, optional gradient boosting (temporal split only). Bookmaker odds: pre-match snapshot only (implied probabilities, margin removal by a preregistered method), unless timestamped live odds are integrated identically for all systems. Hyperparameters fixed on validation only. Any baseline using variables unavailable to Laya is excluded from the main comparison and reported as auxiliary.

---

## 7. Quality Gates / Stopping and Blocking Rules

The final confirmatory analysis is **blocked** if any of the following holds:

1. more than **5%** of snapshots contain leakage;
2. more than **10%** of matches are missing in a mandatory stratum;
3. the rate of invalid Laya responses exceeds **5%** without a preregistered sensitivity analysis;
4. a checkpoint or task is not fully versioned;
5. the provenance of a target or feature cannot be audited.

These thresholds can be modified only in this preregistration (before execution). Every reported aggregation publishes its denominator and invalidity rate.

---

## 8. Data Exclusion and Validity Rules

- Responses failing the JSON/schema/probability-sum/category checks are recorded as invalid with an error code (`INVALID_JSON`, `INVALID_SCHEMA`, `INVALID_PROBABILITY`, `INVALID_PROBABILITY_SUM`, `MISSING_CATEGORY`, `LEAKAGE_DETECTED`, `CONTEXT_TOO_LONG`, `SDK_ERROR`, `NETWORK_RETRY_EXHAUSTED`) and never silently repaired or renormalized.
- Invalid responses are analyzed as a missingness category and reported with rates by stratum.
- All exclusions are logged with reasons; the final report lists included/excluded/missing counts per competition and season.

---

## 9. Disclosure (OSF standard statements)

I confirm that:

1. This registration was completed **before** any final test data were collected or analyzed, and before the final test set was inspected.
2. The hypotheses, primary metrics, baseline definitions, split design, blocking thresholds, and analysis plan are fixed as described here.
3. Any deviation from this plan will be reported explicitly in the final manuscript, with the reason for the deviation and whether it was decided before or after seeing final test results.
4. Exploratory analyses not specified here will be clearly labeled as exploratory (not confirmatory) in all reports and communications.
5. The system under test (Laya) is a third-party AI decision engine evaluated as-is; the study reports no betting advice and makes no causal claims.
6. There are no conflicts of interest to declare. The author has no relationship (financial, employment, or contractual) with the vendor of the evaluated system, with any bookmaker, or with any sports-data company.
7. Funding: none — self-funded independent research; no funder had any role in the design, analysis, or reporting.
8. The code is open source (MIT); the protocol text and published documents are CC-BY 4.0. The study protocol and reference implementation were developed with the assistance of an AI system (Super Z, Z.ai) under the direction of the author, who takes full responsibility.

---

## 10. Timeline (planned)

- **Stage 1 (this registration):** 2026-09-26 (repository, protocol, code, tests published) — 2026-09-27 (OSF registration).
- **Data collection and execution:** October–December 2026 (within 3 months of registration): collector adaptation to the frozen source, integration of the production Laya SDK (version and checkpoint hashed before collection), pipeline execution over the frozen corpus.
- **Stage 2 (results):** analyses executed exactly as preregistered; report published as a stage-2 registered report (release `v1.0.0-results`); all deviations disclosed.

---

## 11. Attachments to upload with this registration

- [x] Study protocol v2.0.0 (French original, authoritative) — `PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md` (SHA-256 `d8a3c83b6169d7d8e7210ebb280e040881956816b347a9ba5f3a5e5056f4e8ea`)
- [x] English adaptation — `docs/protocol_en.md`
- [x] Frozen experiment manifest (all Annex A/B decisions valued, incl. amendments A1/A2) — `experiment_manifest.json`
- [x] Frozen corpus table (per-competition match counts, source commit, license) — `docs/frozen_corpus.json`
- [x] Power analysis worksheet (exact noncentral-t + Monte-Carlo validation + mirror of `bootstrap_difference`) — `docs/power_analysis.json`, `scripts/power_analysis.py`
- [x] Repository snapshot/commit hash of the preregistered code — recorded in the OSF registration summary and equal to the repository `main` HEAD at registration time (GitHub: steve-dev-55/laya-football-evaluation)
