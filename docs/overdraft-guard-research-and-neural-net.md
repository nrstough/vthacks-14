# Overdraft Guard: competitive research and neural-network recommendation

Research date: September 19, 2026. Project inspected: `/Users/nathanstough/Desktop/VT Hacks`, repository `nrstough/vthacks-14`, branch `main`, HEAD `e83ca59` at the initial inspection. Backend files were actively appearing during review, so this is a snapshot, not a claim about the other session's final implementation. No project files were changed and no test suite was run.

## Recommendation

Keep the exact spending-plan optimizer. Add a neural network to estimate **ordinary spending missing from the scheduled bills**, then let the exact solver calculate a plan against the resulting dated assumptions. Add a visible stress test and action-availability checks around that plan.

The neural network has a useful job here. Replacing an exact solver with a learned decision model is a different proposal, and a much weaker fit. The useful distinction is between estimating an uncertain future and calculating the consequences of a specified future. A prediction can change the plan without invalidating the arithmetic proof; the proof remains conditional on the forecast inputs, candidate actions, locks, horizon, and objective.

My preferred hackathon route is a **bounded experiment with a pretrained time-series network**, starting with Chronos-Bolt Tiny or Mini. If Nathan specifically wants to train an original network, use a small residual-spending MLP as an explicitly experimental alternative. Do not undertake both implementations during this hackathon. Neither is assumed to outperform simple baselines until tested.

## What the project actually is today

The README and current solver documents describe a stateless prescriptive cash-flow tool: find a small set of dated skips, deferrals, downgrades, or cancellations to avoid a negative end-of-day balance and protect a chosen cushion. The frontend calls itself **Overdraft Guard**.

The implementation inspected has a React/TypeScript/Recharts interface with starting-balance and cushion sliders, three fixture presets, before/after daily balances, and action locks that trigger another solve. It first uses a local brute-force solver, then requests `/api/solve`, falling back locally on a server failure. Request cancellation and sequence guards prevent older results overwriting newer ones. The chart currently uses a fixed September 19–October 2 schedule. Presets change opening balance and cushion rather than demonstrating genuinely different histories.

The Python backend is being built, not yet a finished service verified by this review. At the later file inventory, simulation, eligibility, brute force, objective, certificates, schemas, wording, tiers, and orchestration files existed; the initial list was largely scaffolding. The README describes the intended finished arrangement and is ahead of the observed implementation. No inference about deployment readiness or passing tests should be made from its prose.

The intended optimizer minimizes, in order: days below zero, worst shortfall, failure to hold the cushion, number of actions, below-cushion exposure, pain, plan churn, deterministic ID tie-break. It distinguishes full cushion protection, clearing zero without the cushion, and an unresolved cash gap. The intended proof-status handling appropriately weakens wording if optimality is not proved.

Read sources: `README.md`, `docs/ideas.md`, `docs/features/solver.md`, current solver spec and plan review, API types, `App.tsx`, API client, fixtures, and the existing external memo. The older handoff contains superseded hosting/prize decisions; current prize strategy favors Nessie, Vultr, and a domain. Sponsor eligibility was not reverified in this research.

## Competitors: what overlaps, and what to learn

These comparisons use official product/help pages, not hands-on subscriptions. They establish advertised features, not independent performance. I found no explicit public claim of your exact minimum-action certificate in the pages reviewed; that is not proof that no competitor has similar internal optimization.

