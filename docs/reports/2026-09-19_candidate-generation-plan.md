# Plan — candidate generation + `POST /api/candidates`

Run spec: `docs/specs/2026-09-19_candidate-generation.md` (decisions D1–D14, AC1–AC12).
Feature spec: `docs/features/candidates.md`. Branch `backend`, worktree
`/Users/nathanstough/Desktop/VT Hacks`. Deep mode: three exploration agents (architecture,
file impact, risk) → this plan → critique → Codex review.

Line numbers are as of commit `af65052` (original numbering; step 1b's insert shifts
1d/1e down by ~22 lines) and were read by the file-impact agent; re-check
`git branch --show-current` and `git status` before step 1 — this checkout has been
switched underneath sessions twice tonight.

## Ground rules carried from CLAUDE.md and the run spec

- `git switch`, never `checkout`. `git add` names files, never a directory.
- No edit to any existing `backend/tests/test_*.py`, to `frontend/`, to
  `backend/requirements.txt`, or to `docs/api-contract.md` lines 8–160.
- Money is integer cents; dates are `YYYY-MM-DD` strings at every model boundary
  (`Strict` means a `datetime.date` passed to a `StrictStr` field raises); never
  `model_construct()` — it skips the validators that make a bad defer loud.
- No `set` in anything that decides an output; tuples and insertion-ordered dicts only.

## Step 0 — pre-flight

```bash
git branch --show-current      # must print: backend
git status --short             # only the five untracked docs/ files (spec, feature, plan, review, Solana addition)
.venv/bin/pytest backend/ -q -m "not perf" | tail -1   # 977 passed
```

## Step 1 — `backend/app/schemas.py` (additive)

1a. Line 1 docstring: `"""Request and response models for POST /api/solve and POST
/api/candidates.` (rest unchanged).

1b. After `class Locks` (ends line 121), before `class SolveRequest` (line 124), add the
two shared checks as module-level functions. `iso()` at line 47 is the precedent for a
module-level helper both models call. Bodies are the *current* `_horizon_end` (lines
143–152) and `_scheduled` (156–160), verbatim:

```python
def check_horizon(horizon_end: str, as_of: str | None) -> str:
    """The span check both request models share. See the module docstring for why it
    runs on horizon_end and reads as_of from info.data."""
    iso(horizon_end)
    if as_of:
        span = (datetime.date.fromisoformat(horizon_end) - datetime.date.fromisoformat(as_of)).days + 1
        if span < 1:
            raise ValueError("horizon_end is before as_of; there are no days to plan over")
        if span > MAX_T:
            raise ValueError(f"horizon of {span} days is longer than the {MAX_T}-day limit")
    return horizon_end


def check_unique_txn_ids(v: list[ScheduledTxn]) -> list[ScheduledTxn]:
    ids = [t.id for t in v]
    if len(ids) != len(set(ids)):
        raise ValueError("transaction ids must be unique")
    return v
```

1c. `SolveRequest._horizon_end` (141–152) body → `return check_horizon(v,
info.data.get("as_of"))`; `_scheduled` (154–160) body → `return check_unique_txn_ids(v)`.
Field order, names, decorators unchanged. Error strings unchanged (test_validation asserts
on them).

1d. Insert at line 197 (after `SolveRequest`, inside the request section):

```python
class CandidatesRequest(Strict):
    """What /api/candidates needs: the window and the rows, nothing about balances.

    Declared in the same order as SolveRequest and checked by the same functions,
    so the two endpoints reject the same input the same way. `limit` defaults to
    MAX_FREE because that is the largest set every fallback still answers — the
    exhaustive engine here and the browser's stand-in both refuse above it.
    """

    as_of: StrictStr
    horizon_end: StrictStr
    scheduled: list[ScheduledTxn] = Field(max_length=MAX_SCHED)
    limit: Annotated[StrictInt, Field(ge=1, le=MAX_N)] = MAX_FREE

    @field_validator("as_of")
    @classmethod
    def _as_of(cls, v: str) -> str:
        return iso(v)

    @field_validator("horizon_end")
    @classmethod
    def _horizon_end(cls, v: str, info: ValidationInfo) -> str:
        return check_horizon(v, info.data.get("as_of"))

    @field_validator("scheduled")
    @classmethod
    def _scheduled(cls, v: list[ScheduledTxn]) -> list[ScheduledTxn]:
        return check_unique_txn_ids(v)
```

`limit` is `StrictInt`, so `null` and `"18"` are 422 and an omitted key is 18; no
`validate_default` is needed because the default is not something a validator inspects.

1e. Append after `class SolveResponse` (ends line 267):

```python
class CandidatesMeta(Strict):
    rows_considered: Annotated[StrictInt, Field(ge=0, le=MAX_SCHED)]
    protected: list[Id]      # sorted
    unrecognised: list[Id]   # sorted
    not_actionable: list[Id] # sorted
    truncated: bool


class CandidatesResponse(Strict):
    candidates: list[Candidate] = Field(max_length=MAX_N)
    meta: CandidatesMeta
```

