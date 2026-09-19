### Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Plan adherence | Fail | AC12 still fails in two focus-restoration cases. |
| Scope discipline | Excellent | Changes remain scoped; the corrected deadline wording is justified. |
| Test coverage | Fail | 66 tests pass, but focus behavior remains untested and incompletely verified. |
| Review compliance | Fail | The reviewed focus-preservation requirement remains partially unresolved. |
| Freeze integrity | Excellent | No hashes present; frozen spec text is unchanged, with results appended. |
| Regression check | Acceptable | No test assertion failures; one backend setup error is environmental. Protected files match `main`. |
| Documentation | Acceptable | Minor stale figures and an overstated test-coverage claim. |
| **Overall** | **Fail** | **Focus preservation remains incomplete.** |

### Commentary

1. **Plan adherence, Review compliance — downgrade to Fail: collapsed left-out rows cannot receive restored focus.**  
   Collapse “other changes,” then keyboard-toggle the card minimum in the plan. Its checkbox moves into the closed [details element](/Users/nathanstough/Desktop/vthacks-frontend/frontend/src/components/PrescriptionList.tsx:125), while [restoration](/Users/nathanstough/Desktop/vthacks-frontend/frontend/src/App.tsx:106) merely calls `.focus()` without opening it. The hidden control cannot receive focus under the [HTML focus rules](https://html.spec.whatwg.org/multipage/interaction.html#focusable-area). This is a source-traced finding, not a browser reproduction. Reveal the destination before restoring focus, and verify Space → re-solve → Space with the section initially collapsed.

2. **Plan adherence — contributes to Fail: rapid undo loses focus on the second response.**  
   Toggle the card, then undo while its request is in flight. If that response lands before the undo’s debounce expires, it moves the row and restores focus, consuming [the tracked reference](/Users/nathanstough/Desktop/vthacks-frontend/frontend/src/App.tsx:97). The final response moves the row back, but the reference is now empty, leaving focus on the body. Executing the extracted production handlers with a mocked document reproduced this sequence; actual solver responses confirmed both row movements. Preserve focus across successive commits or reject intermediate responses superseded by current input.

3. **Test coverage — downgrade to Fail: the focus regression has no regression test.**  
   The [latest results](/Users/nathanstough/Desktop/vthacks-frontend/docs/specs/2026-09-19_frontend-ux.md:337) claim all three previous findings gained tests. The seven additions cover narration and deadlines; none exercises focus. Recorded structural checks also do not establish the specified keyboard interaction. Add coverage for both cases above and perform the actual keyboard check. Browser replay here was unavailable: the in-app browser was absent and Chrome access was not approved.

4. **Regression check — Acceptable due to incomplete independent verification, not a demonstrated regression.**  
   On branch `frontend` in the supplied worktree, Node 22.17.1 passed `npm run lint`, both `tsc --noEmit -p` checks, and all **66 `npm test` tests**. A fresh Vite build with `write: false` matched the existing JavaScript bundle exactly and passed its wording gates. Python 3.14.7 running `.venv/bin/pytest backend/ -q -m 'not perf' -s -p no:cacheprovider` produced **976 passed, 6 deselected, 1 setup error**: [the fixture](/Users/nathanstough/Desktop/vthacks-frontend/backend/tests/test_api.py:28) requires a writable temporary directory unavailable in this sandbox.

5. **Documentation — downgrade to Acceptable only.**  
   The [demo checklist](/Users/nathanstough/Desktop/vthacks-frontend/docs/demo-script.md:22) retains the historical 59-test figure, and the [feature document](/Users/nathanstough/Desktop/vthacks-frontend/docs/features/frontend.md:169) says 619 kB versus approximately 620 kB now. Refresh those figures and append a correction to the regression-test claim in finding 3. These do not warrant Documentation Fail.
