# Preregistration — OSF

> **Document ready to paste into an OSF preregistration (template: "Standard Pre-Data Collection Registration" or "Preregistration Challenge" adapted).**
> Fields to be filled before submission are marked **[TODO]**. Once the registration is frozen, this document must not be modified anymore; any change after the final test has been consulted must be disclosed as a post hoc deviation.

---

## 1. Study Information

- **Title:** Laya as a Real-Time Probabilistic Decision Engine for Football: A Preregistered Multi-Agent Evaluation Protocol
- **Registration type:** Preregistered protocol — no data have been collected and no final test results have been inspected at the time of registration.
- **Authors:** Steve Djoumessi Mba — Independent Researcher (no institutional affiliation at time of registration)
- **Affiliation(s):** Independent Researcher
- **Email for correspondence:** 138932932+steve-dev-55@users.noreply.github.com
  (GitHub no-reply address preserving author privacy; replace with a
  personal address on the OSF form if preferred)
- **Date of registration:** 2026-09-26
- **Version of the study protocol:** 2.0.0 (French original authoritative; English adaptation available in the repository)
- **Persistent identifiers:**
  - Repository (code, MIT): https://github.com/steve-dev-55/laya-football-evaluation
  - This preregistration: [OSF DOI — assigned on registration]
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

- **Competitions:** Premier League, La Liga, Serie A, Bundesliga, Ligue 1 (five; frozen).
- **Seasons:** three complete seasons, explicitly listed in the experiment manifest. [TODO: list exact season labels after source selection]
- **Primary/secondary sources:** [TODO: name sources and document licenses before collection]
- **Target sample size:** ~1,000 included matches (power objective, not a quota). The power analysis (primary metric per target, minimal difference of interest, expected exclusion rate, maximum number of confirmatory tests) is completed and frozen in the manifest before the final collection. [TODO: attach power analysis numbers]
- **Inclusion:** finished and officially validated matches; no extra time; final score, events, and statistics available; timestamps precise enough for cutoffs; resolved team identities.
- **Exclusion (logged):** stopped/postponed/replayed/abandoned matches; extra time or shootouts; score–event inconsistencies; missing non-imputable targets; impossible timestamps; unresolved duplicates; post-match-only aggregates where live snapshots are required. Excluded matches are never replaced after consulting results.
- **Split:** strictly temporal — training on the oldest periods, validation on the next period, final test on the most recent period (never used for any model choice). With only three seasons: documented rolling-origin scheme + final temporal holdout. Same-day matches stay in the same block.

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
- **Multiplicity:** Holm–Bonferroni within preregistered families of tests. [TODO: freeze the exact family structure in the manifest]
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
6. There are no conflicts of interest to declare. [TODO: confirm or amend]
7. Funding: [TODO: none / details].
8. The code is open source (MIT); the protocol text and published documents are CC-BY 4.0. The study protocol and reference implementation were developed with the assistance of an AI system (Super Z, Z.ai) under the direction of the author, who takes full responsibility.

---

## 10. Timeline (planned)

- **Stage 1 (this registration):** protocol frozen, code released, preregistration + repository published. [TODO: date]
- **Data collection and execution:** after registration. [TODO: window]
- **Stage 2 (results):** analyses executed exactly as preregistered; report published as a stage-2 registered report; deviations disclosed. [TODO]

---

## 11. Attachments to upload with this registration

- [ ] Study protocol v2.0.0 (French original, authoritative) — `PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md`
- [ ] English adaptation — `docs/protocol_en.md`
- [ ] Frozen experiment manifest (with all Annex B decisions valued) — [TODO]
- [ ] Power analysis worksheet — [TODO]
- [ ] Repository snapshot/commit hash of the preregistered code — [TODO: commit SHA]