## Step 2 — `backend/app/candidates/__init__.py` and `lexicon.py`

2a. `__init__.py`: docstring only ("Turn a transaction list into the changes a person
could make. See docs/features/candidates.md.") plus `from .generator import generate`.
The module is `generator.py`, not `generate.py`, so the package attribute and the
function do not share a name.

2b. `lexicon.py`:

```python
_NON_ALNUM = re.compile(r"[^A-Z0-9]+")

def normalise(text: str) -> tuple[str, ...]:
    return tuple(_NON_ALNUM.sub(" ", text.upper()).split())
```

Category names as module constants (strings). `PROTECTED: tuple[str, ...]` =
`("card_payment", "housing", "loan", "insurance", "utilities", "phone", "medical",
"tuition", "transfer", "atm_cash")`. `PRIORITY: tuple[str, ...]` = `PROTECTED +
("food_delivery", "rideshare", "coffee", "groceries", "fuel", "restaurant", "streaming",
"gym", "software", "shopping", "entertainment", "personal_care")`. Streaming precedes
shopping so `AMAZON PRIME VIDEO` pauses rather than cancels an order; delivery precedes
rideshare so `UBER EATS` beats `UBER`.

`ENTRIES: tuple[tuple[str, str | None, tuple[str, ...]], ...]` — `(category, display,
phrases)`; display is `None` for protected categories and for generic phrases, a brand
name otherwise. Minimum
content (phrases are written as they appear on statements; `normalise` is applied at
import so `GOLD'S GYM` and `APPLE.COM/BILL` are fine):

- card_payment: CHASE CARD, CARD EPAY, CAPITAL ONE, AMEX, AMERICAN EXPRESS, DISCOVER,
  CITI CARD, CREDIT CARD, CRD PMT, CARDMEMBER, SYNCHRONY, BARCLAYCARD, APPLE CARD
- housing: RENT, MORTGAGE, APARTMENT, APARTMENTS, APTS, PROPERTY MGMT, PROPERTIES,
  LEASING, HOA, GUARANTEED RATE, ROCKET MORTGAGE
- loan: LOAN, NELNET, SALLIE MAE, NAVIENT, MOHELA, AUTO PMT, CAR PMT, TOYOTA FIN,
  HONDA FIN, FORD CREDIT, AFFIRM, KLARNA, AFTERPAY, UPSTART, SOFI
- insurance: INSURANCE, GEICO, PROGRESSIVE, STATE FARM, ALLSTATE, USAA, GAP INSURANCE,
  LEMONADE
- utilities: ELECTRIC, DOMINION ENERGY, APPALACHIAN POWER, DUKE ENERGY, POWER CO,
  POWER COMPANY, WATER BILL, WATER AUTH, WATER DEPT, WATER WORKS, SEWER, UTILITY,
  UTILITIES, COLUMBIA GAS, GAS CO, GAS COMPANY, WASTE MGMT, COMCAST, XFINITY, COX COMM,
  SPECTRUM, FIOS, INTERNET
- phone: VERIZON, T MOBILE, TMOBILE, AT T, ATT WIRELESS, SPRINT, MINT MOBILE, VISIBLE,
  CRICKET, WIRELESS
- medical: PHARMACY, MEDICAL, HEALTHCARE, HEALTH SYSTEM, CLINIC, DENTAL, HOSPITAL,
  URGENT CARE, TARGET OPTICAL, BP MONITOR (`HEALTH` alone would swallow `ANYTIME FITNESS
  HEALTH CLUB`)
- tuition: TUITION, BURSAR, UNIVERSITY, COLLEGE, VIRGINIA TECH
- transfer: TRANSFER, ZELLE, VENMO, CASH APP, PAYPAL, XFER
- atm_cash: ATM, WITHDRAWAL, CASH WITHDRAWAL
- food_delivery (DoorDash / Uber Eats / Grubhub / Instacart / Postmates): DOORDASH,
  UBER EATS, UBEREATS, GRUBHUB, INSTACART, POSTMATES
- rideshare (Uber / Lyft): UBER, LYFT
- coffee (display "coffee" unused — template has no brand): STARBUCKS, DUNKIN, PEET,
  DUTCH BROS, COFFEE, CAFE, TIM HORTONS
- groceries (display per brand; template uses no brand): KROGER, HARRIS TEETER, FOOD
  LION, PUBLIX, WALMART, WAL MART, ALDI, LIDL, TRADER JOE, WHOLE FOODS, WHOLEFDS,
  SAFEWAY, GIANT FOOD, GIANT EAGLE, WEGMANS, COSTCO, SAMS CLUB, SAM S CLUB, BJ S
  WHOLESALE, GROCERY, SUPERMARKET, FRESH MARKET, FARMERS MARKET, H E B, MEIJER, WINN
  DIXIE, SPROUTS, FOOD CITY
- fuel: SHELL OIL, SHELL SERVICE, EXXON, MOBIL, CHEVRON, SUNOCO, WAWA, SHEETZ, 7
  ELEVEN, CIRCLE K, SPEEDWAY, MARATHON PETRO, CITGO, VALERO, RACETRAC, QUIKTRIP, PILOT
  TRAVEL, FLYING J, LOVES TRAVEL, TEXACO, GAS STATION
- restaurant (display per brand): CHIPOTLE, MCDONALD, CHICK FIL A, TACO BELL, WENDY,
  BURGER KING, PANERA, SUBWAY, PIZZA, DOMINO, PAPA JOHN, FIVE GUYS, COOK OUT, BOJANGLES,
  ZAXBY, RAISING CANE, RESTAURANT, GRILL, BISTRO, DINER, SUSHI, WINGS, BBQ, TAVERN,
  BREWERY, TOTAL WINE, ABC STORE, TST
- streaming: NETFLIX, SPOTIFY, HULU, DISNEY PLUS, DISNEYPLUS, HBO, MAX COM, PARAMOUNT, PEACOCK, APPLE
  COM BILL, APPLE MUSIC, YOUTUBE PREMIUM, AUDIBLE, PRIME VIDEO, CRUNCHYROLL, SIRIUS,
  PANDORA, TIDAL
- gym (display "gym"; template has no brand): PLANET FIT, PLANET FITNESS, LA FITNESS,
  ANYTIME FITNESS, GOLD S GYM, YMCA, CRUNCH FITNESS, ORANGETHEORY, EQUINOX, GYM, CLUB
  FEES, PELOTON, CORE POWER YOGA, FUEL FITNESS
- software: ADOBE, MICROSOFT, GOOGLE ONE, GOOGLE STORAGE, ICLOUD, DROPBOX, CHATGPT,
  OPENAI, NOTION, GITHUB, PATREON, SUBSTACK, NYTIMES, NY TIMES, WSJ, WASHINGTON POST
- shopping (display per brand): AMZN, AMAZON, TARGET, BEST BUY, BESTBUY, EBAY, ETSY,
  WAYFAIR, IKEA, HOME DEPOT, LOWE S, LOWES, APPLE STORE, NIKE, ZARA, H M, OLD NAVY,
  TJ MAXX, TJMAXX, MARSHALLS, ROSS STORES, KOHL, MACY, NORDSTROM, SHEIN, TEMU, GAMESTOP,
  STEAM GAMES, PLAYSTATION, XBOX, NINTENDO, ULTA, SEPHORA, DICK S SPORTING, REI
- entertainment: AMC, REGAL, CINEMARK, TICKETMASTER, STUBHUB, EVENTBRITE, TOPGOLF,
  DAVE BUSTER, THEATRE, THEATER, CINEMA
- personal_care: SUPERCUTS, GREAT CLIPS, SALON, BARBER, NAILS, SPA, MASSAGE

Import-time invariants (plain `if … raise ValueError` at module scope, so a bad table
fails at import, i.e. at test collection): every protected entry has `display=None`
(the brand-or-fallback rule for changeable entries lives in `policy.py`, which imports
this module and can see `LABELS`); every category in `ENTRIES` is in `PRIORITY`; no normalised phrase appears in two categories;
no single-token phrase is ≤ 3 characters or in `_GENERIC = ("CLUB", "MARKET", "WATER",
"POWER", "GAP", "BP", "QT", "FUEL", "GIANT", "PILOT", "GAS", "STORE", "SHOP", "BANK",
"ONLINE", "PAYMENT", "SERVICE", "SERVICES", "INC", "LLC", "CO", "THE", "OF", "AND",
"US", "USA")`. The rule, exactly: a **single-token** phrase of ≤ 3 characters must be
in `_SHORT_OK = ("ATM", "HOA", "WSJ", "REI", "AMC", "TST", "BBQ", "SPA", "GYM", "HBO")`;
multi-token phrases (`H M`, `AT T`, `H E B`, `7 ELEVEN`, `CLUB FEES`) are exempt because
the ban is on lone generic tokens, not on tokens inside a phrase. The critique found
`GYM` and `HBO` missing from the first draft of this list — the import would have
failed at test collection.

Index built at import: `_INDEX: dict[str, tuple[_Phrase, ...]]` keyed by first token,
where `_Phrase = (tokens, rank, category, display)` and `rank = PRIORITY.index(category)`;
the tuple for each key is sorted by `(rank, -len(tokens), tokens)` so the first contiguous
match in iteration order is the winner without a second pass.

```python
@dataclass(frozen=True)
class Match:
    category: str
    display: str | None

UNKNOWN = Match("unknown", None)

def classify(description: str) -> Match:
    tokens = normalise(description)
    best: tuple[int, int, tuple[str, ...], Match] | None = None
    for i, tok in enumerate(tokens):
        for phrase, rank, category, display in _INDEX.get(tok, ()):
            if tokens[i : i + len(phrase)] == phrase:
                key = (rank, -len(phrase), phrase)
                if best is None or key < best[:3]:
                    best = (*key, Match(category, display))
                break  # this key's tuple is sorted; the first hit is its best
    return best[3] if best else UNKNOWN
```

## Step 3 — `backend/app/candidates/policy.py`

```python
@dataclass(frozen=True)
class Alternative:
    action: str          # from schemas.Action
    pct: int             # of abs(amount), floored to cents
    lead_time_days: int
    pain: int
    needs_payday: bool = False

POLICY: dict[str, tuple[Alternative, ...]] = {
    "streaming":     (Alternative("cancel", 100, 2, 1),),
    "gym":           (Alternative("cancel", 100, 3, 1),),
    "software":      (Alternative("cancel", 100, 1, 2),),
    "food_delivery": (Alternative("skip", 100, 0, 2),),
    "coffee":        (Alternative("skip", 100, 0, 1),),
    "restaurant":    (Alternative("skip", 100, 0, 2),),
    "groceries":     (Alternative("downgrade", 35, 0, 3), Alternative("defer", 100, 0, 4, True)),
    "fuel":          (Alternative("defer", 100, 0, 3, True), Alternative("downgrade", 50, 0, 3)),
    "shopping":      (Alternative("skip", 100, 1, 2),),
    "rideshare":     (Alternative("skip", 100, 0, 3),),
    "entertainment": (Alternative("skip", 100, 0, 2),),
    "personal_care": (Alternative("skip", 100, 1, 2),),
}
UNKNOWN_DISCRETIONARY = (Alternative("skip", 100, 0, 3),)
```

`LABELS: dict[tuple[str, str], tuple[str, str | None]]` keyed `(category, action)` →
`(with_brand, without_brand)`; `{brand}`, `{date}` (short effective date), `{recharge}`
(short recharge date) placeholders, per the feature spec's wording table. Lexicon
entries whose phrase is a generic noun (`PIZZA`, `GRILL`, `DINER`, `TAVERN`, `TST`,
`RESTAURANT`, `THEATRE`, `CINEMA`, `SALON`, `NAILS`, `BARBER`, `SPA`, `MASSAGE`, …) carry
`display=None`, and the generator uses `without_brand` for them: restaurant → "Skip the
meal out"; entertainment → "Skip the night out"; personal_care → "Skip the appointment";
shopping → "Cancel the order". Categories whose template uses `{brand}` and whose lexicon
has a `None` display **must** have a `without_brand` template — an import-time invariant.
Pinned displays: DoorDash, Uber Eats, Grubhub, Instacart, Uber, Lyft, Netflix, Spotify,
Hulu, Disney+, HBO, Amazon, Target, Best Buy, Adobe, Microsoft, Chipotle, Panera,
McDonald's, Chick-fil-A. `("unknown", "skip")` → `("Skip this charge", None)` lives in
`LABELS` too, so the invariant below covers it. `DETAIL_SUFFIX`: recurring → `"
recurring"` (the schema carries a boolean, not a cadence — "monthly" would misdescribe a
weekly or annual charge); downgrade → `" down to {remaining}"`; defer → `" moved past
payday"`.

Import-time invariants: every `POLICY` key is in `lexicon.PRIORITY` and not in
`PROTECTED`; every non-protected `PRIORITY` category has a `POLICY` row; within a row
actions are unique; `action` in `get_args(Action)`; `1 <= pct <= 100`; `1 <= pain <= 5`;
`0 <= lead_time_days <= MAX_T`; `action == "defer"` iff `needs_payday`; every
`(category, action)` in `POLICY` **and** `("unknown", "skip")` has a `LABELS` entry; for
every `with_brand` template containing `{brand}`, either every lexicon entry of that
category carries a display or a `without_brand` template exists.

## Step 4 — `backend/app/candidates/generator.py`

```python
def generate(req: CandidatesRequest) -> CandidatesResponse:
```

1. `window = (req.as_of, req.horizon_end)`; `paydays: list[str]` = sorted dates of rows
   with `kind == "income" and amount_cents > 0 and as_of <= date <= horizon_end` (string
   comparison is safe on canonical ISO; duplicates on one day collapse naturally because
   only the date is used).
2. For each `txn` in `req.scheduled` in input order: pre-filter `kind != "income" and
   amount_cents < 0 and as_of <= date <= horizon_end` → else skip silently (not
   considered). `considered += 1`. `m = classify(txn.description)`.
   - `m.category in PROTECTED` → `protected.append(txn.id)`; continue.
   - `m.category == "unknown"`: `unrecognised.append(txn.id)`; if `txn.kind !=
     "discretionary"` → `protected.append(txn.id)`; continue. Else `alts =
     UNKNOWN_DISCRETIONARY`.
   - else `alts = POLICY[m.category]`.
   - `emitted_any = False`. For `k, alt in enumerate(alts)`:
     - `freed = abs(txn.amount_cents) * alt.pct // 100`; if `freed == 0` → continue.
     - if `days_between(req.as_of, txn.date) < alt.lead_time_days` → continue.
     - `recharge = None`; if `alt.needs_payday`: `recharge = next((d for d in paydays if
       d > txn.date), None)`; if `recharge is None` → continue. (`action == "defer"` iff
       `needs_payday`; assert that in policy invariants.)
     - `cid = _candidate_id(txn.id, alt.action)`.
     - `label = _label(m, alt, txn, recharge)`; `detail = _detail(txn, alt, freed)`.
     - `Candidate(id=cid, label=label, detail=detail, action=alt.action,
       target_txn_id=txn.id, freed_cents=freed, effective_date=txn.date,
       recharge_date=recharge, lead_time_days=alt.lead_time_days, pain=alt.pain)` —
       validators run here; a defer without a recharge is impossible by construction and
       would raise anyway.
     - `pool.append((k, alt.pain, -freed, cid, candidate))`; `emitted_any = True`.
   - if not `emitted_any` and category is changeable → `not_actionable.append(txn.id)`.
3. `pool.sort(key=lambda t: t[:4])`; `truncated = len(pool) > req.limit`; `chosen =
   [t[4] for t in pool[: req.limit]]`.
4. Dedupe labels on `chosen` (a `Counter` of labels; for each label with count > 1,
   rewrite every holder with `" on {short_date(effective)}"`; recount; then `"
   ({money(freed)})"`; recount; then `" (#{n})"` where `n` is the 1-based position of the
   holder among its duplicates in `(effective_date, id)` order — **never** the
   transaction id, which is caller text and could carry a banned word into
   `certificate.sentence`). Rebuild each rewritten
   candidate with `c.model_copy(update={"label": new})` — `model_copy` does not
   re-validate, which is fine because only `label` changes and `label` has no validator.
5. `chosen.sort(key=lambda c: (c.effective_date, c.id))` — plain code-point order, the
   same key as `assemble.plan_sort_key`.
6. Self-check (a plain `if … raise RuntimeError("candidate generator invariant: …")`,
   never `assert`, so `-O` cannot strip it): ids unique; every `len(id) <= 64`; every
   `freed <= abs(target amount)`; every `as_of <= effective_date <= horizon_end`; every
   defer has `recharge_date > effective_date`; labels unique.
7. Return `CandidatesResponse(candidates=chosen, meta=CandidatesMeta(rows_considered=
   considered, protected=sorted(protected), unrecognised=sorted(unrecognised),
   not_actionable=sorted(not_actionable), truncated=truncated))`.

Helpers:

```python
def _candidate_id(txn_id: str, action: str) -> str:
    plain = f"{txn_id}.{action}"
    if len(plain) <= 64:
        return plain
    h = hashlib.sha1(txn_id.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"{txn_id[:40]}.{action}.{h}"   # 40 + 1 + 9 + 1 + 12 = 63 at the longest action
```

`_label`: look up `LABELS[(category, action)]`, format with `brand=m.display`,
`date=short_date(txn.date)`, `recharge=short_date(recharge)` where present. `_detail`:
`f"{txn.description}, {money(abs(txn.amount_cents))}"` + suffixes per policy;
`remaining = abs(amount) - freed`.

## Step 5 — `backend/app/main.py`

5a. Line 18: `from app.candidates import generate` goes **before** the `app.schemas`
import (alphabetical); extend line 18's schemas import with `CandidatesRequest,
CandidatesResponse`.

5b. Insert after line 49 (the end of `api_solve`), before the mount comment at 51:

```python
    @app.post("/api/candidates", response_model=CandidatesResponse)
    def api_candidates(req: CandidatesRequest) -> CandidatesResponse:
        return generate(req)
```

5c. Line 52 comment: `… and the API would answer 404 for /health and 405 for /api/solve
and /api/candidates.`

## Step 6 — `backend/tests/fixtures/accounts.py`

Seeded generator of realistic windows, in the voice of `tests/gen.py`:

- `MERCHANTS: tuple[tuple[str, str, bool, int, int], ...]` — `(description, kind,
  recurring, lo_cents, hi_cents)`, ~36 rows covering every changeable category, every
  protected category, two unknowns (one `bill`, one `discretionary`), the false-positive
  strings from the risk review, a unicode description, and the demo's own strings.
- `window(rng) -> dict` with `as_of`, `horizon_end` (14–45 days), `scheduled`: positive
  weekly or biweekly `PAYROLL` income; 4–24 outflow rows drawn from `MERCHANTS` with
  amounts in range; sometimes a negative income row (clawback); sometimes a row before
  `as_of` and one after `horizon_end`; sometimes two rows with identical description,
  date and amount (ids differ).
- `windows(n, seed=20260919)`.
- `solve_request(win, candidates, opening=None, buffer=2500, locks=None, previous=None)
  -> dict` — splices generated candidates into a full `SolveRequest` dict; `opening`
  defaults to the do-nothing trough plus a small offset, copied from `gen.py`'s
  `_opening_for_mixed_tiers` idea so tiers 2 and 3 get exercised, **clamped to
  `[-CENTS_ABS, CENTS_ABS]`** — 2000 rows at `-CENTS_ABS` put the trough near `-2×10^14`,
  far outside the `10^11` input bound, and an unclamped default would 422 the every-cap
  case on `opening_balance_cents` before it reached the solver.

## Step 7 — `backend/tests/test_candidates_classify.py` (~35 tests)

- `normalise`: exact token sequences — `KROGER #382` → `("KROGER", "382")`, `kroger
  0382` → `("KROGER", "0382")`, `KROGER*382` → `("KROGER", "382")`, `APPLE.COM/BILL` →
  `("APPLE", "COM", "BILL")`, `GOLD'S GYM` → `("GOLD", "S", "GYM")`; then a separate
  test that all four Kroger spellings **classify** identically (groceries) — the tokens
  differ, the category must not; empty, whitespace, `"Café ☕"` → no exception.
- `MERCHANT_TABLE` (~40 rows, `(description, expected_category)`) including every string
  in the run spec's AC8 list with its *intended* category — `SAM'S CLUB #6314` →
  groceries, `GAP INSURANCE PREMIUM` → insurance, `MARKET ST PROPERTIES` → housing,
  `WATER ST TAVERN` → restaurant, `CORE POWER YOGA` → gym, `TARGET OPTICAL` → medical,
  `FUEL FITNESS` → gym, `GUARANTEED RATE` → housing — the demo's 15 descriptions, `HARRIS TEETER
  PAYROLL` → groceries (classification is kind-blind; the generator's kind filter is
  tested in step 8), `GYMBOREE` → unknown, `UBER EATS` → food_delivery, `UBER TRIP` →
  rideshare, `AMAZON PRIME VIDEO` → streaming, `AMZN MKTP US*2K41Z` → shopping, `GAP
  INSURANCE PREMIUM` → insurance, `GAP OUTLET` → unknown, `SAM'S CLUB #6314` →
  groceries, `WATER ST TAVERN` → restaurant, `CORE POWER YOGA` → gym, `TARGET OPTICAL` →
  medical, `GUARANTEED RATE` → housing, `BP#9876543` → unknown, `SHELL SHACK` → unknown.
- Lexicon invariants as tests too (belt and braces over the import-time checks): no
  phrase in two categories; no generic single token; every category has a policy or is
  protected; `PRIORITY` starts with all of `PROTECTED`.
- Longest-phrase-wins at equal rank: a two-hit string within one category.
- `classify` is a pure function: 1000 calls on a shuffled table, same answers.

## Step 8 — `backend/tests/test_candidates_policy.py` (~50 tests)

Helper `gen(scheduled, as_of="2026-09-19", horizon_end="2026-10-02", limit=18)` builds a
`CandidatesRequest` and returns `generate(...)`. Row helper `row(id, date, desc, cents,
kind="discretionary", recurring=False)`.

- Pre-filter, one test per filter, each with the positive twin so removing the filter
  fails exactly one: income row with a grocery description → nothing and not considered;
  negative income row → nothing; positive discretionary (refund) → nothing; zero amount
  → nothing; row on `as_of - 1` → nothing; row on `horizon_end + 1` → nothing; rows on
  `as_of` and on `horizon_end` → offered.
- Protected: one test per protected category → nothing and listed in `meta.protected`.
  Unknown + bill → protected and unrecognised; unknown + discretionary → skip pain 3 and
  unrecognised.
- Recharge rule: no later payday → no defer, `not_actionable` if nothing else offered;
  payday same day → next payday; payday after horizon → no defer; only later income is
  negative → no defer; two paydays, earliest strictly after chosen; recharge >
  effective for every defer in 300 windows.
- Amounts: pct floor at 1, 2, 3, 99, 100, 101 cents for groceries (35 %) and fuel
  (50 %); 0-cent result drops only that alternative; `1 <= freed <= abs(amount)` over 300
  windows.
- Lead time: gym charge 3 days out → offered; 2 days out → `not_actionable`; streaming on
  `as_of + 1` → not offered (the demo's Spotify case).
- Ids: match `ID_RE`; 64-char txn id → valid, ≤ 64; two ids sharing a 60-char prefix →
  distinct; 2000 **60-char** ids sharing a 45-char prefix (so `txn_id[:40]` is identical
  for all and uniqueness rests on the 12-hex hash) → all unique; byte-identical on repeat;
  unchanged when an unrelated row is added; `_candidate_id("t_x", "downgrade")` exact
  string.
- Labels: no duplicates over 300 windows; two identical rows (desc, date, amount, different
  ids) → distinct labels via the ordinal suffix; same merchant two dates → `" on Sep 22"` /
  `" on Oct 1"`; unknown label is exactly `"Skip this charge"` and never contains the
  description; every label and every template suffix clear of `BANNED`, the judgmental
  list, `"None"`, `"$-"`, and never ends with `"."`; `GUARANTEED AUTO PROTECTION`
  (discretionary) → label clean, detail carries it verbatim; two identical rows with ids
  `guaranteed_1` / `guaranteed_2` → both labels still clean (the dedupe suffix never
  quotes the id).
- Details: contain `money(abs(amount))`; ` recurring` iff recurring; downgrade detail's
  `down to` figure equals `abs(amount) - freed`; non-defer `recharge_date is None`.
- Multi-occurrence: Netflix on two dates in a 45-day window → two candidates, distinct
  ids and labels, each freeing its own amount.
- Golden: the demo `SCHEDULED` → exactly the feature spec's table (ids, actions, freed,
  dates, recharge, lead, pain), `not_actionable == ["t_spotify"]`, `protected ==
  ["t_card", "t_verizon"]`, no candidate targets `t_card`, and
  `len(split(SolveRequest(…locks empty…)).free) <= MAX_FREE`.
- Meta identity over 300 windows, exactly as D2 defines it. Let `C` = ids passing the
  pre-filter (recomputed from the request), `P`, `NA`, `U` the meta lists, `O` = the
  target set of the returned candidates, `Cut = C − (P ∪ NA ∪ O)` (rows whose every
  alternative fell below the limit). Assert: `P`, `NA`, `O` pairwise disjoint; `U ∩ NA =
  ∅`; `U ⊆ P ∪ O ∪ Cut` (classification is pre-cap, so an unknown discretionary row the
  cap removed is still listed as unrecognised); `rows_considered == len(C)`; `Cut == ∅`
  iff `truncated` is false **or** every cut alternative belonged to a row that kept
  another (so `⊆`, never strict `⊂`). Two explicit cases Codex constructed: one grocery
  row with two alternatives at `limit=1` → `truncated=True`, `Cut=∅`, the row offered;
  two unknown discretionary rows at `limit=1` → `truncated=True`, one row in `Cut`, both
  in `U`.
- Rank and cap: 100 grocery rows **with a payday after all of them** (so each really has
  two alternatives) at `limit=60` → 60 distinct targets; default limit → 18; `truncated`
  true in both; shuffled input → identical output; 2000 rows → 18 by default and exactly
  60 at `limit=60`.
- Cross-process determinism: `subprocess.run([sys.executable, "-c", …], env={…,
  "PYTHONHASHSEED": "0"})` and `"1"`, each dumping `generate(...)` for 20 windows as
  sorted JSON; outputs byte-equal. Uses `sys.executable` (the venv) and `cwd=backend/`.

## Step 9 — `backend/tests/test_candidates_api.py` (~20 tests + 1 perf)

Own `client` and `client_with_site` fixtures (copies of `test_api.py:20–31`; existing
test files are not edited).

- 422 table, parametrised over `(mutation, expected_loc1)`: unknown field; float cents;
  malformed date; duplicate txn id; 400-day span; `horizon_end < as_of`; 2001 rows;
  `limit` 0, 61, `null`, `"18"`, `18.0`. Each asserts `loc[0] == "body"` and `loc[1]`.
- `limit` omitted → at most 18 and the demo returns 14.
- Empty `scheduled` → 200, `candidates == []`, `rows_considered == 0`.
- Every-cap: 2000 rows, 366-day window, amounts at `-CENTS_ABS` → 200, ≤ `limit` (this
  endpoint has no opening balance; the round-trip in step 10 passes an explicit
  `opening_balance_cents = CENTS_ABS`, the input bound, which lands deep in tier 3 and
  exercises the derived-figure bounds that finding F1 was about).
- Mount: `client_with_site.post("/api/candidates", …)` → 200 and `GET /` → 200.
- Response items each `Candidate.model_validate`; whole body `CandidatesResponse`.
- Two fresh `TestClient(create_app(None))` → identical bytes.
- `@pytest.mark.perf`: 2000 rows with 2 KB descriptions → print ms; assert < 2 s.

## Step 10 — `backend/tests/test_candidates_roundtrip.py` (~15 tests, some parametrised)

- `CASES`: demo ×3 (`SCENARIOS` windows with their presets), 300 `windows()`, the
  every-cap window. For each: generate → `solve_request(...)` →
  `SolveRequest.model_validate` succeeds → `POST /api/solve` 200.
- Engine agreement: brute force is 2^n × horizon — measured 2.7 s at 18 free over 14
  days and 5–9 s over 45. So the gate runs CP-SAT vs brute force on demo ×3 plus the
  first 50 windows **with `len(candidates) <= 14`** (≤ 0.2 s each); the full 300-window
  sweep at ≤ 18 is a `@pytest.mark.perf` case. Same `plan`, `tier`,
  `certificate.per_item` asserted.
- Oracle parity (`@requires_node`): demo ×3 + first 100 windows; assert `len(candidates)
  <= 18` before calling `oracle`; compare with **`test_parity.assert_agrees`**
  (`test_parity.py:55`), not bare `_normalise` — `assert_agrees` carries the one
  deliberate divergence, the tier-3 empty-plan certificate wording. Include one
  generated case that exercises it: a window whose rows are all protected (empty
  candidate set) with an opening below the trough → tier 3, empty plan.
- Invariants: `import tests.test_invariants as inv` — **never** `from … import test_x`,
  or pytest collects the imported name in this module where its `case` fixture does not
  exist — and call `inv.test_…((raw, res))` for 50 generated cases (the functions take
  the `(raw_dict, response_dict)` tuple directly; `test_invariants.py:69–72`).
- Lock survival: pick the first generated id, regenerate the same window → still present;
  solve with it in `locks.in` → in `plan`.
- Moving `as_of`: a window with a row dated exactly `as_of` (the demo has none on Sep
  19, so demo ×3 would pass vacuously); generate at `D`, validate the same candidates at
  `D + 1` → `ValidationError` naming `candidates` (`schemas.py:182` is the only check
  that fires). Pins D14c as documented behaviour.
- Generated sets never contain a recharge past `horizon_end` (so nobody later claims they
  cover that solver path; `gen.py` does).

## Step 11 — docs and in-code pointers (doc-sync, before commit)

- `docs/api-contract.md`: line 1 → `` # API contract — `POST /api/solve` and `POST /api/candidates` ``;
  lines 3–6 may gain one sentence but the file must keep the same number of lines above
  line 8; append after line 160 a `` ## `POST /api/candidates` `` section: request,
  response, `limit` semantics, `meta` identity, the three client rules (same `as_of`,
  re-fetch on change, prune locks), 200/422 shapes. Verify: `diff <(git show
  HEAD:docs/api-contract.md | sed -n 8,160p) <(sed -n 8,160p docs/api-contract.md)` is
  empty.
- `README.md:9–10` endpoint + package list; `:15` "the frozen `/api/solve` shape" →
  "the frozen request and response shapes".
- `CLAUDE.md:65` add `POST /api/candidates`.
- `docs/features/solver.md:18` point "candidate generation" at the feature doc; `:47`
  "(model constraint + validation)" → "(a search constraint in both engines — competing
  candidates on one transaction are legal input, and `docs/features/candidates.md` emits
  them on purpose)"; `:106` link; `:116` "(data-prep layer's job)" → "(the generator
  does this: one candidate per occurrence, see `candidates.md`)".
