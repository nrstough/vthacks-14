### Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Plan adherence | Acceptable | Core design implemented; D9 has a documented display limitation. |
| Scope discipline | Excellent | Changes stay within scope; unrelated changes came from merged `main`. |
| Test coverage | **Fail** | The required counterfactual test for descriptor forgery does not detect a broken security boundary. |
| Review compliance | Excellent | Recorded Codex findings are addressed in the implementation. |
| Freeze integrity | Acceptable | Skipped: no P1/P2/P3 hashes present. |
| Regression check | Acceptable | No code failures observed; four backend tests blocked by sandbox permissions. |
| Documentation | Acceptable | Minor reporting inconsistency; changed behavior is documented. |
| **Overall** | **Fail** | Missing effective regression coverage for the extraction boundary. |

### Commentary

1. **Test coverage — causes Fail.** [test_chat_suggestions.py:136](/Users/nathanstough/Desktop/vthacks-chat-acts/backend/tests/test_chat_suggestions.py:136) supplies literal marker text **inside a sentence**, rather than a masked merchant reference on a trailing line. It therefore tests neither descriptor restoration nor extraction ordering. I reversed the ordering **in memory**, extracting after unmasking: all **65 suggestion tests still passed**. A separate probe confirmed that this mutation turns a merchant descriptor into an actionable suggestion, while the current implementation correctly returns none. Add an endpoint test whose mocked completion ends with the merchant’s opaque reference; assert no suggestions and quoted display text. Verify that reversing the ordering makes it fail. This violates the run spec’s explicit requirement that every guard have a counterfactual test.

2. **Test coverage / Regression check — limits grades to Acceptable independently of finding 1.** On `chat-acts`, Python 3.14.7, `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest backend/ -q -p no:cacheprovider --capture=sys` produced **2,373 passed, 10 deselected, four setup errors**. All four require temporary-file creation prohibited by this read-only sandbox. With Node 22.17.1, `npm test` produced **369 passes**; `npm run lint` and both TypeScript project checks passed. A fresh production build was not rerun because it writes files; bundle tests used the existing `dist/`. These limitations are not demonstrated regressions.

3. **Plan adherence — downgrade to Acceptable.** D9’s display neutralization misses marker lines indented with non-ASCII whitespace, as acknowledged in [suggestions.py:148](/Users/nathanstough/Desktop/vthacks-chat-acts/backend/app/chat/suggestions.py:148). Such text remains visible as raw syntax, although it cannot become an actionable offer. A separate, broader display-only matcher would close this gap without weakening parsing.

4. **Documentation — downgrade to Acceptable, cosmetic only.** The run spec’s [Results section:370](/Users/nathanstough/Desktop/vthacks-chat-acts/docs/specs/2026-09-19_chat-suggests-constraints.md:370) says only one existing test changed. Three changed: the response equality assertion and two monkeypatched generators. The later Deviations section correctly records the latter two. Reconcile the Results summary; no operator behavior is affected.
