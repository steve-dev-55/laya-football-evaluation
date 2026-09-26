# Reproducible Experimental Protocol

## Evaluating Laya as a Probabilistic Decision Engine Applied to Football

> **Unofficial English adaptation of `PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md` v2.0.0 — the French original is authoritative.**
> In any case of divergence between this adaptation and the French document, the French text prevails.

| | |
|---|---|
| **Version** | 2.0.0 (protocol), 0.1.0 (English adaptation) |
| **Status** | Operational protocol, to be preregistered before any analysis of the final test set |
| **Working language** | French for documentation; English recommended for canonical questions sent to the model |
| **Units of analysis** | Match and match snapshot |
| **Target** | Specialized AI agents operating through shared artifacts |
| **Licenses** | MIT (code) — CC-BY 4.0 (text) |

---

## 0. Object and Guiding Principles

### 0.1 Objective

Measure whether Laya produces, at several instants of a football match, predictive distributions that are:

1. calibrated;
2. discriminative;
3. consistent with the information available;
4. stable under formulation variants;
5. competitive against reproducible statistical baselines.

The primary targets are the final 1X2 result, the grouped final score, the total number of corners, and the total number of yellow cards.

### 0.2 Central Rule

At a cutoff `t`, no artifact transmitted to Laya, no baseline feature, and no model-selection parameter may depend on information posterior to `t` for live data, or posterior to the pre-match cutoff for historical data. The final result is used only after inference, at evaluation time.

### 0.3 What the Study Can and Cannot Conclude

The study can estimate the out-of-sample predictive quality of Laya on the selected competitions and seasons. It cannot, by itself, establish causality, betting profitability, universal superiority of Laya, or general quality of the model on other domains.

### 0.4 Non-Negotiable Principles

- Raw data are immutable and preserved before any transformation.
- Every variable carries a provenance and an availability time.
- Pipelines are idempotent: re-running an agent must neither duplicate rows nor modify validated artifacts.
- Every invalid Laya response is recorded as invalid; it is never silently repaired.
- The main analytical decisions are frozen before consulting the final test set.
- Confidence intervals are clustered by match — snapshots are never treated as independent observations.
- Baselines and Laya receive exactly the same level of information at the same cutoff.
- Conclusions always distinguish observation, statistical result, and hypothesis.

---

## 1. Research Questions and Preregistered Hypotheses

### 1.1 Primary Question

Given the information available at minute `t`, does Laya produce predictive distributions that are better calibrated and/or more discriminative than the predefined baselines for: the final 1X2 result, the grouped final score, the total number of corners, and the total number of yellow cards?

### 1.2 Secondary Questions

- Does quality improve as the match progresses?
- Does Laya react in the expected direction after a goal, a red card, a penalty, or a substitution?
- Is the distribution stable under paraphrase, field reordering, and controlled translation?
- What level of information is required to reach a given quality level?
- Are errors concentrated in particular matches, competitions, teams, or states?
- Is Laya better calibrated but less discriminative than the baselines, or the reverse?

### 1.3 Confirmatory Hypotheses

The following hypotheses must be written into the experiment manifest before evaluation of the final test set:

- **H1 — temporal progression:** 1X2 log loss decreases as the cutoff moves from pre-match to 85 minutes.
- **H2 — calibration:** Laya's calibration, measured by ECE and log loss, is better than that of the historical baseline at identical information.
- **H3 — event reaction:** after a goal, the probability of the corresponding winner increases on average, all else equal.
- **H4 — robustness:** semantically equivalent paraphrases do not strongly modify the predictive distribution.
- **H5 — counts:** for corners and cards, Laya's performance is compared separately against a historical-mean baseline and an adapted count model.

Any hypothesis not preregistered in the manifest is exploratory and must not be presented as confirmatory.

---

## 2. System Under Test: Laya

### 2.1 Mandatory Metadata

Before any request, the Laya agent records: the exact package name and installed version; the exact checkpoint hash or identifier; the variant used (`laya`, `laya-multilingual`, or other); the maximum context length; the Python version and main dependencies; the router configuration; the execution date and run identifier; and the inference parameters, including batch and any seed. Architectural characteristics announced in the documentation are not considered experimental facts until verified in the installed environment.

### 2.2 SDK Validation Before Collection

A smoke test must confirm: (1) the real import name; (2) the real signature of `Router.predict`; (3) the types accepted by `questions`; (4) the output format; (5) the behavior on an invalid question; (6) the reproducibility of two identical requests; (7) the conservation of probabilities and output keys. The boolean type must be named according to the actually installed SDK; the term `noul` from the initial protocol must not be used until confirmed by the API.

