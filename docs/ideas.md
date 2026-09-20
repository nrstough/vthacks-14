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

---

## 2. A world model for the predictor, instead of a bigger regressor

**Recorded:** Sun Sept 20, 2026. **Status:** idea only, not scheduled. Raised
by Nathan: the predictor may want a world model — LeCun's JEPA line — rather
than a plain supervised network.

### The idea

Every network scored in the [forecast evaluation](reports/2026-09-20_forecast-evaluation.md)
is a direct regressor: 56 days of history in, a number of dollars out, trained
on the error of that number. A JEPA-style model is trained differently. It
encodes the past into a latent state, predicts the *next latent state* rather
than the next dollars, and is trained by matching its prediction to an encoder's
own view of the future. Nothing forces it to reconstruct the unpredictable part
of the signal, which is the stated motivation: the specific $43 charge on
Thursday is noise, the fact that the account is in a "rent week, groceries
already done" regime is not.

For this product the appealing version is: learn a latent state of the person's
spending regime, predict how that state evolves, and read the forecast off the
state — with a small decoder — instead of regressing the fortnight's total
directly.

### What the evidence says about whether it would help

The evaluation's round-three result is the thing to argue with, and it is not a
statement about model capacity:

> No model beats the curve. They land on it. Every one of them buys a
> safety/nuisance tradeoff that a single percentile already offers.

Four networks, three sizes, two architectures, nine anchored checkpoints — all
of them landed on the same unseen/nuisance tradeoff curve that moving the
baseline percentile reaches for free. That is the signature of a problem where
the conditional mean is nearly flat and the uncertainty, not the point estimate,
carries the information. A better representation learner does not obviously move
a curve like that; it changes how you get a point estimate, and the point
estimate was never the binding constraint.

Two further facts make a JEPA run expensive to justify tonight:

- **Data.** JEPA's whole premise is large-scale self-supervised pretraining. The
  real-account evaluation has one consented export, 1,060 rows, and 692 heavily
  overlapping windows. The report already says the modern multi-account checking
  dataset this would need "does not publicly exist". A world model trained on
  the synthetic corpus would inherit exactly the profile-reference problem that
  produced a 13% spread on the direct models.
- **Provenance.** The one architectural change that did work — anchoring the
  model on the person's own weekday baseline and learning only the correction —
  worked because it put the person's level into the architecture, not into the
  training set. That is the cheap version of the same insight, and it still lost
  to the baseline on a real account.

### The version worth keeping

There is a reframing here that survives the objection, and it is not the
forecasting one. **The solver already is a world model** — an explicit,
auditable one. It has state (balances, dates, scheduled charges), dynamics
(what each candidate move does to that state), and it plans against them. The
JEPA critique of model-free prediction is a critique of the thing we do not do.
If the idea gets written up for a judge, that is the honest framing: the part
of the system that reasons about the future is deterministic and provable, and
the learned part is confined to a scalar it cannot hide inside.

The genuinely new thing a latent world model could add is **regime detection**
rather than a dollar forecast: this fortnight does not look like the last eight,
so the assumption on screen is less trustworthy than usual. That output feeds
the existing tolerance story (idea 1, Part A) rather than the verdict, needs no
dollar-level accuracy to be useful, and can be evaluated honestly on the data
that exists — does the flag fire on the 18% of fortnights that overspend at p80?

### The extension: a forecaster *inside* the world model, not beside it

The objection above is to a swapped-in encoder. It is not an objection to this,
which is a different proposal and the stronger one.

Today the forecast is **exogenous and flat**. `same_weekday_8_week_p60` produces
one number per day, before the solve starts, and nothing the solver decides
changes it. The solver's own dynamics are explicit and hand-written; the
forecast is a constant poured into them. A better regressor — JEPA-encoded or
not — still hands over a constant before the solve begins.

The extension is a learned **transition model over account state** that rolls
forward a day at a time and is conditioned on the plan being evaluated. Defer
a charge, move a due date, skip a subscription: those plausibly change what the
person spends next week, and right now nothing in the system can express that.
A rollout model does not produce a number, it produces a *response*.

That is a capability gap rather than an accuracy gap, which matters, because
accuracy is where the last three rounds of evaluation went to die. This one can
be argued on structure instead of on a benchmark.

Three things it would buy:

1. **A plan-conditional forecast.** The only version of "learned forecasting"
   that the percentile dial cannot replicate, because the dial has no way to
   know what plan it is being asked about.
2. **Tolerance for free.** Idea 1 Part A proposes a deterministic stress grid.
   Rollouts of a transition model are that grid, learned instead of enumerated
   — and the reason to prefer the grid was explainability, so this has to earn
   its way past a thing that already works.
3. **Regime state as a by-product**, which is the output of section "The version
   worth keeping" above, obtained without training a second model for it.

**What it costs, and this is the part to settle before any model is trained.**
Make the forecast depend on the plan and the solve stops being a solve. It
becomes a fixed point: solve against a forecast, re-forecast under the chosen
plan, re-solve, repeat until stable. CP-SAT proves optimality against a fixed
instance. It cannot prove optimality of a fixed point it never saw. Everything
downstream of proof status — the tier badge, the word "proven", the
certificate's wording — is decided by how that resolves. Either the iteration
provably converges and the certificate is honest about what it is optimal *for*,
or minimality is no longer claimed. Per the frozen rule, minimality is claimed
only when proven, so this is a design decision, not an implementation detail.

The second cost is subtler and is the one that would actually bite. The model
still never sets the verdict — but a plan-conditional forecast reacts to the
solver's choices, so a model that under-predicts spending more after a deferral
would make deferrals look systematically cheap. Direction of error has to be
audited **per move type**, not in aggregate. Aggregate calibration hides exactly
the bias that would matter.

**The first step needs no model at all.** The whole extension rests on one
empirical claim: that spending after a plan intervention differs from spending
without one. That is testable on the data already in hand — label the windows in
the consented export by whether a bill was deferred or a large charge moved, and
measure whether the following fortnight's residual spending differs beyond
noise. If it does not, the plan-conditional term is zero, the extension collapses
back to the flat assumption, and no world model is warranted. If it does, the
size of that difference is the ceiling on what any of this can win — and it is
worth knowing that number before committing a night to the architecture.

### What would kill it

- Any version whose output reaches the feasibility decision. The frozen rule
  holds: the model never participates in the verdict.
- Reporting a win from the research corpus. Two recipes have now beaten their
  own baseline there and neither survived contact with a real account. Nothing
  promotes on corpus numbers again.
- Scoring it on MAE. If a world model is proposed, it is scored on the
  unseen/nuisance curve against a per-person percentile dial, or it is not
  scored.
- A plan-conditional forecast shipped before the proof-status question is
  answered. A fixed point the certificate still calls proven is the one failure
  this product cannot absorb.

### Gate

Nothing starts here before the core is deployed and polished, and not at all
during the event: this is a research-lane idea with a data prerequisite the
research lane does not currently have. The regime-detection variant is the only
part that could be prototyped against existing data, and it comes after error
bars, not before.
