# LinkedIn post — English

**Angle:** practical and rigorous — real-time probabilistic decision engines.
**Placeholders resolved (DOI assigned): post as-is.**
**Target length:** ~200 words.

---

**AI agents are being used as real-time decision engines. Who checks whether their probabilities are actually any good — while the match is live?**

I just froze the protocol of a study that does exactly that. The system under test is a typed AI decision engine (Laya): at every snapshot of a football match — pre-match, minutes 15 to 85, and immediately after every goal, red card, penalty or substitution — it must output a full probability distribution over the final result, 17 score buckets, corners and yellow cards.

Four choices make this evaluation credible:

1. **Point-in-time integrity.** Automated leakage tests on 100% of snapshots; anything not available at the cutoff never reaches the model.
2. **Fair baselines.** Poisson, Dixon–Coles, multinomial logistic regression, bookmaker odds — all trained on the same information as the AI, at the same cutoff.
3. **Preregistration.** Five hypotheses, metrics, blocking thresholds — frozen before the test set is touched (registered-report stage 1; no results yet, by design).
4. **Full reproducibility.** Nine-agent pipeline, hashed artifacts, open source (MIT / CC-BY 4.0).

If you work in sports analytics, probabilistic forecasting, or LLM evaluation, I'd genuinely value your critique of the protocol while it can still be improved.

Repo: https://github.com/steve-dev-55/laya-football-evaluation — Preregistration: https://doi.org/10.17605/OSF.IO/TPSQB

#SportsAnalytics #ProbabilisticForecasting #LLM #OpenScience

---

*Note: recount length after replacing placeholders; keep under ~1,300 visible characters if possible.*