### 2.3 Nature of the Outputs

Laya is evaluated as a typed decision engine, not as a text generator. The agent must keep the raw response and produce a normalized representation only after validating the output contract. The confidence returned by Laya is a secondary output: it replaces neither a calibration measure nor a probability used directly in metrics.

---

## 3. Data Scope

### 3.1 Competitions and Period

Recommended scope: Premier League, La Liga, Serie A, Bundesliga, Ligue 1; three complete seasons, explicitly defined in `experiment_manifest.json`. The initial target of 1,000 matches is a power objective, not a quota for keeping low-quality matches. The final counts of included, excluded, and missing matches must be reported by competition and season.

### 3.2 Sources

A primary source is chosen before collection. A secondary source verifies results and events but never silently completes the primary one. Every source record contains: provider; endpoint or file; source identifier; retrieval date; HTTP status or error code; SHA-256 hash of the raw content; and known license restrictions. Possible sources: StatsBomb, API-Football, FBref, or another documented source; quality and license terms must be verified before use.

### 3.3 Inclusion Rules

Include only matches that are: finished and officially validated; played without extra time; with a final score available; with the events and statistics needed; with timestamps precise enough for the cutoffs; with uniquely resolved home/away identities.

### 3.4 Exclusion Rules

Exclude and log: stopped, postponed, replayed, or abandoned matches; matches with extra time or a shootout; inconsistencies between the final score and the events; a missing non-imputable target variable; impossible timestamps; unresolved duplicates; and post-match-only aggregates where a snapshot would require them earlier. Excluded matches must not be replaced after consulting results.

### 3.5 Counting Conventions

- Goals from open play, penalties, and own goals count for the benefiting team in the official 90-minute-plus-stoppage score.
- Shootout goals are not match goals.
- Corners are counted per team and aggregated to the total.
- Yellow cards issued to players are counted.
- A second caution to the same player counts as a second yellow only if this convention is identified and available in the source.
- Cards issued to coaches, substitutes, staff, and the bench are excluded from the primary target.
- Duplicate events must be deduplicated on a documented key, never by untraceable manual deletion.

A sensitivity analysis is required if the source cannot reliably distinguish a second yellow, a direct red card, and a bench card.

---

## 4. Data Model and Artifact Contracts

### 4.1 Recommended Tree

```text
data/
  raw/{competition}/{season}/
  canonical/{competition}/{season}/
  snapshots/{competition}/{season}/
  predictions/{run_id}/
  evaluation/{run_id}/
configs/
logs/
reports/
tests/
experiment_manifest.json
```

Raw Laya responses are preserved in `predictions/{run_id}/raw/` and referenced in the database by path and hash.

### 4.2 Minimal Tables

```sql
matches (
  match_id TEXT PRIMARY KEY,
  source_match_id TEXT NOT NULL,
  competition_id TEXT NOT NULL,
  season TEXT NOT NULL,
  date_utc TEXT NOT NULL,
  kickoff_timestamp TEXT NOT NULL,
  home_team_id TEXT NOT NULL,
  away_team_id TEXT NOT NULL,
  home_goals INTEGER NOT NULL,
  away_goals INTEGER NOT NULL,
  total_corners INTEGER,
  total_yellow_cards INTEGER,
  total_red_cards INTEGER,
  status TEXT NOT NULL,
  source_hash TEXT NOT NULL
);

match_events (
  event_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  elapsed_seconds INTEGER NOT NULL,
  period INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  team_id TEXT,
  player_id TEXT,
  detail TEXT,
  source_event_id TEXT,
  source_hash TEXT NOT NULL
);

match_statistics (
  stat_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  available_timestamp TEXT NOT NULL,
  elapsed_seconds INTEGER NOT NULL,
  team_id TEXT NOT NULL,
  shots INTEGER,
  shots_on_target INTEGER,
  corners INTEGER,
  yellow_cards INTEGER,
  red_cards INTEGER,
  possession REAL,
  xg REAL,
  source_hash TEXT NOT NULL
);

pre_match_context (
  pre_match_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  team_id TEXT NOT NULL,
  cutoff_timestamp TEXT NOT NULL,
  feature_version TEXT NOT NULL,
  form_last_5 TEXT,
  form_last_10 TEXT,
  goals_scored_avg REAL,
  goals_conceded_avg REAL,
  head_to_head TEXT,
  ranking_before REAL,
  xg_for_avg REAL,
  xg_against_avg REAL,
  injuries TEXT,
  suspensions TEXT,
  lineup TEXT,
  pre_match_odds TEXT,
  source_match_ids TEXT NOT NULL
);

match_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  cutoff_seconds INTEGER NOT NULL,
  cutoff_timestamp TEXT NOT NULL,
  snapshot_type TEXT NOT NULL,
  information_tier TEXT NOT NULL,
  state_json TEXT NOT NULL,
  state_hash TEXT NOT NULL,
  validation_status TEXT NOT NULL
);

laya_predictions (
  prediction_id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  model_version TEXT NOT NULL,
  run_id TEXT NOT NULL,
  raw_response_path TEXT NOT NULL,
  raw_response_hash TEXT NOT NULL,
  parsed_response TEXT,
  probability_1 TEXT,
  probability_x TEXT,
  probability_2 TEXT,
  expected_goals REAL,
  expected_corners REAL,
  expected_yellow_cards REAL,
  model_confidence REAL,
  latency_ms REAL,
  status TEXT NOT NULL,
  error_code TEXT
);

evaluation (
  evaluation_id TEXT PRIMARY KEY,
  prediction_id TEXT NOT NULL,
  actual_result TEXT NOT NULL,
  actual_home_goals INTEGER NOT NULL,
  actual_away_goals INTEGER NOT NULL,
  actual_total_corners INTEGER NOT NULL,
  actual_total_yellow_cards INTEGER NOT NULL,
  log_loss_1x2 REAL,
  brier_1x2 REAL,
  score_bucket_log_loss REAL,
  rps_1x2 REAL,
  mae_goals REAL,
  mae_corners REAL,
  mae_yellow_cards REAL,
  created_at TEXT NOT NULL
);
```

