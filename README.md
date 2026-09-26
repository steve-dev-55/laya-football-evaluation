# Laya Football Evaluation

**A preregistered, multi-agent evaluation protocol for AI decision engines as real-time probabilistic forecasters of football matches.**

[![CI](https://github.com/steve-dev-55/laya-football-evaluation/actions/workflows/ci.yml/badge.svg)](https://github.com/steve-dev-55/laya-football-evaluation/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs: CC-BY 4.0](https://img.shields.io/badge/Docs-CC--BY_204.0-blue.svg)](LICENSE-CC-BY-4.0)
[![Protocol](https://img.shields.io/badge/Protocol-v2.0.0-preregistered-purple.svg)](PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md)
[![Tests](https://img.shields.io/badge/tests-130%20passed-brightgreen.svg)](tests/)

> 📌 **Status — Stage 1 (preregistration).** The protocol, reference
> implementation and full test suite are published **before** running the
> experiment on real data. Results will follow in a separate release
> (`v1.0.0-results`). See [docs/publication_process.md](docs/publication_process.md).
>
> 📝 **Preregistered on OSF**: [10.17605/OSF.IO/TPSQB](https://doi.org/10.17605/OSF.IO/TPSQB)
> — frozen corpus: 2 403 matches (StatsBomb Open Data, three complete seasons,
> ten competitions) · power analysis: MDE₈₀ = 0.009 log loss · registered code
> state: commit `172b8d6`.

## What is this?

Can a **typed AI decision engine** (an LLM-based system that outputs
probability distributions rather than free text) serve as a **real-time
probabilistic forecaster** during a football match? This repository provides
a rigorous, fully preregistered answer:

- **Four targets** evaluated at **seven in-play cutoffs** (0', 15', 30',
  45', 60', 75', 85') plus event-driven snapshots (goals, red cards,
  penalties, substitutions):
  - 1X2 match result (derived from a joint score distribution)
  - Score buckets — 17 ordered categories (`0-0` … `3-3`, `other`)
  - Total corners — 22 levels (`0` … `20`, `21+`)
  - Total yellow cards — 14 levels (`0` … `12`, `13+`)
- **Three information tiers** (A: pre-match, B: minimal live, C: full live
  with xG/possession) — an ablation of what information actually drives
  predictive quality.
- **Point-in-time guarantees**: no snapshot ever contains information
  unavailable at its cutoff (100% audited, §5 of the protocol).
- **Fair baselines** receiving the exact same information: uniform,
  historical frequencies, current-score persistence, count persistence,
  independent Poisson, multinomial logistic regression.
- **Grouped inference**: stratified bootstrap by match (≥ 2 000
  replicates), Holm-Bonferroni correction across preregistered test
  families — snapshots are never treated as independent observations.

## The 9-agent architecture

Agents never talk to each other directly — they communicate exclusively
through **versioned artifacts with SHA-256 hashes**, making every step
idempotent and independently auditable:

```
            ┌─────────────────────────────────────────────┐
            │              ORCHESTRATOR                   │
            │   manifest • ordering • pre/postconditions  │
            └──────────────────────┬──────────────────────┘
                                   │
 ┌──────────┐   ┌─────────┐   ┌────────────┐   ┌───────────┐
 │ COLLECTOR│──▶│ CLEANER │──▶│ PRE-MATCH  │──▶│ SNAPSHOT  │
 └──────────┘   └─────────┘   └────────────┘   └─────┬─────┘
                                                      │
              ┌───────────┐   ┌───────────┐   ┌───────▼──────┐
              │  ANALYST  │◀──│ EVALUATOR │◀──│  LAYA +      │
              └───────────┘   └─────────▲ ┘   │  BASELINES   │
                                        └─────┴──────────────┘
```

## Quickstart

```bash
# 1. Install
pip install numpy scipy pandas scikit-learn PyYAML pytest ruff

# 2. Run the full pipeline on deterministic synthetic data (zero real data)
bash scripts/run_pipeline.sh demo_run

# 3. Inspect the output
cat reports/final_report.md        # 17-section final report (§20)
open data/laya_experiment.db       # SQLite: 7 tables, §4.2 schema

# 4. Run the test suite (130 tests: unit + leakage + e2e)
python -m pytest tests/ -q
```

> The demonstration run uses a **deterministic mock Laya client** and
> synthetic data. Executing the real study requires pinning the actual
> model/checkpoint and an authorized data source (see
> [docs/publication_process.md](docs/publication_process.md), stage 4).

## Repository layout

```
PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md   # The protocol (French, authoritative, v2.0.0)
docs/protocol_en.md                    # Complete English adaptation
docs/publication_process.md            # 5-stage publication process
docs/preregistration_osf.md            # OSF-ready preregistration document
docs/diffusion/                        # Outreach posts (FR/EN) + researcher emails
experiment_manifest.json               # All 17 frozen decisions (Annex B)
configs/experiment.yaml                # Experiment configuration
src/core/                              # IDs, canonical JSON, tasks, leakage, metrics, stats
src/storage/                           # SQLite schema (7 tables) + point-in-time queries
agents/                                # The 9 agents (§14)
tests/                                 # 130 tests incl. end-to-end + negative leakage tests
paper/                                 # 12-page LaTeX preprint (registered-report stage 1)
scripts/                               # run_pipeline.sh (§16) + synthetic data generator
```

## Scientific integrity — what makes this preregistration solid

1. **Hypotheses frozen first.** H1 (temporal progression), H2 (calibration),
   H3 (event reaction), H4 (robustness), H5 (count targets) are written in
   the manifest **before** any test-set evaluation. Anything else is
   exploratory by definition.
2. **No silent repairs.** Invalid model responses are recorded with their
   protocol error code (`INVALID_PROBABILITY_SUM`, `LEAKAGE_DETECTED`, …)
   and never renormalized or retried into validity.
3. **Blocking thresholds.** The final test is blocked if > 5% snapshots
   leak, > 10% of a mandatory stratum is missing, or > 5% responses are
   invalid without a sensitivity analysis.
4. **Everything hashed.** Raw responses, canonical states, artifacts —
   every stage output carries a SHA-256 so a third party can reproduce the
   metrics from the stored artifacts alone.

## Citations

If you use this protocol or code, please cite:

```bibtex
@software{djoumessi_mba_2026_laya,
  author = {Djoumessi Mba, Steve},
  title = {Laya as a Real-Time Probabilistic Decision Engine for Football:
           A Preregistered Multi-Agent Evaluation Protocol},
  year = {2026},
  version = {0.1.0},
  publisher = {GitHub},
  url = {https://github.com/steve-dev-55/laya-football-evaluation}
}
```

Full structured metadata: [`CITATION.cff`](CITATION.cff) (GitHub renders it
automatically under "Cite this repository").

## License

- **Code**: [MIT](LICENSE)
- **Protocol, documentation, figures, paper**: [CC-BY 4.0](LICENSE-CC-BY-4.0)

## Warning

This is a scientific study of probabilistic forecasting quality. It is
**not** betting advice and implies no guarantee of profit or outcome
(protocol §18).
