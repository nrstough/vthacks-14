1. **Critical** — Step 6.1’s oracle import is one directory short. From `backend/tests/oracle/dump.ts`, `../../../frontend/...` resolves to `backend/frontend/...`. Use `../../../../frontend/src/solver/mockSolver.ts`.

2. **Critical** — Step 4.2’s `irredundant = all(load_bearing)` returns true for an empty plan. The oracle explicitly requires `perItem.length > 0`. Use `bool(per_item) and all(...)` and test empty plans at all three tiers.

3. **Critical** — Porting the oracle’s certificate sentence unchanged violates R10. Its empty-plan branch always says “No changes needed. The schedule already clears,” including when all candidates are locked out and a deficit remains. Add a tier-3 empty-plan certificate branch and test the entire response for contradictory claims.

4. **Critical** — Step 4.3’s FEASIBLE wording adjustment leaves tier-3 claims such as “No combination … closes the gap” and “This is the best partial plan.” An unproven incumbent does not establish either claim. Make those branches conditional on proof status and test FEASIBLE tier-3 responses, including zero selected changes.

5. **Critical** — Step 7 does not enforce the stated six-second total budget. The minimum stage allocation can exceed remaining time, and stage 8 can perform up to 60 additional solves without a specified budget update. Use one monotonic deadline across all solves, cap allocations by remaining time, and return the incumbent as FEASIBLE when exhausted.

6. **Critical** — Step 6.4 says locks are drawn “disjoint from candidate ids,” which generates invalid requests under Step 1. Generate `locks.in` and `locks.out` as mutually disjoint subsets of candidate ids; reserve unknown lock ids for validation tests.

7. **Critical** — Step 6.5’s unconditional prose-containment checks do not match the oracle’s branches. Empty plans have no `worst_item`; cushion-only certificates contain neither money nor a date; non-irredundant tier-3 certificates need not contain the marginal amount. Make assertions branch-specific and explicitly cover these cases.

8. **Suggestion** — Step 8e must call the real `CpSolver.solve` before overriding its returned status to FEASIBLE. Simply returning FEASIBLE leaves no solution for subsequent `solver.value()` calls. Also test stage-8 UNKNOWN separately to verify incumbent preservation and proof-status downgrading.

9. **Suggestion** — The missing-OR-Tools test can depend on test order: setting `sys.modules["ortools"] = None` does not disable an already imported `engine_cpsat` or its cached dependencies. Exercise import failure in a fresh subprocess or introduce a narrowly scoped engine-loading seam.

10. **Suggestion** — Step 5.3 derives planted expected plans from the brute engine being tested. Establish expected outcomes independently, with hand-calculated balances and objective comparisons, especially for the per-level counterfactuals. Otherwise shared mistakes can pass both fixture checks and CP-SAT parity.