### 4.3 Identifiers and Idempotence

Use deterministic identifiers:

- `team_id = SHA256(competition_id + ':' + canonical_team_name)`;
- `match_id = SHA256(competition_id + ':' + season + ':' + kickoff_timestamp + ':' + home_team_id + ':' + away_team_id)`;
- `snapshot_id = match_id + ':' + cutoff_seconds + ':' + information_tier + ':' + variant_id`.

An agent must be able to re-run a step without creating a second match, snapshot, or prediction for the same `run_id`.

---

## 5. Point-in-Time Construction and Leakage Prevention

### 5.1 Reference Times

For each match, define: `T_kickoff` (official kickoff time); `T_pre_match_cutoff` (equal to kickoff unless the study explicitly includes lineups or odds available earlier); `cutoff_seconds` (elapsed playing time used by the snapshot); `cutoff_timestamp` (the real timestamp of the cutoff). Displayed minutes are not always sufficient: use `elapsed_seconds` when available and document the treatment of stoppage time.

### 5.2 Pre-Match Block

All pre-match variables of a match `M` must depend only on data whose availability date is strictly earlier than `T_pre_match_cutoff`. Compute aggregates through a temporal view:

```sql
WHERE available_timestamp < :pre_match_cutoff
  AND match_id <> :current_match_id
```

This filter must not be replaced by a whole-season filter or a final standings table. For each feature, store the `source_match_ids` used; a validation checks that each one has `available_timestamp < T_pre_match_cutoff`.

### 5.3 Live Snapshots

At cutoff `t`, include only observations available no later than the cutoff:

```sql
WHERE match_id = :match_id
  AND available_timestamp <= :cutoff_timestamp
  AND elapsed_seconds <= :cutoff_seconds
```

A statistic published only at the end of the match must never be used as a live statistic, even if it contains a `minute` column.

### 5.4 Forbidden Fields

Never include in `state_json`: the final score; final goals per team; final corners; final cards; the realized result; any event posterior to the cutoff; statistics labeled `full_time`, `final`, `total_match`, or equivalent; identifiers or texts revealing the target; the name of a result or evaluation file; or the outputs of a previous Laya prediction for the same match. The leakage test must inspect keys, values, metadata, serialized text, and referenced paths.

### 5.5 Mandatory Anti-Leakage Tests

Every snapshot must pass the following tests:

```python
def test_no_future_events(snapshot, events):
    cutoff = snapshot["cutoff_seconds"]
    future = [e for e in events
              if e["match_id"] == snapshot["match_id"]
              and e["elapsed_seconds"] > cutoff]
    assert not future

def test_no_final_fields(snapshot):
    forbidden = (
        "final_score", "final_goals", "final_corners",
        "final_yellow_cards", "actual_result", "full_time"
    )
    serialized = json.dumps(snapshot["state"], sort_keys=True).lower()
    assert not any(key in serialized for key in forbidden)

def test_pre_match_sources_before_cutoff(snapshot, contexts, matches):
    cutoff = snapshot["state"]["metadata"]["pre_match_cutoff_timestamp"]
    used_ids = set(snapshot["state"]["metadata"]["pre_match_source_match_ids"])
    for match in matches:
        if match["match_id"] in used_ids:
            assert match["available_timestamp"] < cutoff
```