| Tool | Verified overlap | Implication for Overdraft Guard |
|---|---|---|
| **Quicken Simplifi** | Account cash-flow chart from recurring reminders, future transactions, and expected refunds. Its help page explicitly says Planned Spend items and Savings Goals are excluded from this chart. | A future-balance chart is established territory. Estimating missing everyday spending addresses a concrete input gap. [Official reference](https://support.simplifi.quicken.com/en/articles/3357429-using-projected-cash-flow). |
| **PocketSmith** | Multiple what-if scenarios let users alter income and spending and inspect projected balances. | A scenario slider alone is not distinctive. Automatically choosing dated interventions and showing their necessity is stronger. [Scenario documentation](https://www.pocketsmith.com/plan-ahead/what-if-scenarios/). |
| **PocketGuard** | Leftover subtracts expenses and goals from income, includes bills/budgets/debt obligations, and resets monthly. | Your useful contrast is timing within the month: a positive monthly remainder can coexist with a bad day before payroll. [Leftover documentation](https://pocketguard.com/help/leftover/). |
| **YNAB** | Targets, scheduled transactions, and Auto-Assign prioritize funding categories using dates and funding needs. | Do not call competing budgets merely passive trackers. Your narrower claim is selection among explicit dated changes to resolve a cash deficit. [Underfunded logic](https://support.ynab.com/en_us/underfunded-a-guide-BJwPhQO09). |
| **Rocket Money** | Identifies subscriptions, offers cancellation assistance, and negotiates some bills. | “Cancel unused subscriptions” is an existing product. Your advantage must be which actions matter before the deadline and how long they take to become effective. [Subscriptions](https://www.rocketmoney.com/feature/manage-subscriptions), [negotiation process](https://help.rocketmoney.com/en/articles/9744564-how-to-submit-a-bill-negotiation). |
| **Cleo Autopilot** | Advertises personalized daily guidance, safe-to-spend figures, forecasting of expenses and income timing, adaptive plans, and financial actions. | This is the closest strategic competitor. Do not claim originality simply for being proactive, AI-powered, or recommending actions. Differentiate with transparent alternatives and checkable conditional certificates. [Official launch description](https://web.meetcleo.com/blog/introducing-autopilot). |

An earlier research precedent is **Financial Forecasting and Analysis for Low-Wage Workers** (2018), developed with Neighborhood Trust/WageGoal. It combines historical averaging and regularized regression with recurring-transaction heuristics. It is directly relevant evidence that this population's cash-flow forecasting needs are established—and a reason to include strong simple baselines. [Paper](https://arxiv.org/abs/1806.05362).

Position the product as: **“A short-term cash-flow repair plan you can inspect and revise: which changes to make, by when, and what breaks if you decline one.”** A future balance chart, subscription list, or conversational wrapper cannot carry the differentiation by itself.

## What I would add, in priority order

### 1. Make the proposed actions credible

The fixtures currently assume specific amounts and dates for cancelling a gym, downgrading Spotify, reducing a card payment, postponing gas, and cancelling an Amazon order. These are useful synthetic demonstrations, but a historical bank transaction does not establish that a subscription can be cancelled before its next charge or that a payment can be reduced by a particular amount.

Add an action status such as **confirmed**, **user assumption**, or **needs confirmation**, with a deadline and source. Only count savings as confirmed when their availability is confirmed. In demo mode, label synthetic cancellation terms explicitly. Preserve essential spending via user-controlled protection rather than inferring essentials solely from merchant identity.

Show deferrals as obligations that return later, with any known costs, not as money permanently saved. A near-payday repair should also disclose whether it merely moves the shortfall just beyond the horizon. A short post-payday preview would reveal that tradeoff. Financial-term accuracy matters here more than another animation.

Scope estimate: a basic provenance/status display can be small; implementing realistic contracts, minimum-payment terms, or cancellation automation is not. This recommendation does not authorize executing any financial action.

### 2. Show how fragile the plan is

Start with a deterministic stress grid: payroll delayed, extra spending, and a lower paycheck. Evaluate the **same chosen plan** against each scenario, then offer a separate re-plan operation. Re-optimizing silently under each perturbation answers a different question: whether some replacement plan exists, rather than whether the one already shown survives.

A useful line: “This plan tolerates another $24 of spending before payday. A two-day paycheck delay breaks it on Tuesday.” Numbers must be calculated, never scripted. Separate single shocks from combined shocks. Extend the simulation horizon when payroll is delayed past its current end. If a claim refers to worst-case timing, explicitly test or conservatively assign the extra spend date.

Call this a stress test or scenario range, not a confidence interval. A finite grid establishes results only for the tested scenarios unless monotonicity or bounds are proved. Existing `docs/ideas.md` already proposes this feature; it is a strong direction, not a newly discovered idea.

### 3. Add a neural estimate of unscheduled spending

Today the sample schedule knows the exact date and amount of future groceries, gas, and DoorDash orders. Real history does not give that knowledge. Model ordinary future outflows that are **not already represented by confirmed bills or planned purchases**.

User experience: two small controls, “Scheduled only” and “Include typical spending.” When enabled, label forecast contributions separately. The plan may change because there is now a realistic allowance for ordinary spending. Keep verified bills and confirmed income deterministic initially. Expand into uncertain payroll later only if there is time and usable history.

Avoid double-counting. The residual target must exclude any charge already represented elsewhere, including internal transfers and credit-card accounting flows. Do not train directly on total balances if the same confirmed deposits and bills will then be added a second time. Forecasting cannot authorize actions or establish which merchant terms apply.

### 4. Make rejection explain itself

Locks already exist. Improve their feedback: “Keeping this membership means one additional change” or “With these protected expenses, $X is still needed by date Y.” An alternative is a pair of plans: fewest actions versus lower disruption, with the tradeoff visible.

This is more useful than quietly assigning a pain score. In the current eight-part objective, pain is sixth, so a learned pain model may seldom affect the chosen plan. Changing its priority would change the product's “fewest” promise and requires an explicit product decision.

### 5. Add a short evidence view

Show schedule provenance, solver proof status, and a backtest of the forecast versus a simple baseline. Use distinct sample histories: fixed payroll, variable payroll, and an unexpected bill. The current presets mostly vary cash available. A small honest evaluation panel is more distinctive than additional broad budgeting features.

## Neural-network design: a bounded proposal

### Recommended first experiment: pretrained residual forecasting

Chronos-Bolt is a pretrained neural time-series family with direct quantile forecasts. The official model listing includes Tiny (9M parameters) and Mini (21M); the model card documents CPU and Apple Silicon inference options. That makes it a plausible local candidate, not a measured latency guarantee on this laptop or the intended VM. Its general benchmarks do not establish accuracy on personal banking data. [Official model card](https://huggingface.co/amazon/chronos-bolt-small).

Use the last 8–12 weeks of daily residual outflows if available, including zero-spend days. Keep “missing data” distinct from zero. Forecast 7–14 daily values. Start with the median as an explicitly estimated schedule; use a high-spend curve for a separately labeled stress scenario. Inference should run when history changes, not on every balance-slider movement. Cache model weights locally and preserve a deterministic fallback.

A pretrained neural model satisfies “incorporate a neural net,” but it does not justify “we trained our own financial model.” It also need not use Gemini or qualify for its sponsor track. Current Chronos has newer models with covariates, but avoid a model tournament during the event. The smaller Bolt option is a scope choice, not a claim it is the best model. [Current family](https://github.com/amazon-science/chronos-forecasting).

Keep the current Python solver environment stable. Test forecasting dependencies in an isolated environment before touching the service; compatibility with the project's Python 3.14 environment was not checked in this review. Exported forecasts can support an offline demo, but the UI must label precomputed results accurately.

### If the goal is to train your own network

Use a small MLP first: lagged daily residual amounts, recent weekly totals, weekday, and days since confirmed payroll → next 7–14 residual amounts or quantiles. A two-layer 64/32-unit network is a reasonable experimental starting point, not an established optimum. A small GRU is a later alternative if the MLP misses sequence structure; an RL policy or new transformer is unnecessary for the initial experiment.

Train on windows from multiple independent account histories. Windows from one three-month account do not become thousands of independent people merely because they overlap. Synthetic histories may support a demonstrator with varied pay cycles, sparse purchases, bursts, missing observations, and regime changes. Hold out entire generated accounts and generator regimes. Report the result as synthetic performance; no claim of real-world financial reliability follows from it.

The [CTU Financial dataset](https://relational.fel.cvut.cz/dataset/Financial) is a real historical relational dataset with transactions, originally documented for loan-outcome prediction. It may support a secondary forecasting experiment after verifying its schema and permitted use. Its age, geography, and original task make it a poor stand-in for contemporary US student behavior. Public availability alone does not settle license or redistribution conditions. No dataset was downloaded or validated during this review, and the user's private bank export was not opened.

### Architecture boundary

`history → cleaning and confirmed recurring schedule → residual forecaster → dated forecast rows → exact optimizer → independent balance replay → plan and stress tests`

Keep forecast metadata separate from the strict existing `/api/solve` request unless the contract is intentionally revised. An upstream adapter can produce ordinary dated rows while an outer response carries model version, forecast provenance, and uncertainty labels. Predictions are fixed inputs for each solve; converting them into integer cents makes arithmetic exact, not predictions certain.

The conceptual approach is established in predict-then-optimize research. That supports separating roles and measuring downstream decision quality; it does not certify this proposed architecture or imply that the hackathon needs end-to-end differentiable optimization. [Elmachtoub and Grigas](https://arxiv.org/abs/1710.08005).

## Evaluation: when is the neural layer worth keeping?

Reserve a two-hour feasibility spike after core integration is stable; this is a proposed timebox, not an estimate guaranteeing completion.

1. Establish a recent-average baseline and a weekday/seasonal baseline on the same cleaned history. Include a simple regularized model if training your own network.
2. Use chronological cutoffs: inputs stop at the forecast origin, and no future transactions or later-corrected recurrence labels leak into features. Split people/accounts as well as time when assessing cross-user generalization.
3. Measure 7/14-day cumulative outflow error, daily MAE, underprediction, and quantile loss where applicable. Do not rely on percentage errors when actual spending is zero.
4. Evaluate resulting plans against held-out realized outflows: remaining shortfall days/depth and avoidable extra interventions. This replay is a simulation of the defined action effects, not proof of how real users would respond to interventions.
5. Test sensitivity to short histories, many zero days, irregular payroll, and missing data. Show whether the network actually changes a recommendation, not just its forecast curve.
6. Keep it if it adds demonstrable value on the selected task without a material increase in false reassurance or demo fragility. If it loses, retain the result as a clearly marked experiment and use the better baseline operationally.

Do not label pointwise daily 90th-percentile predictions a “90% chance of no overdraft.” Whole-horizon coverage depends on joint errors and needs its own calibration/evaluation. Likewise, a neural forecast's uncertainty cannot become a guarantee merely because CP-SAT solves its input exactly.

## What I would leave out this weekend

An RL spending-policy agent, a learned replacement for the exact solver, automated cancellations, a social product, a database solely to justify a prize, and a broad conversational interface. Neural estimation already adds a meaningful research burden. Prioritize one visible integration over several superficial ones.

A learned action-preference model is plausible later, but there are no established real override/acceptance labels in the current project and its position in the objective limits its influence. Merchant normalization is a useful alternate neural task if history quality blocks forecasting, but a pretrained text model alone would be less distinctive than addressing unscheduled spending.

## Proposed demo narrative

1. Open a clearly labeled Nessie sample account and reveal the pre-payday low point.
2. Enable estimated ordinary spending; show why a calendar-only view was optimistic.
3. Generate the dated repair plan and inspect the effect of removing one change.
4. Protect one expense; show the replacement plan or explicit remaining gap.
5. Delay payroll two days; expose the original plan's fragility and re-plan deliberately.
6. Show a compact baseline comparison and state exactly what is simulated, predicted, and proved.

The resulting pitch is stronger than “we use AI for budgeting”: the network estimates a missing part of the future, the solver chooses among credible actions, and the interface makes the assumptions and consequences inspectable.
