### Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Plan adherence | Fail | AC12 still loses focus across overlapping responses with different balance inputs. |
| Scope discipline | Excellent | Protected files and dependencies unchanged; deviations support the requested behavior. |
| Test coverage | Fail | 81 tests pass, but they miss the incorrect derivation of focus settlement. |
| Review compliance | Fail | The overlapping-response focus fix remains incomplete. |
| Freeze integrity | Excellent | No recorded hashes to validate; original committed spec text is unchanged. |
| Regression check | Acceptable | Frontend checks pass; backend has 976 passes and one environmental setup error. |
| Documentation | Acceptable | Demo checklist has a stale frontend test count. |
| **Overall** | **Fail** | Focus preservation remains incomplete. |

### Commentary

1. **Plan adherence / Review compliance — downgrade to Fail.** [App.tsx:101](/Users/nathanstough/Desktop/vthacks-frontend/frontend/src/App.tsx:101) treats matching override sets as proof that the displayed response matches all current input. It ignores pending starting-balance and cushion changes.

   A concrete sequence uses the gym checkbox: unexclude it at $200, then change the balance to $300 while the first solve is pending. If the gym has focus when the older response arrives during the newer request’s debounce, that response moves it into the plan, restores focus, and clears the remembered ID. The $300 response subsequently removes it from the plan, leaving nothing to restore. Exercising the real oracle and helpers confirms these transitions and decisions; the DOM outcome is source-traced, not browser-reproduced.

   Track the full request associated with each response and retain focus memory until it matches current input.

2. **Test coverage — downgrade to Fail.** [focus.test.ts:55](/Users/nathanstough/Desktop/vthacks-frontend/frontend/tests/focus.test.ts:55) supplies `settled` directly, so its overlap tests cannot detect the incorrect value produced by `App.tsx`. Add a regression covering equal overrides with different pending balance/cushion values, including both response arrivals. AC12’s real keyboard sequence and React event wiring also remain unverified.

3. **Documentation — downgrade to Acceptable only.** [demo-script.md:22](/Users/nathanstough/Desktop/vthacks-frontend/docs/demo-script.md:22) reports **75 frontend tests**; the current suite contains **81**. Update the count. This is low-impact staleness, not a Documentation failure.

4. **Regression check — Acceptable because verification is environment-limited.** On branch `frontend` in `/Users/nathanstough/Desktop/vthacks-frontend`, Node **22.17.1** passed `npm run lint`, both TypeScript configurations with `--noEmit`, and `npm test` (**81/81**). A Vite build with `write:false` matched every existing production artifact byte for byte.

   Under Python **3.14.7**, `.venv/bin/pytest backend/ -q -m 'not perf' --capture=sys -p no:cacheprovider` produced **976 passed, 6 deselected, 1 setup error**. [test_api.py:28](/Users/nathanstough/Desktop/vthacks-frontend/backend/tests/test_api.py:28) requires a writable temporary directory, unavailable in this sandbox. This is not an implementation regression. Live keyboard replay was unavailable because computer access to Chrome was denied.
