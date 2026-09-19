1. **Critical** — Step 6’s chat-button gradient fails the intended contrast threshold. White text over its midpoint is approximately 4.31:1, falling further toward `#0ea5e9`; the button uses 14px text. Darken the gradient and include the enabled `.chat-form button` in step 8’s contrast checks, measuring the background beneath the text.

2. **Critical** — The backend verification commands pipe pytest into `tail` without enabling `pipefail`. A failed test run can therefore return success, and truncation can hide parity skip details. Preserve pytest’s exit status and full report; explicitly verify that the parity tests executed.

3. **Suggestion** — The new tier-3 wording is not pinned end-to-end. The proposed Python unit test exercises `plan_reason`, while the frontend test merely inspects exported constants; neither establishes that the TypeScript solver actually emits the gap variant. Add a deterministic tier-3 fixture containing a selected zero-marginal change, assert its emitted reason, and run that fixture through parity.

4. **Suggestion** — `backend/app/chat/prompt.py` independently describes every non-load-bearing plan item as “only protects the cushion, not needed to clear zero.” Leaving this untouched feeds Gemini the old interpretation alongside the new tier-3 reason. Remove that duplicated interpretation or make it tier-aware, and test the generated chat context.

5. **Suggestion** — Step 7’s font-reference test can pass vacuously if no URLs match, including when the emitted CSS uses quoted URLs. Assert that CSS files and font references were found, accept quoted and unquoted `url(...)` forms, and verify the expected families and weights are represented.