Add a negative test: artificially inject a future event and check that the validator fails. The tests must run on 100% of snapshots, not only on the manually audited sample.

### 5.6 Manual Audit

Audit at least 5% of snapshots, stratified by competition, season, cutoff, and event type. The audit checks coherence between the raw source, the canonical event, and the state transmitted to Laya. Auditors record their decision and justification.

---

## 6. Snapshot Plan and Information Tiers

### 6.1 Fixed Snapshots

Create, if the match is still in progress at the corresponding instant: `pre_match`; 15 minutes; 30 minutes; 45 minutes; 60 minutes; 75 minutes; 85 minutes. The 45-minute snapshot represents the state at the end of the first period before interval events, unless a documented decision states otherwise.

### 6.2 Event-Driven Snapshots

Create a snapshot immediately after each: goal; red card; penalty awarded or taken; substitution. The event type, timestamp, and identifier are recorded in the metadata. If several events share a timestamp, create a snapshot after the documented source order plus one aggregated control version.

### 6.3 Information Tiers

For the ablation study, define before analysis:

- **Tier A — pre-match:** form, available standings, head-to-head, authorized odds, and pre-match context;
- **Tier B — minimal live:** Tier A + score, cards, corners, dismissals, and available events;
- **Tier C — full live:** Tier B + shots, shots on target, possession, and xG whenever these variables were genuinely available at the cutoff.

Tiers are different states of the same match and must not be compared as independent observations in confidence intervals.

---

## 7. State Transmitted to Laya

### 7.1 Canonical Serialization

The JSON must be deterministic: sorted keys, fixed numeric precision, missing values as `null`, no uncontrolled free text, UTF-8 encoding.

```json
{
  "metadata": {
    "competition": "Premier League",
    "season": "2023-2024",
    "home_team": "Team A",
    "away_team": "Team B",
    "cutoff_seconds": 3600,
    "cutoff_timestamp": "2024-01-15T16:00:00Z",
    "information_tier": "C"
  },
  "pre_match": {
    "home": {},
    "away": {}
  },
  "live": {
    "score": {"home": 1, "away": 0},
    "corners": {"home": 4, "away": 3},
    "yellow_cards": {"home": 1, "away": 2},
    "red_cards": {"home": 0, "away": 0},
    "shots": {"home": 8, "away": 5},
    "shots_on_target": {"home": 3, "away": 2},
    "possession": {"home": 55.0, "away": 45.0},
    "xg": {"home": 1.2, "away": 0.8}
  }
}
```

The `metadata.cutoff_timestamp` field serves to audit the snapshot; it must not indirectly encode the result, e.g., through a file name or an identifier containing a target.

### 7.2 Missing Data Handling

Never replace a missing live variable with a final statistic or a value computed from the match result. Accepted representations: `null` if the model and SDK accept it; a controlled, documented omission identical between Laya and the baselines; an `unavailable` category only if planned before collection. Missingness rates are reported by variable, source, competition, season, and cutoff.

---

## 8. Typed Tasks and Target Support

### 8.1 1X2 Result

The 1X2 is derived from the joint score distribution:

```text
P(1) = sum of P(h, a) for h > a
P(X) = sum of P(h, a) for h = a
P(2) = sum of P(h, a) for h < a
```

The real 90-minute-plus-stoppage score is used, without extra time or shootouts.

### 8.2 Grouped Score: Correcting the `other` Category

The initial grid must not be described as an exact-score distribution if it contains an `other` class. The recommended primary task is a **score bucket** distribution:

```text
0-0, 0-1, 0-2, 0-3,
1-0, 1-1, 1-2, 1-3,
2-0, 2-1, 2-2, 2-3,
3-0, 3-1, 3-2, 3-3,
other
```

Any score with at least one component above 3 is mapped to `other`. Log loss and calibration then apply to these 17 categories, not to the exact score. For higher-resolution goal analysis, add two separate marginal tasks: home goals `0`–`7` then `8+`; away goals `0`–`7` then `8+`. These marginals must not be recombined into a joint distribution without an explicitly validated method.

### 8.3 Corners

Use levels `0` to `20` plus `21+` when the `score` type accepts an ordered tail. If the SDK does not allow a tail class, use a censored target `min(total_corners, 20)` and do not present the expectation as uncensored.

### 8.4 Yellow Cards

Use levels `0` to `12` plus `13+`, with the same tail rule. The threshold may be raised before the experiment if a descriptive analysis shows an excessive tail frequency; it must never be chosen after comparing results.

### 8.5 Question Definitions