- `docs/features/candidates.md`: fill the golden table from the real run if any figure
  differs (it should not — the table was worked by hand — but if it does, the *test*
  is right only after the arithmetic is re-checked by hand, not by copying the output).
- Run spec: append `## Results` with counts, timings, test names per AC (AC table →
  test function names), and the three review verdicts.

## Step 12 — verify, commit, audit

```bash
.venv/bin/pytest backend/tests/test_candidates_classify.py backend/tests/test_candidates_policy.py backend/tests/test_candidates_api.py backend/tests/test_candidates_roundtrip.py -q -m "not perf"
.venv/bin/pytest backend/ -q -m "not perf"          # expect 977 + N, N >= 80
.venv/bin/pytest backend/ -m perf -q -s              # 7 perf cases reported
git diff --stat HEAD -- backend/tests frontend backend/requirements.txt   # must be empty
git status --short -- backend/tests                                      # only the five new ?? paths
```

Commit in three, each with explicit paths: (1) schemas + candidates package + main;
(2) tests + fixture; (3) docs. Then the post-commit critique loop and the Codex audit
per the pipeline.

## Risks and mitigations (from the risk agent, with what the plan does about each)

| # | Risk | Where handled |
|---|---|---|
| R1 | Oracle refuses > 20 free; exponential | `limit` default 18 (1d); parity asserts ≤ 18 before calling (10) |
| R2 | "free" = everything emitted with empty locks | golden test asserts `split().free` (8); default limit = `MAX_FREE` |
| R3 | 503 leaks cap; browser fallback throws unhandled > 20 | unreachable at default limit; D14a/b pointers to the other lanes |
| R4 | Generator bug → 500 here, 422 there | `Candidate(...)` validators + self-check (4.6) + round-trip over 300 windows (10) |
| R5 | Id fallback at exactly 64; sha1 collisions; FIPS | prefix 40 + 12 hex = 63; `usedforsecurity=False`; uniqueness self-check; shared-prefix tests (8) |
| R6 | Unbounded description × phrases | first-token index (2b); perf test with 2 KB descriptions (9) |
| R7 | Set iteration → brand varies by hash seed | tuples only; two-subprocess `PYTHONHASHSEED` test (8) |
| R8 | Generic tokens misclassify | protected first; `_GENERIC` import-time rule; 40-row table with the named negatives (7) |
| R9 | Negative income as payday | `amount_cents > 0` in payday list (4.1); test (8) |
| R10 | Reordered fields silently skip the span check | same order, shared helpers (1d); 422 tests for backwards and 400-day (9) |
| R11 | Route below the mount, no test notices | inserted at 50 (5b); mount test (9) |
| R12 | Vanished lock id → 422 → silent client fallback | contract client rules (11); lock-survival + as_of+1 tests (10) |
| R13 | Cached candidates vs moving `as_of` | contract rule; documented 422 test (10) |
| R14 | No TS-parity for new models | D14d pointer; not fixable from this lane |
| R15 | `meta` identity ambiguous | D2 definition; partition test (8) |
| R16 | Same-action alternatives collide ids | policy invariant (3) + generator uniqueness (4.6) |
| R17 | Dedupe O(N²) and incomplete | after the cap, `Counter`, ordinal as final suffix (4.4) |
| R18 | Raw description in a label reaches prose | fixed unknown label; banned-word tests on labels + suffixes (8) |
| R19 | Generated set weaker than fixture | documented (D4, feature spec); demo not switched |
| R20 | Past-horizon recharge never exercised by generated sets | explicit test that they never occur + note (10) |
