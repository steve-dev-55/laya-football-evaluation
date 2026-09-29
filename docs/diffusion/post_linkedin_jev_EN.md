# Post LinkedIn — English (Jev allusion variant, sourced v2)

**Angle:** Jev (TypeSafe AI) as the timely reference — Laya as the open-source, scientifically preregistered version.
**Jev source:** official TypeSafe AI announcement — https://typesafe.ai/blog/introducing-system-one-models-and-jev
**Status: ready to post as-is (no placeholders).**
**Length:** ~1,550 visible characters (LinkedIn limit 3,000).

---

Did you see the announcement? TypeSafe AI just launched **Jev**, the first "System One Model": calibrated probabilistic decisions, ~100× faster than an LLM, no text generation — so no hallucinations.

Right direction: software needs reliable probabilities, not prose.

But one question remains open: **how do you verify that a decision engine is actually calibrated?**

Meet **Laya — the open-source version of Jev, for football.**

Same philosophy as Jev: match state in → structured probability distributions out (final result, 17 score categories, corners, cards) — in real time, from kickoff to the 90th minute.

Plus one thing Jev doesn't have: **built-in scientific verifiability.**

✅ OSF preregistration (DOI: 10.17605/OSF.IO/TPSQB) — hypotheses, metrics and thresholds frozen BEFORE any testing
✅ 100% open-source code (MIT) — 9-agent pipeline, auditable line by line
✅ Automatic leakage prevention — the AI never sees information postdating its prediction (verified on 100% of snapshots)
✅ Honest baselines — Poisson, Dixon–Coles, bookmaker odds, trained on the same information, at the same moments

Jev announces "calibrated". Laya will measure it: ECE, randomized PIT, log loss, Brier, RPS — grouped bootstrap + Holm-Bonferroni, on 2,403 matches.

A closed engine asks you to trust its benchmarks.
An open engine invites you to verify them.

Code: https://github.com/steve-dev-55/laya-football-evaluation
Protocol: https://doi.org/10.17605/OSF.IO/TPSQB

#AI #Calibration #OpenSource #SportsAnalytics #OpenScience

---

*Internal note: all statements about Jev come from the public TypeSafe AI announcement (link at the top of this file). No affiliation between this project and TypeSafe AI; "the open-source version of Jev" is an analogy positioning (an open-source probabilistic decision engine), not a technical equivalence claim. Do not post any Laya performance claim: the study has no results yet (preregistration stage).*
*Reach tip: post the Jev announcement link (https://typesafe.ai/blog/introducing-system-one-models-and-jev) as the FIRST COMMENT rather than in the post, to preserve LinkedIn reach.*
