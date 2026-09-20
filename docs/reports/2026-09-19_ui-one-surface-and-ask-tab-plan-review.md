1. **Critical** — Step 4 contradicts the required auto-open behavior. `decideConsidered(1, 2)` returns `leave`, so rule out A → manually collapse → rule out B stays collapsed on the Safari path. Open whenever the override count increases, and test that sequence explicitly.

2. **Critical** — Count transitions cannot guarantee collapse on reset. If the user manually opens the list with zero overrides, pressing a preset produces `0 → 0`, leaving it open. Reset `consideredOpen` explicitly in `adopt()` and the clear-overrides handler; test resetting a manually opened list with zero overrides.

3. **Critical** — Clearing `newIds` only when leaving Plan misses pending responses. `App.tsx`’s `apply()` can repopulate it while Ask is visible, causing rows to animate as new on return. Suppress or clear highlights for responses received while Plan is hidden, and verify switching away before a delayed solve completes.

4. **Critical** — The chat-scroll mitigation has no implementation step. `ChatPanel.tsx` scrolls only when `[messages, pending]` changes; an answer arriving while hidden will not trigger another scroll when Ask becomes visible. Pass visibility into `ChatPanel`, rerun scrolling on reveal, and test a response arriving while Plan is selected.

5. **Suggestion** — The browser assertion targets the wrong element. With `hidden` on the wrapper, the nested `.chat-panel` can still compute `display: flex` despite being invisible. Assert `display: none` on the wrapper, no rendered panel rectangles, and exclusion from keyboard navigation.

6. **Suggestion** — Step 6 never explicitly renames “Checking account” to “Plan” or wires the new tab helpers into rendering. Pure helper tests cannot prove the actual pill labels or alarm placement. Specify those changes and verify the rendered labels, default selection, and tier-3 dot.

7. **Suggestion** — Step 0’s expected status already excludes an intended artifact: the checkout contains both the untracked run spec and `docs/reports/2026-09-19_ui-one-surface-and-ask-tab-plan.md`. Allowlist both explicitly so implementation does not immediately hit its prescribed hard stop.