```python
QUESTIONS_V1 = {
    "score_bucket": {
        "type": "choice",
        "instructions": "What is the final score category of this football match?",
        "criteria": SCORE_BUCKET_CRITERIA,
    },
    "total_corners": {
        "type": "score",
        "instructions": "What will be the total number of corners in the match?",
        "criteria": [str(i) for i in range(21)] + ["21+"],
    },
    "total_yellow_cards": {
        "type": "score",
        "instructions": "What will be the total number of yellow cards in the match?",
        "criteria": [str(i) for i in range(13)] + ["13+"],
    },
}
```

Names, category order, and exact wording are versioned; any modification creates a new task version.

### 8.6 Response Validator

Before insertion: (1) check that the response is valid JSON; (2) check the expected keys and only the documented keys; (3) check that each probability is finite and in [0, 1]; (4) check that the sum equals 1 within `1e-6`; (5) check for missing or duplicated categories; (6) check the coherence of the expected value with the tail convention; (7) keep the raw text before any transformation. An out-of-tolerance sum produces `INVALID_PROBABILITY_SUM`. Silent renormalization is forbidden; any explicitly authorized normalization must be separated, versioned, and counted as an analysis variant.

---

## 9. Laya Agent Execution

### 9.1 Procedure

For each valid snapshot: (1) load `state_json`; (2) verify its hash and anti-leakage status; (3) serialize the state canonically; (4) run the planned question version; (5) call the router with the declared checkpoint; (6) write the raw response immediately; (7) validate, then parse; (8) derive 1X2 and counting statistics; (9) record latency, status, any error, and the response hash.

### 9.2 Determinism

Run a repetition audit on a stratified sample of at least 10% of snapshots, with `k = 5` identical requests. If the outputs are identical, one request suffices for production and the audit is retained. If they differ, use `k = 5` for all snapshots of the main protocol, or freeze and justify an aggregation rule before the test. Never average a distribution without keeping the five individual outputs. Report inter-call variance, decision-change frequency, and log-loss variation.

### 9.3 Errors and Retries

Network errors may be retried with bounded exponential backoff; a retry must never replace the original response, and every attempt is logged. Parsing, schema, or leakage errors are validity errors and must not be auto-repaired without diagnosis. Minimal error codes:

```text
OK
NETWORK_RETRY_EXHAUSTED
INVALID_JSON
INVALID_SCHEMA
INVALID_PROBABILITY
INVALID_PROBABILITY_SUM
MISSING_CATEGORY
LEAKAGE_DETECTED
CONTEXT_TOO_LONG
SDK_ERROR
```

### 9.4 Confidence

Store the confidence returned by Laya, but evaluate separately: the calibration of the probabilities; the calibration of confidence against the correctness of the most probable decision; and the relation between confidence and log loss. Strong confidence is not proof of correctness.

---

## 10. Fair Baselines

All baselines are trained or computed with data available at the same cutoff.

### 10.1 Minimal Baselines

- **Uniform:** uniform distribution over the categories; reference control.
- **Historical frequency:** observed frequency in the training window, by competition and possibly by season.
- **Current score:** keep the current score as the final score; a deliberately naive, non-probabilistic baseline, converted to a distribution with a preregistered rule if needed.
- **Count persistence:** current count + historical average of the remainder, with a precise definition of the remainder.

A baseline producing a point value must not be compared to a distribution without a documented conversion method.

### 10.2 Statistical Models

At minimum: independent or bivariate Poisson for goals; a Dixon-Coles model or equivalent where justified; Poisson or negative binomial for corners and cards; multinomial logistic regression for 1X2; an optional tabular model (e.g., gradient boosting) only with a temporal split. Hyperparameters are fixed on validation; the final test is never used to choose them.

### 10.3 Bookmaker Odds

Pre-match odds are a strong baseline only at the pre-match snapshot, unless timestamped live odds are available and integrated identically. Convert odds to implied probabilities, then remove the margin with a method defined before analysis. Never use an odds value published after the cutoff.

### 10.4 Fair Comparison

Each baseline must receive an `information_tier` feature table equivalent to the one transmitted to Laya. A baseline benefiting from variables unavailable to Laya is excluded from the main comparison and presented as auxiliary analysis.

---

## 11. Split, Validation, and Power

### 11.1 Temporal Split

No random split at the snapshot level. Recommended protocol: training on the oldest periods; validation on the immediately following period; final test on the most recent period, never consulted for model choices. If only three seasons are available, use a documented rolling-origin scheme and a final temporal holdout. Matches on the same day must stay in the same block whenever feature availability could create dependence.

### 11.2 Observation Dependence

