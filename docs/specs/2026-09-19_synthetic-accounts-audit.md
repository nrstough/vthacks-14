### Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Plan adherence | **Fail** | Nessie workflow and D8 disclosure remain undelivered; public deployment acceptance is unverified. |
| Scope discipline | Excellent | Frontend changes came from the `main` merge, not this implementation. |
| Test coverage | **Fail** | Tests miss reproduced chat defects; public deployment checks lack passing evidence. |
| Review compliance | **Fail** | Caller-controlled text can still bypass the chat scrubber. |
| Freeze integrity | Acceptable | No P1/P2/P3 hashes present; committed spec changes are append-only. Generator hash matches. |
| Regression check | **Fail** | Chat masking introduces prompt corruption and retains the wording bypass. Existing canaries and performance checks pass. |
| Documentation | Acceptable | Living docs disclose incomplete Nessie work; minor chat documentation drift. |
| **Overall** | **Fail** | |

### Commentary

1. **Plan adherence — causes Fail.** The [dated correction](docs/specs/2026-09-19_synthetic-accounts.md#claims-struck-as-untrue) acknowledges missing account seeding/read-back, `not_round_tripped`, and D8’s fallback-disclosure flag. The adapter remains disconnected from HTTP routes. Recording omissions does not fulfill the original commitments. Complete the workflow and disclosure, or obtain an explicit scope revision. D-F and D-G are also expressly deferred.

2. **Review compliance / Regression check / Test coverage — causes Fail.** In [chat masking](backend/app/chat/__init__.py:126), arbitrary conversation text receives descriptor exemptions. Reproduced through `chat()` with a valid descriptor `guaranteed`, user text `This plan is guaranteed to clear.`, and an echoing model stub: the reply returns that sentence unchanged. Masking hides the word from `scrub()`, then restoration reintroduces it as a product claim. Preserve descriptor provenance structurally and add this end-to-end regression case.

3. **Regression check / Test coverage — causes Fail.** [Masking the entire system instruction](backend/app/chat/__init__.py:121) also replaces ordinary prose substrings. A valid transaction description `a` produces **239 replacements in the fixed brief**, including `You ⸤M11⸥re the expl⸤M11⸥iner`. Replace descriptors in structured transaction fields before rendering context; leave fixed instructions intact. Test short descriptors and descriptors matching financial figures.

4. **Plan adherence / Test coverage — causes Fail.** The spec’s last deployment record leaves the firewall unresolved. The script contains public checks, but there is no recorded successful public HTML, referenced-JavaScript, and solve-response verification. Run those checks against the deployed revision and append the results; an internal `/health` response does not satisfy acceptance.

5. **Test coverage / Regression check — verification limits, no additional downgrade.** On `data-deploy` at `10767bc`, using Python **3.14.7** and Node **22.17.1**:
   - Backend gate, with `--capture=sys -p no:cacheprovider`: **1,997 passed, 1 skipped, 8 deselected, 3 setup errors**. All three errors require temporary files prohibited by this read-only environment.
   - Performance suite: **8 passed**; all **300 accounts agreed in 126.6 seconds**, within the ~137-second baseline.
   - Frontend lint passed; **209 tests passed** against the existing bundle. A fresh build was not performed because filesystem writes are prohibited.
   - All specified canaries matched; `windows(300)` was byte-identical to `70bac4d`, including the full golden hash.

6. **Documentation — Acceptable, minor downgrade only.** [The chat feature doc](docs/features/chat.md:94) still describes unconditional final reply scrubbing without explaining descriptor restoration afterward. Update it to describe the actual boundary. The accounts, Nessie, and API docs accurately disclose the delivered functionality and omissions.
