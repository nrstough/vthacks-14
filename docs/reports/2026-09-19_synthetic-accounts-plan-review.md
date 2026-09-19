1. **Critical** — Step 2.2 cannot satisfy D6 by sanitizing only product-generated descriptors. `/api/candidates` accepts arbitrary descriptions, and `/api/solve` accepts arbitrary candidate labels/details. Masking only in `assemble.py` also leaves candidate responses exposed. Define shared display sanitization for both response paths, preserve raw descriptors for classification, and update the existing test that explicitly requires the banned descriptor in `c.detail`.

2. **Critical** — Step 2.3’s quoted-text exception would allow banned words into `ChatResponse.reply`. Removing scheduled descriptions from the prompt is also insufficient: descriptors appear in plan details, candidate details, and conversation messages. Use safe display names consistently and retain a final output check. Test both absence of corrupted names and absence of banned wording.

3. **Critical** — Phase 4 never specifies the actual account seed/read-back workflow. Credential verification creates only a customer; account creation, transaction writes, normalized reads, stable transaction IDs, and opening-balance semantics remain undefined. Specify these mappings, the endpoint invoking them, and behavior after partial writes or ambiguous timeouts so retries do not duplicate data or double-count balances.

4. **Critical** — The backend-only scope conflicts with the promised on-screen modelled label and Nessie fallback disclosure. `frontend/src/App.tsx` uses canned scenarios, and its existing source chip describes solver provenance only. Either explicitly scope delivery to an API with provenance metadata and defer UI acceptance, or include a coordinated frontend integration step.

5. **Critical** — D-F appears only in the risk table. Step 3.4 takes locks from the current candidate response, so it cannot reproduce eviction during re-fetch. Define the refresh policy and test: obtain a truncated list, pin a candidate, change the schedule so it falls below the cutoff, then refresh and solve.

6. **Critical** — Registering a `nessie` marker does not deselect it. The documented gate uses `-m "not perf"`, which includes live Nessie tests. Add explicit opt-in collection or update every gate command to exclude Nessie; reconcile this with the spec’s “deselect count unchanged” requirement.

7. **Critical** — Step 4.4 must preserve decimal precision during JSON decoding, before conversion to cents. Copying Gemini’s `json.loads` introduces floats; `Decimal(str(value))` cannot recover digits already lost. Specify decimal-aware decoding and exact outbound encoding, bounds/non-finite checks, and whether `0.1+0.2` must be rejected under the no-rounding rule.

8. **Critical** — Phase 3 leaves the new endpoint’s method, path, request fields, defaults, seed reproducibility, and response shape unspecified. Its numbered “P2” tests are not defined in either the plan or run spec. Supply the contract and executable acceptance criteria, including what happens when payday adjustment leaves no day available for the planted pre-payday dip.

9. **Suggestion** — Step 2.1 should enumerate display fields rather than scan every `StrictStr`: IDs legally contain banned substrings, and existing tests deliberately use `guaranteed_1`. Its counterfactual is also reversed—removing a checked field normally hides failures. Inject prohibited text into each display field and verify the checker detects it.

10. **Critical** — Phase 5 fixes deployment scripts but never schedules the actual deployment or verifies the served application. A public-origin `/health` check still passes when the bundle is missing. Add the deployment step and verify public `/`, a referenced JS asset, and the API; run the spec’s frontend lint/build/test checks before shipping.