Snapshots of a match share the same final result; event-driven observations are even more dependent. Per-snapshot metrics are descriptive; standard errors and intervals must be clustered by `match_id`.

### 11.3 Power Analysis

Before final collection, define: the primary metric per target; the minimal difference of interest; the expected exclusion rate; the number of matches required; the number of competitions and seasons; and the maximum number of confirmatory tests. If power is insufficient, report an imprecise estimate and do not conclude equivalence from a non-significant result.

### 11.4 Pre-Analysis Quality Criteria

The final test is blocked if: more than 5% of snapshots contain leakage; more than 10% of matches in a mandatory stratum are missing; the rate of invalid Laya responses exceeds 5% without a sensitivity analysis; a checkpoint or task is not fully versioned; or the provenance of a target or feature cannot be audited. These thresholds may be modified only in the preregistered manifest.

---

## 12. Evaluation Metrics

### 12.1 1X2 Classification

Compute: multiclass log loss with floor `epsilon = 1e-15`; multiclass Brier score; accuracy of the most probable class; RPS (1X2 is ordered); ECE with announced bins and method; reliability curves; and log loss by cutoff, competition, season, and tier. AUC is not a primary metric for an ordered multiclass target; if provided, it is an auxiliary one-vs-rest analysis with an explicit method.

### 12.2 Score Buckets

Compute: log loss over the 17 categories; multiclass Brier; RPS if a coherent category order is defined; accuracy of the most probable bucket; and calibration for frequent categories and for `other`. Do not call this metric "exact-score log loss".

### 12.3 Counts

For corners and cards: MAE of the expected value, only if compatible with the tail convention; RMSE; discrete log score; discrete CRPS; Poisson or negative-binomial deviance where applicable; coverage of 50%, 80%, and 95% predictive intervals; mean width of these intervals; randomized PIT for discrete variables; and tail mass in `21+` or `13+`. If a tail is censored, report the censored-target metrics separately with the interpretation limitation.

### 12.4 Calibration

For every distribution, report: ECE and bin count; maximum calibration error; reliability curves; randomized PIT histograms for counts; empirical coverage; and the Brier decomposition if implemented. ECE depends on binning: fix the method and optionally add a quantile-binning sensitivity analysis.

### 12.5 Intervals and Tests

Use a stratified bootstrap clustered by match, with at least 2,000 replications if the budget allows. To compare two models: compute the per-match difference in contributions; use a clustered bootstrap interval; report the mean difference, the 95% CI, and an effect size; and apply Holm-Bonferroni within predefined test families. A non-significant test does not prove that the models are equal.

---

## 13. Robustness and Event Reactions

### 13.1 Paraphrases

Create a small versioned set of semantically equivalent formulations with identical state content and categories. Measure: mean absolute probability variation; Jensen-Shannon distance; total variation distance; expected-value change; most-probable-class change rate; and log-loss variation. A single 1X2 decision is not enough to measure the robustness of a distribution.

### 13.2 Reordering and Format

Test separately: JSON field order; authorized field names; compact vs. indented JSON; French vs. English, only if the multilingual model is evaluated; and the presence of a fixed descriptive dictionary. Each variant must preserve semantic content and the context budget.

### 13.3 Event Reactions

For each admissible event, compare before/after snapshots within a predefined time window. Expected directions, without automatic causal interpretation: home goal — average increase of `P(1)`; away goal — average increase of `P(2)`; home red card — average decrease of `P(1)` and possible increase of `P(2)`; penalty — an effect consistent with the benefiting team if the penalty outcome is not posterior to the cutoff. Also measure reactions on corners and cards distributions, without assuming that an event must improve all objectives.

### 13.4 Near-Identical Snapshots

Identify snapshot pairs whose states differ little but whose time or triggering event differs. Look for: unjustified oscillations; class changes without new information; excessively concentrated probabilities; and incoherence between the current score and the final distribution. This analysis is descriptive and does not replace out-of-sample evaluation.

---

## 14. AI Agent Architecture

Agents do not communicate directly: they read and write versioned artifacts with a status and a hash.

### 14.1 Orchestrator Agent

Responsibilities: create `experiment_manifest.json`; validate versions and parameters; run agents in order; verify preconditions and postconditions; stop the pipeline on blocking errors; and produce a run journal.

### 14.2 Collector Agent

Inputs: manifest, authorized sources, competition parameters. Outputs: raw responses, call logs, hashes, coverage report. Rules: no transformation; bounded retries; no inference from a partial response.

### 14.3 Cleaner Agent

Inputs: immutable raw data. Outputs: canonical data, `cleaning_report.json`, motivated exclusions. Controls: identifiers, duplicates, schedules, score, events, card and corner conventions.

