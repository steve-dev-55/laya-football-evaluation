# X (Twitter) thread — English

**Angle:** practical — AI agents as real-time probabilistic decision engines.
**Placeholders resolved (DOI assigned): post as-is.**
**Post as a reply-chain thread (7 tweets).**

---

**Tweet 1/7 (hook)**

Can an AI agent be trusted as a LIVE probability engine — not a one-shot quiz answerer?

We just froze a preregistered protocol to find out.

17 score categories. 7 cutoffs per match. 100% of snapshots leakage-tested.

The testbed is football. The question is general. 🧵

---

**Tweet 2/7 (the gap)**

LLM benchmarks measure static accuracy. But a real-time decision engine must do something harder: emit a full probability distribution at every moment of a live process — and stay calibrated as information arrives.

Almost nothing out there evaluates that. So we built it.

---

**Tweet 3/7 (the design)**

Every match is sampled at 7 fixed cutoffs (pre-match, 15', 30', 45', 60', 75', 85') AND immediately after every goal, red card, penalty and substitution.

Three information tiers: A = pre-match only, B = +score/events, C = +shots, possession, xG.

Same match, growing information. 📈

---

**Tweet 4/7 (anti-leakage)**

The hardest enemy of live evaluation is post-hoc contamination.

Our central rule: at cutoff t, the model sees NOTHING that wasn't available at t. Enforced by automated tests on 100% of snapshots + a negative injection test + manual audit on ≥5%.

No exceptions. Fail = pipeline blocked.

---

**Tweet 5/7 (fair baselines)**

"Is the AI good?" only means something versus fair baselines.

Every baseline gets the SAME information at the SAME cutoff: uniform, historical frequency, Poisson, Dixon-Coles, multinomial logit, bookmaker odds.

Strict temporal split. Match-clustered bootstrap (≥2,000 reps). Holm-Bonferroni.

---

**Tweet 6/7 (preregistration)**

5 hypotheses are preregistered (H1–H5): temporal progression, calibration, event reaction, paraphrase robustness, count targets.

No results yet — on purpose. Protocol + code are frozen BEFORE the test set is touched. Registered-report stage 1.

That's the point.

---

**Tweet 7/7 (open + CTA)**

Code: MIT. Text: CC-BY 4.0. Nine-agent pipeline, hashed artifacts, SQLite, fully re-runnable.

Repo: https://github.com/steve-dev-55/laya-football-evaluation
Preregistration: https://doi.org/10.17605/OSF.IO/TPSQB

Sports-analytics & forecasting researchers: poke holes in the protocol now — that's the best moment to.

#SportsAnalytics #LLM #OpenScience #Forecasting #Calibration

---

*Character-count note: each tweet fits the 280-char limit (verified after DOI replacement — use https://osf.io/tpsqb, the short form, if needed).*
