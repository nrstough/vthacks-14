# Ideas

Historical idea log. The newer [product and training plan](vthacks-product-and-training-plan.md) records Nathan's expanded direction: automatic history-based setup, residual-spending forecasting, natural-language purchase questions through Gemini, and calculated alternatives. The isolated [neural pilot](vthacks-training-pilot.md) has run; the product integrations remain proposed. Earlier gates below are historical and do not imply those features already exist.

---

## 1. Deterministic core with error bars, plus an optional agent layer

**Recorded:** Sat Sept 19, 2026. **Status:** idea only, not scheduled.

The product stays a deterministic optimizer. Two additions sit on top of it,
in this order, and only if the core is deployed and polished first.

### Part A — error bars on a deterministic answer

The solver is exact and reproducible: integer cents, single worker, fixed
seed, same input gives the same plan. That is a strength and it should stay.
What it does not currently say is **how much the world can move before the
plan stops working.**

The inputs are the uncertain part, not the arithmetic:

| Source of drift | Rough size |
|---|---|
| Payday lands late | 1 to 2 business days |
| Pay amount varies with hours worked | a few percent, hourly work |
| Recurring charge amount drifts | banded at 1% today |
| Recurring detection misses or over-matches | threshold effects at WRatio 88, 3 occurrences |
| Unplanned spending before payday | unbounded, the real one |

**What it would look like.** Keep the headline verdict exactly as it is. Add
one secondary line: *"This plan still clears if your paycheck is two days
late, or if you spend up to $38 more than planned. Both at once and it does
not."* That is a robustness statement, not a probability, and it is the thing
a person actually wants to know.

**How to compute it.** Prefer a deterministic stress grid over Monte Carlo:
re-verify the chosen plan across a small cross product, for example payday
late by 0, 1 or 2 days, pay amount at 100%, 95% or 90%, and unplanned spend
of $0, $25 or $50. Report the breaking point, not a distribution. A grid is
reproducible, explainable in one sentence to a judge, and cheap. A stochastic
model would be more impressive on paper and harder to defend in four minutes.

**Chart treatment.** A shaded band around the with-plan line rather than a
second line, so it reads as tolerance rather than as a competing forecast.

**What would kill it.** If the band makes the headline hedge. The certificate
must stay crisp and conditional, "sufficient under the schedule shown". Error
bars answer a different question and belong below the fold, never in the
verdict sentence.

### Part B — an AI agent at the edges

The frozen design rule holds: **the model never participates in the
feasibility decision.** It cannot change the arithmetic, the tier, or the
certificate. Roles worth considering, cheapest and safest first:

1. **Plain-English explanation** of the plan and the certificate. Proposed for
   the Gemini API track. There is no separate Gen AI track at this event. Lowest risk, lowest originality.
2. **Merchant normalization**, turning messy descriptors into human names,
   with the existing regex and fuzzy-match path as the fallback when the
   model is unavailable.
3. **Candidate generation.** The highest-value use. The candidate list is
   hand-authored today: what moves exist for a given transaction, what each
   frees, how much it hurts. An agent proposing candidates feeds the solver
   rather than replacing it, and every proposal is still priced and selected
   by CP-SAT under the same lexicographic objective.
4. **A cancellation agent** that executes a cancellation end to end. This is
   the GoDaddy ANS stretch already noted in the plan.

**The property to state out loud to judges.** The agent can only widen or
narrow the set of options. The optimizer decides. If the agent is down, the
product still works and still proves its answer. That is the opposite of the
usual hackathon LLM wrapper and it is the more defensible story.

**What would kill it.** Any version where the model's output reaches the
verdict without passing through the solver. Also anything that makes the
demo depend on a network call that can fail on venue wifi during judging.

### Gate

Original gate (superseded by the current product-direction discussion): neither part starts before the Sat 18:30 check of a working deployed demo.
Error bars come before the agent: they strengthen the existing claim, while
the agent adds a new surface and a new failure mode. If only one fits, do
error bars.