### 14.4 Pre-Match Agent

Inputs: canonical data anterior to each cutoff. Outputs: `pre_match_context`, the list of source matches per feature, `pre_match_validation.json`. Blocking: no feature passes if its history contains a future date or the current match.

### 14.5 Snapshot Agent

Inputs: canonical match, pre-match context, cutoff rules. Outputs: fixed and event-driven snapshots, state hashes, `snapshot_validation.json`. Blocking: all anti-leakage tests must pass before snapshot publication.

### 14.6 Laya Agent

Inputs: validated snapshots, question configuration, checkpoint. Outputs: raw responses, normalized predictions, latencies, errors, repetition audit. Blocking: an invalid response is isolated, never replaced by a modified response.

### 14.7 Baselines Agent

Inputs: the same snapshots and temporal split. Outputs: baseline distributions, trained parameters, fit metrics. Blocking: no training on the final test.

### 14.8 Evaluator Agent

Inputs: valid predictions, final targets, frozen manifest. Outputs: per-prediction contributions, aggregates, bootstrap, calibration, per-model comparison. Blocking: no aggregation without a report of the denominator and the invalidity rate.

### 14.9 Analyst Agent

Inputs: evaluation reports, manifests, logs, exclusions. Outputs: final Markdown and PDF report, limitations table, reproducible annexes. Rule: explicitly separate confirmatory results, exploratory analyses, and hypotheses.

---

## 15. Communication Contract and Logging

Every artifact contains at least:

```json
{
  "schema_version": "1.0.0",
  "experiment_id": "exp_2026_001",
  "run_id": "run_001",
  "producer": "snapshot_agent",
  "created_at": "2026-09-25T12:00:00Z",
  "input_hashes": [],
  "output_hash": "sha256:...",
  "status": "validated",
  "record_count": 0,
  "warnings": [],
  "errors": []
}
```

Mandatory logs: `logs/orchestrator.log`, `logs/collector.log`, `logs/cleaner.log`, `logs/pre_match.log`, `logs/snapshot.log`, `logs/laya.log`, `logs/baselines.log`, `logs/evaluator.log`, `logs/analyst.log`, `logs/errors.log`. Each log line includes `timestamp`, `agent`, `run_id`, `entity_id`, `action`, `status`, and a short message without personal data.

---

## 16. Execution Order and Reference Commands

Commands must be adapted to the repository, but the logical order is fixed:

```bash
python -m src.storage.database init
python -m agents.collector --config configs/experiment.yaml
python -m agents.cleaner --run-id RUN_ID
python -m agents.pre_match --run-id RUN_ID
python -m agents.snapshot --run-id RUN_ID
python -m agents.laya --run-id RUN_ID --task-version v1
python -m agents.baselines --run-id RUN_ID
python -m agents.evaluator --run-id RUN_ID
python -m agents.analyst --run-id RUN_ID
```

Before each step: verify prerequisite artifacts. After each step: write an output manifest and a status of `validated`, `warning`, or `blocked`.

---

## 17. Reproducibility

Keep: source code and commit or versioned archive; a dependency file with exact versions; the Python version; the complete experiment manifest; the seed and configuration of every model; the exact Laya version and checkpoint hash; SHA-256 hashes of raw and canonical data; the exact questions and criteria; raw Laya responses; snapshot generation scripts; metric scripts and parameters; exclusions and errors; the sample-size report; and the date and timezone of all timestamps. A reproduction must be able to restart from the raw files without calling the external API again, except for steps explicitly marked non-reproducible.

---

## 18. Limits, Ethics, and Governance

- Public sports data may be incomplete, corrected after publication, or license-restricted.
- Laya's apparent quality may reflect coverage biases of the competitions or sources.
- Live events and statistics may be published with delay; real availability must be modeled.
- Snapshots of a match are not independent observations.
- An `other` category or a censored tail limits the interpretation of the score or expectation.
- Post-event effects are not causal effects.
- The results must not be presented as betting advice or as a guarantee of outcome.
- No sensitive personal data are needed; player identifiers must be pseudonymized if retained.
- Model errors and missing data must be reported, not masked by opportunistic imputation.

---

## 19. Deliverables and Acceptance Criteria

### 19.1 Deliverables

Documented raw dataset; canonical dataset and cleaning report; SQLite or equivalent database; validated pre-match context; snapshots and anti-leakage report; raw Laya responses and normalized predictions; baseline predictions; evaluation table; metrics by snapshot, competition, and season; bootstrap and calibration curves; final Markdown and PDF report; data dictionary; manifest and changelog; reproduction instructions.

### 19.2 Acceptance Criteria

The protocol is considered executable if:

