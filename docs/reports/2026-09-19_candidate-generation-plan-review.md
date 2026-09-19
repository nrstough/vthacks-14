1. **Critical — Brandless entries would prevent startup.** Step 2b requires every non-protected lexicon entry to have a display name, while step 3 explicitly assigns `display=None` to entries such as `PIZZA`, `SALON`, and `TST`. The import-time invariant would reject the intended table. Allow brandless entries when their policy has an appropriate fallback template, and update AC6 accordingly.

2. **Critical — The truncation metadata assertions are incorrect.** One grocery row with two alternatives and `limit=1` produces `truncated=True` while every considered target remains offered, contradicting the strict-subset assertion. Two unknown discretionary rows capped to one leave the omitted row in `unrecognised`, contradicting `U ⊆ P ∪ O`. Define whether `unrecognised` includes omitted rows, reconcile the documentation, and test both cases explicitly.

3. **Critical — The maximum-size roundtrip fixture exceeds the opening-balance limit.** Steps 6 and 10 combine a trough-derived opening balance with 2,000 charges of `-CENTS_ABS`. That produces an opening near `2 × 10^14`, but `SolveRequest` allows only `10^11`. Supply an explicit valid opening for this fixture or bound the helper’s result.

4. **Critical — Oracle comparison bypasses an established exception.** Step 10 proposes comparing responses using `_normalise`, which only removes timing and engine metadata. The backend intentionally differs from the oracle for tier-3 empty-plan certificate wording. Reuse [assert_agrees](</Users/nathanstough/Desktop/VT Hacks/backend/tests/test_parity.py:55>) and include an explicit generated case exercising that exception.

5. **Critical — The normalization test contradicts the implementation.** Step 7 expects identical tokens for `KROGER #382`, `kroger 0382`, and `KROGER`. The specified normalizer returns `("KROGER", "382")`, `("KROGER", "0382")`, and `("KROGER",)` respectively. Assert identical classification, and test normalization against the actual token sequences.

6. **Suggestion — `recurring` does not establish monthly frequency.** The schema carries only a boolean, so appending `" monthly"` to every recurring charge misdescribes annual or weekly charges. Use frequency-neutral wording unless cadence is supplied explicitly.

7. **Suggestion — The verification commands run the expensive sweep twice.** Step 12’s first command includes the new perf-marked 300-window brute-force sweep, then the final perf command repeats it. Add `-m "not perf"` to the first command so the expensive sweep runs once in the designated performance pass.
