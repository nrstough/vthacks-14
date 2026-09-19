1. **Critical** — C18 does not specify how unticking updates `acct.base`. In `App.tsx`, `adopt()` resets controls and the displayed result but never replaces the base used by the solve effect. Add a reducer action for stream selection, rebuild from the original imported schedule so rechecking restores rows, and preserve current balance/buffer values. Test untick, recheck, and multiple toggles through the reducer.

2. **Critical** — C3’s two DOM modes covering ≥80% of occurrences does not establish semimonthly recurrence. A monthly bill shifted around weekends can satisfy that rule and become two projected bills per month. Require two distinct monthly phases with adequate separation and repeated evidence within months; test monthly weekend-shifted bills against semimonthly income.

3. **Critical** — Projection can count already-posted money twice. Rows dated `as_of` are accepted, projection includes `as_of`, and the opening input is “Today’s balance.” A paycheck already included in that balance can therefore be projected again. Define the balance cutoff and suppress occurrences already represented in it; distinguish posted-today income from an expected-but-unposted payday in tests.

4. **Critical** — Derived amounts exceed the proposed schema bounds for valid inputs. `unscheduled_inflow_cents: NonNegCents` cannot hold the sum of two maximum-size inflows, and daily residual medians can exceed `ScheduledTxn.amount_cents` limits. Reuse the existing derived-money types for aggregates and explicitly reject or otherwise handle oversized projected amounts before response validation. Add boundary tests proving these requests never produce 500s.

5. **Critical** — Import date validation omits protections already present in `SampleAccountRequest`. `iso()` accepts `9999-12-31`, after which horizon arithmetic overflows; the three-year lookback can also underflow near year 1. Validate arithmetic headroom and test both calendar boundaries.

6. **Critical** — Filtering and empty-history behavior are unresolved. Step 2 computes history bounds before rejecting future/old rows, and its future-row rejection reason is absent from `RejectedRow.reason`. All rows can also be rejected, leaving no valid history bounds. Filter first, define the complete reason enum and empty-result behavior, and test all-future, all-too-old, and mixed histories.

7. **Critical** — C15 sanitizes candidate details but leaves branded candidate labels intact. `candidates/generator.py::_label()` can emit “Pause Netflix for a cycle”; an imported description of `Netflix` consequently survives into the response, solve, and chat despite R1/A2. Generate brand-free import labels while preserving their uniqueness. Include ordinary recognized merchant descriptions in privacy tests; high-entropy descriptions alone miss this path.

8. **Critical** — The revised assumed-spending method still has an incompatible response contract. `assumed_method` only permits `"same_weekday_8_week_mean"`, while C11 requires a median; the proposed provenance sentence also says “average.” Update the literal, frontend types, provenance wording, documentation, and assertions together.

9. **Critical** — The plan does not preserve original row indexes explicitly through sorting and filtering. `source_row_indexes` must reference `request.rows`, whereas detection operates on sorted rows. Carry original indexes alongside rows throughout detection and residual removal, and test newest-first input containing duplicates and rejected rows; otherwise local labels can identify the wrong transactions.

10. **Critical** — The planned browser verification will target the wrong backend. `frontend/vite.config.ts` hardcodes `/api` to port 8000; starting the history backend on 8002 does not change that. Configure the history frontend’s proxy target explicitly and verify its requests reach 8002.

11. **Suggestion** — `Date.UTC` is normalization, not date validation: invalid dates such as February 30 roll into March. Specify component round-trip validation and the two-digit-year mapping, with malformed-calendar tests, rather than copying the solver’s trusted-input date conversion.

12. **Suggestion** — Lapsed-stream handling needs an explicit internal representation. C7 requires retaining their row membership while suppressing projection, but `Stream` contains no lapsed status and `project()` receives no `history_end`. Also, C7’s monthly bill stopped 40 days ago is not lapsed under the stated two-interval threshold. Define how detection passes activity status to projection and correct that fixture.

13. **Suggestion** — The new import `chatKey` arm needs an identity rule. A constant `"import"` key would preserve the previous account’s conversation when a different CSV is imported. Use a new identity for each successfully adopted import and test successive imports, including ones with identical dates and stream counts.