1. a complete run can be launched from a manifest;
2. all artifacts have a hash and a producer;
3. 100% of snapshots pass the anti-leakage tests;
4. all responses are classified valid or invalid with a code;
5. the denominator of every metric is published;
6. the baselines use an equivalent temporal split;
7. the intervals are clustered by match;
8. the limitations of the `other` categories and censored tails are visible in the report;
9. the final test results are not used to modify the protocol;
10. a third party can reproduce at least the primary metrics from the stored artifacts.

---

## 20. Final Report Structure

1. Executive summary; 2. Preregistered questions and hypotheses; 3. Sources, scope, and exclusions; 4. Point-in-time definition and anti-leakage controls; 5. Laya version and typed tasks; 6. Baselines and temporal split; 7. Metrics and statistical plan; 8. Overall results; 9. Results by cutoff, competition, and tier; 10. Calibration; 11. Robustness and event reactions; 12. Error analysis; 13. Confirmatory results; 14. Exploratory analyses; 15. Limitations; 16. Conclusion; 17. Reproducibility annexes.

Every results table indicates: model, target, cutoff, number of matches, number of snapshots, number of valid responses, metric, confidence interval, and bootstrap method.

---

## 21. Operational Checklist per Agent

### Collector

- [ ] source and license documented;
- [ ] calls and errors logged;
- [ ] raw responses immutable;
- [ ] hash computed;
- [ ] coverage published by competition and season.

### Cleaner

- [ ] deterministic identifiers;
- [ ] duplicates handled and justified;
- [ ] goal, corner, and card conventions applied;
- [ ] incoherences isolated;
- [ ] no result-derived feature injected into live data.

### Pre-Match

- [ ] strict cutoff recorded;
- [ ] source matches listed;
- [ ] all dates anterior to the cutoff;
- [ ] point-in-time standings and form;
- [ ] no end-of-season statistics.

### Snapshot

- [ ] fixed cutoffs created per the rule;
- [ ] admissible events included up to the cutoff;
- [ ] future events absent;
- [ ] final fields absent;
- [ ] information tiers correctly labeled;
- [ ] state hash computed.

### Laya Agent

- [ ] SDK and checkpoint versioned;
- [ ] task versioned;
- [ ] raw response saved before parsing;
- [ ] probabilities validated;
- [ ] invalidities logged;
- [ ] determinism audited;
- [ ] no silent manual correction.

### Evaluator

- [ ] final labels joined only after prediction;
- [ ] metrics adapted to censored tails;
- [ ] bootstrap clustered by match;
- [ ] multiple-testing corrections applied;
- [ ] denominators and exclusions published.

### Analyst

- [ ] confirmatory separated from exploratory;
- [ ] observations separated from hypotheses;
- [ ] uncertainty reported;
- [ ] explicit limits;
- [ ] conclusion restricted to the observed scope;
- [ ] report reproducible from the artifacts.

---

## Annex A — Minimal Manifest Example

```json
{
  "experiment_id": "laya-football-001",
  "protocol_version": "2.0.0",
  "competitions": ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"],
  "seasons": ["2021-2022", "2022-2023", "2023-2024"],
  "primary_source": "SOURCE_NAME",
  "secondary_source": "SOURCE_NAME",
  "cutoffs_seconds": [0, 900, 1800, 2700, 3600, 4500, 5100],
  "information_tiers": ["A", "B", "C"],
  "score_bucket_cap": 3,
  "corners_tail": "21+",
  "yellow_cards_tail": "13+",
  "model": {
    "package": "laya",
    "version": "PINNED_VERSION",
    "checkpoint": "PINNED_CHECKPOINT",
    "router_mode": "multilingual"
  },
  "bootstrap_replicates": 2000,
  "alpha": 0.05,
  "seed": 20260925,
  "primary_metrics": {
    "1x2": "log_loss",
    "score_bucket": "log_loss",
    "corners": "crps",
    "yellow_cards": "crps"
  }
}
```

---

## Annex B — Decisions to Freeze Before the Final Test

The following items must receive a value in the manifest; no implicit default is allowed:

- primary and secondary sources;
- seasons and competitions;
- timezone and kickoff definition;
- real availability of statistics;
- second-yellow-card convention;
- handling of same-timestamp events;
- tail thresholds;
- exact definition of tiers A, B, and C;
- wording and order of criteria;
- Laya checkpoint;
- number of repetitions;
- temporal split;
- primary metrics;
- number of bootstrap replications;
- test families for Holm-Bonferroni;
- blocking and resumption criteria;
- missing-data handling rule.

A decision taken after inspecting the final test must be marked as post hoc and excluded from confirmatory conclusions.
