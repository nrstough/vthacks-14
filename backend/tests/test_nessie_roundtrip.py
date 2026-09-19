"""The Nessie round trip: seed an account, read it back, report what changed.

Everything here is stubbed against a scripted sandbox. The one test that touches
the live service carries `@pytest.mark.nessie` and is deselected by default
(pytest.ini's addopts and, because a command-line `-m` replaces rather than
extends addopts, conftest's collection hook as well).

The scripted sandbox is not a mock of the happy path. It exists to make the
sandbox misbehave on purpose, because every interesting failure here is one that
answers 200: a wrong key returns an empty list, writes truncate to whole dollars,
and the balance never moves. Those are the behaviours worth pinning.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse

import pytest

import app.chat.gemini as gemini
import app.nessie.client as client
from fastapi.testclient import TestClient

from app.main import create_app
from app.nessie import NessieUnavailable, NessieUpstreamError
from app.nessie.client import NessieConfig
from app.nessie.roundtrip import (
    account_from_nessie,
    dollars,
    parse_nickname,
    read_back,
    round_to_dollars,
    seed_and_read_back,
    seeded_account,
)
from app.schemas import (
    CandidatesRequest,
    NessieAccountResponse,
    SampleAccountRequest,
    SolveRequest,
)
from tests.test_nessie import FakeResponse, http_error

CFG = NessieConfig(api_key="k" * 32, base_url="https://example.invalid")
SEED = 20260919  # a seed whose account carries all three row kinds


class Sandbox:
    """A scripted Nessie. Records every write; answers reads from them.

    Knobs exist for each way the real service is known or suspected to deviate.
    Nothing here is a guess about HTTP; the shapes come from the measured probe.
    """

    def __init__(
        self,
        *,
        drop_ids=(),
        change_amount=None,
        omit_date_ids=(),
        bad_date_ids=(),
        move_date_ids=None,
        fail_at=None,
        empty_reads=False,
        string_customer=False,
        no_id_customer=False,
        bad_list=None,
        string_row=False,
        html_body=False,
        nickname=None,
        balance=None,
        account_id="acc_0",
        missing_account=False,
    ) -> None:
        self.drop_ids = set(drop_ids)
        self.change_amount = change_amount or {}
        self.omit_date_ids = set(omit_date_ids)
        self.bad_date_ids = set(bad_date_ids)
        self.move_date_ids = move_date_ids or {}
        self.fail_at = fail_at
        self.empty_reads = empty_reads
        self.string_customer = string_customer
        self.no_id_customer = no_id_customer
        self.bad_list = bad_list
        self.string_row = string_row
        self.html_body = html_body
        self.nickname = nickname
        self.balance = balance
        self.account_id = account_id
        self.missing_account = missing_account
        self.calls: list[tuple[str, str, dict | None]] = []
        self.rows: dict[str, list[dict]] = {"deposits": [], "withdrawals": [], "bills": []}
        self.n = 0

    def _next_id(self) -> str:
        self.n += 1
        return f"{self.n:024d}"

    def __call__(self, req, timeout=None):
        method = req.get_method()
        # Parse rather than strip a known host: the route builds its config from
        # the environment, so the base URL is not always the test's.
        path = urllib.parse.urlsplit(req.full_url).path
        body = json.loads(req.data.decode()) if req.data else None
        self.calls.append((method, path, body))

        if method == "POST":
            return self._post(path, body)
        return self._get(path)

    def _post(self, path, body):
        if path == "/customers":
            if self.string_customer:
                return FakeResponse("Customer created")
            if self.no_id_customer:
                return FakeResponse({"code": 201})
            return FakeResponse({"code": 201, "objectCreated": {"_id": "cust_0"}})
        if path.endswith("/accounts"):
            return FakeResponse({"code": 201, "objectCreated": {"_id": self.account_id}})

        kind = path.rsplit("/", 1)[-1]
        written = len(self.rows["deposits"]) + len(self.rows["withdrawals"]) + len(self.rows["bills"])
        if self.fail_at is not None and written + 1 == self.fail_at:
            raise http_error(503, {"message": "sandbox wobbled"})
        ident = self._next_id()
        stored = dict(body)
        stored["_id"] = ident
        self.rows[kind].append(stored)
        return FakeResponse({"code": 201, "objectCreated": {"_id": ident}})

    def _get(self, path):
        if self.html_body:
            return FakeResponse("<html>down for maintenance</html>")
        if path.startswith("/accounts/") and path.rsplit("/", 1)[-1] not in self.rows:
            if self.missing_account:
                return FakeResponse([])
            account = {
                "_id": self.account_id,
                "type": "Checking",
                "customer_id": "cust_0",
                "nickname": self.nickname if self.nickname is not None else "Demo Checking",
                "balance": self.balance if self.balance is not None else 498,
            }
            return FakeResponse(account)

        kind = path.rsplit("/", 1)[-1]
        if self.empty_reads:
            return FakeResponse([])
        if self.bad_list == kind:
            return FakeResponse({"not": "a list"})
        if self.string_row and self.rows[kind]:
            return FakeResponse(["just a string"])

        out = []
        for row in self.rows[kind]:
            ident = f"n_{row['_id']}"
            if ident in self.drop_ids:
                continue
            copy = dict(row)
            if ident in self.change_amount:
                field = "payment_amount" if kind == "bills" else "amount"
                copy[field] = self.change_amount[ident]
            if ident in self.omit_date_ids:
                copy.pop("transaction_date", None)
                copy.pop("payment_date", None)
            if ident in self.bad_date_ids:
                field = "payment_date" if kind == "bills" else "transaction_date"
                copy[field] = "2026-13-40"
            if ident in self.move_date_ids:
                field = "payment_date" if kind == "bills" else "transaction_date"
                copy[field] = self.move_date_ids[ident]
            out.append(copy)
        return FakeResponse(out)


def install(monkeypatch, sandbox: Sandbox) -> Sandbox:
    monkeypatch.setattr(client.urllib.request, "urlopen", sandbox)
    return sandbox


def explode(*_a, **_k):
    raise AssertionError("the network must not be touched")


# ---- rounding, the seed boundary ----


def test_rounding_is_half_away_from_zero():
    assert round_to_dollars(-1999) == -2000
    assert round_to_dollars(-1950) == -2000
    assert round_to_dollars(-1949) == -1900
    assert round_to_dollars(1950) == 2000
    assert round_to_dollars(1949) == 1900


def test_rounding_keeps_zero_and_sign():
    assert round_to_dollars(0) == 0
    assert round_to_dollars(-50) == -100
    assert round_to_dollars(49) == 0


def test_dollars_is_a_nonnegative_integer_never_a_float():
    """A float here would reintroduce exactly the error to_cents exists to stop."""
    for cents in (-1999, 0, 19892, 31240):
        assert type(dollars(cents)) is int
        assert dollars(cents) >= 0


def test_the_seeded_account_is_whole_dollars_throughout():
    account = seeded_account(seed=SEED, horizon_days=30)
    assert account["scheduled"], "a seed with no rows would make every loop below vacuous"
    assert account["opening_balance_cents"] % 100 == 0
    for row in account["scheduled"]:
        assert row["amount_cents"] % 100 == 0


def test_the_seeded_account_still_carries_all_three_kinds():
    kinds = {r["kind"] for r in seeded_account(seed=SEED, horizon_days=30)["scheduled"]}
    assert kinds == {"income", "bill", "discretionary"}


# ---- the nickname, which is how read-only mode learns its window ----


def test_a_nickname_round_trips_the_seed_and_the_window():
    assert parse_nickname("og 7 2026-09-19 2026-10-18") == (7, "2026-09-19", "2026-10-18")


def test_a_nickname_that_is_not_ours_is_not_guessed_at():
    assert parse_nickname("Demo Checking") is None
    assert parse_nickname("og x 2026-09-19 2026-10-18") is None
    assert parse_nickname("og 7 2026-13-40 2026-10-18") is None
    assert parse_nickname(None) is None
    assert parse_nickname(12) is None


# ---- seeding against a faithful sandbox ----


@pytest.fixture
def seeded(monkeypatch):
    box = install(monkeypatch, Sandbox())
    account = seeded_account(seed=SEED, horizon_days=30)
    return account, box, seed_and_read_back(account, CFG)


def test_one_write_per_row_plus_the_customer_and_the_account(seeded):
    account, box, _ = seeded
    posts = [c for c in box.calls if c[0] == "POST"]
    assert len(posts) == 2 + len(account["scheduled"])


def test_the_customer_is_named_so_nobody_mistakes_it_for_a_person(seeded):
    _, box, _ = seeded
    body = box.calls[0][2]
    assert body["first_name"] == "Modelled" and body["last_name"] == "Account"


def test_the_account_carries_the_seed_window_in_its_nickname(seeded):
    account, box, _ = seeded
    body = next(c[2] for c in box.calls if c[1].endswith("/accounts"))
    assert body["nickname"] == f"og {SEED} {account['as_of']} {account['horizon_end']}"
    assert body["type"] == "Checking"
    assert body["balance"] == account["opening_balance_cents"] // 100


def test_every_row_goes_to_the_resource_its_kind_dictates(seeded):
    account, box, _ = seeded
    counts = {"deposits": 0, "withdrawals": 0, "bills": 0}
    for method, path, _body in box.calls:
        if method == "POST" and "/accounts/" in path and not path.endswith("/accounts"):
            counts[path.rsplit("/", 1)[-1]] += 1
    wanted = {"deposits": 0, "withdrawals": 0, "bills": 0}
    for row in account["scheduled"]:
        wanted[{"income": "deposits", "discretionary": "withdrawals", "bill": "bills"}[row["kind"]]] += 1
    assert all(v > 0 for v in wanted.values()), "the seed must exercise all three paths"
    assert counts == wanted


def test_every_amount_on_the_wire_is_a_json_integer(seeded):
    """Nessie truncates a decimal silently. Sending one is how cents vanish."""
    _, box, _ = seeded
    seen = 0
    for _method, _path, body in box.calls:
        if not body:
            continue
        for field in ("amount", "payment_amount", "balance"):
            if field in body:
                assert type(body[field]) is int, (field, body[field])
                seen += 1
    assert seen > 0


def test_every_bill_carries_a_payment_date_and_a_recurring_day(seeded):
    """payment_date is optional to Nessie; without it the row reads back with no
    date and 422s the caller's own next request."""
    _, box, _ = seeded
    bills = [b for m, p, b in box.calls if m == "POST" and p.endswith("/bills")]
    assert bills
    for body in bills:
        assert body["payment_date"]
        assert 1 <= body["recurring_date"] <= 31


def test_a_faithful_sandbox_loses_nothing(seeded):
    account, _, out = seeded
    assert out["source"] == "nessie"
    assert out["nessie"]["mode"] == "seeded"
    assert out["not_round_tripped"] == []
    assert out["written"] == len(account["scheduled"])
    assert out["returned"] == len(account["scheduled"])


def test_every_returned_amount_equals_what_was_written(seeded):
    account, _, out = seeded
    assert out["scheduled"], "an empty schedule would make this loop vacuous"
    by_amount = sorted(abs(r["amount_cents"]) for r in out["scheduled"])
    assert by_amount == sorted(abs(r["amount_cents"]) for r in account["scheduled"])


def test_income_stays_positive_and_charges_stay_negative(seeded):
    _, _, out = seeded
    kinds = {r["kind"] for r in out["scheduled"]}
    assert kinds == {"income", "bill", "discretionary"}
    for row in out["scheduled"]:
        assert (row["amount_cents"] > 0) == (row["kind"] == "income")


def test_ids_are_unique_and_derived_from_the_sandbox(seeded):
    _, _, out = seeded
    ids = [r["id"] for r in out["scheduled"]]
    assert len(set(ids)) == len(ids)
    assert all(i.startswith("n_") for i in ids)


def test_rows_come_back_sorted_because_read_order_is_unverified(seeded):
    _, _, out = seeded
    assert out["scheduled"] == sorted(out["scheduled"], key=lambda r: (r["date"], r["id"]))


def test_every_row_lands_inside_the_window(seeded):
    account, _, out = seeded
    for row in out["scheduled"]:
        assert account["as_of"] <= row["date"] <= account["horizon_end"]


def test_the_opening_balance_is_never_read_back_from_the_sandbox(monkeypatch):
    """Writes never move Nessie's balance, so reading it would report an input
    as though the sandbox had computed it."""
    install(monkeypatch, Sandbox(balance=999999))
    account = seeded_account(seed=SEED, horizon_days=30)
    out = seed_and_read_back(account, CFG)
    assert out["opening_balance_cents"] == account["opening_balance_cents"]


def test_the_same_seed_writes_the_same_bodies(monkeypatch):
    box1 = install(monkeypatch, Sandbox())
    seed_and_read_back(seeded_account(seed=SEED, horizon_days=30), CFG)
    box2 = install(monkeypatch, Sandbox())
    seed_and_read_back(seeded_account(seed=SEED, horizon_days=30), CFG)
    assert box1.calls == box2.calls


# ---- failures that do not look like failures ----


def test_no_key_never_reaches_the_network(monkeypatch):
    monkeypatch.setattr(client.urllib.request, "urlopen", explode)
    req = SampleAccountRequest.model_validate({})
    with pytest.raises(NessieUnavailable):
        account_from_nessie(req, NessieConfig(api_key=None))


def test_no_key_in_read_only_mode_also_never_reaches_the_network(monkeypatch):
    """Read-only mode calls out too; without this check it would surface as a
    generic 502 rather than 'not set up on this server'."""
    monkeypatch.setattr(client.urllib.request, "urlopen", explode)
    req = SampleAccountRequest.model_validate({})
    with pytest.raises(NessieUnavailable):
        account_from_nessie(req, NessieConfig(api_key=None, account_id="acc_0"))


def test_a_customer_create_with_no_id_stops_before_anything_else_is_written(monkeypatch):
    box = install(monkeypatch, Sandbox(no_id_customer=True))
    with pytest.raises(NessieUpstreamError):
        seed_and_read_back(seeded_account(seed=SEED), CFG)
    assert len(box.calls) == 1


def test_a_create_that_answers_a_bare_string_is_an_upstream_error_not_a_crash(monkeypatch):
    """The published docs claim creates answer with a string. Measured they do
    not, but an AttributeError here would be a 500 with a stack trace."""
    install(monkeypatch, Sandbox(string_customer=True))
    with pytest.raises(NessieUpstreamError):
        seed_and_read_back(seeded_account(seed=SEED), CFG)


def test_a_failure_mid_seed_says_how_much_already_exists(monkeypatch):
    """Creates are permanent, so 'it failed' is not actionable on its own."""
    install(monkeypatch, Sandbox(fail_at=7))
    with pytest.raises(NessieUpstreamError) as e:
        seed_and_read_back(seeded_account(seed=SEED, horizon_days=30), CFG)
    assert "6 of" in str(e.value)


def test_the_key_never_appears_in_a_mid_seed_failure(monkeypatch):
    install(monkeypatch, Sandbox(fail_at=7))
    with pytest.raises(NessieUpstreamError) as e:
        seed_and_read_back(seeded_account(seed=SEED, horizon_days=30), CFG)
    assert "k" * 32 not in str(e.value)


def test_an_upstream_message_carrying_the_key_is_scrubbed(monkeypatch):
    def fake(*_a, **_k):
        raise http_error(500, {"message": f"failed for /customers?key={'k' * 32}"})

    monkeypatch.setattr(client.urllib.request, "urlopen", fake)
    with pytest.raises(NessieUpstreamError) as e:
        seed_and_read_back(seeded_account(seed=SEED), CFG)
    assert "k" * 32 not in str(e.value)
    assert "<redacted>" in str(e.value)


def test_a_network_error_carrying_the_key_is_scrubbed(monkeypatch):
    def fake(*_a, **_k):
        raise urllib.error.URLError(f"tried https://example.invalid/customers?key={'k' * 32}")

    monkeypatch.setattr(client.urllib.request, "urlopen", fake)
    with pytest.raises(NessieUpstreamError) as e:
        seed_and_read_back(seeded_account(seed=SEED), CFG)
    assert "k" * 32 not in str(e.value)


def test_a_non_json_body_is_an_upstream_error_not_a_five_hundred(monkeypatch):
    install(monkeypatch, Sandbox(html_body=True))
    with pytest.raises(NessieUpstreamError):
        seed_and_read_back(seeded_account(seed=SEED), CFG)


def test_a_malformed_list_is_refused(monkeypatch):
    install(monkeypatch, Sandbox(bad_list="deposits"))
    with pytest.raises(NessieUpstreamError):
        seed_and_read_back(seeded_account(seed=SEED), CFG)


def test_a_row_that_is_not_an_object_is_refused(monkeypatch):
    install(monkeypatch, Sandbox(string_row=True))
    with pytest.raises(NessieUpstreamError):
        seed_and_read_back(seeded_account(seed=SEED), CFG)


def test_reads_that_come_back_empty_are_unverified_never_an_empty_account(monkeypatch):
    """A wrong key answers 200 with an empty list, exactly as a real but empty
    account does. Rendering that would show a judge a blank screen as data."""
    install(monkeypatch, Sandbox(empty_reads=True))
    with pytest.raises(NessieUnavailable):
        seed_and_read_back(seeded_account(seed=SEED), CFG)


# ---- what the sandbox changed, reported rather than hidden ----


def _ids_by_reason(out, reason):
    return {p["id"] for p in out["not_round_tripped"] if p["reason"] == reason}


def test_a_row_written_but_not_returned_is_named(monkeypatch):
    box = install(monkeypatch, Sandbox())
    account = seeded_account(seed=SEED, horizon_days=30)
    seed_and_read_back(account, CFG)  # populate to learn a real id
    victim = f"n_{box.rows['withdrawals'][0]['_id']}"

    install(monkeypatch, Sandbox(drop_ids={victim}))
    out = seed_and_read_back(account, CFG)
    assert _ids_by_reason(out, "written but not returned") == {victim}
    assert out["returned"] == len(out["scheduled"]) == out["written"] - 1


def test_an_amount_the_sandbox_changed_is_named_and_the_sandbox_value_is_kept(monkeypatch):
    box = install(monkeypatch, Sandbox())
    account = seeded_account(seed=SEED, horizon_days=30)
    seed_and_read_back(account, CFG)
    victim = f"n_{box.rows['withdrawals'][0]['_id']}"

    install(monkeypatch, Sandbox(change_amount={victim: 3}))
    out = seed_and_read_back(account, CFG)
    assert _ids_by_reason(out, "amount changed by the sandbox") == {victim}
    row = next(r for r in out["scheduled"] if r["id"] == victim)
    assert abs(row["amount_cents"]) == 300


def test_a_row_with_no_date_is_dropped_and_named(monkeypatch):
    box = install(monkeypatch, Sandbox())
    account = seeded_account(seed=SEED, horizon_days=30)
    seed_and_read_back(account, CFG)
    victim = f"n_{box.rows['deposits'][0]['_id']}"

    install(monkeypatch, Sandbox(omit_date_ids={victim}))
    out = seed_and_read_back(account, CFG)
    assert _ids_by_reason(out, "no usable date") == {victim}
    assert all(r["id"] != victim for r in out["scheduled"])
    assert all(r["date"] for r in out["scheduled"])


def test_a_row_with_an_impossible_date_is_dropped_and_named(monkeypatch):
    box = install(monkeypatch, Sandbox())
    account = seeded_account(seed=SEED, horizon_days=30)
    seed_and_read_back(account, CFG)
    victim = f"n_{box.rows['bills'][0]['_id']}"

    install(monkeypatch, Sandbox(bad_date_ids={victim}))
    out = seed_and_read_back(account, CFG)
    assert _ids_by_reason(out, "no usable date") == {victim}


def test_a_row_moved_outside_the_window_is_dropped_and_named(monkeypatch):
    """The generator and both solvers drop these silently; silence is what makes
    a short plan look like a wrong one."""
    box = install(monkeypatch, Sandbox())
    account = seeded_account(seed=SEED, horizon_days=30)
    seed_and_read_back(account, CFG)
    victim = f"n_{box.rows['withdrawals'][0]['_id']}"

    install(monkeypatch, Sandbox(move_date_ids={victim: "2027-01-01"}))
    out = seed_and_read_back(account, CFG)
    assert _ids_by_reason(out, "outside the window") == {victim}
    assert all(r["id"] != victim for r in out["scheduled"])


def test_a_row_is_reported_once_even_when_two_things_are_wrong(monkeypatch):
    box = install(monkeypatch, Sandbox())
    account = seeded_account(seed=SEED, horizon_days=30)
    seed_and_read_back(account, CFG)
    victim = f"n_{box.rows['withdrawals'][0]['_id']}"

    install(monkeypatch, Sandbox(omit_date_ids={victim}, change_amount={victim: 3}))
    out = seed_and_read_back(account, CFG)
    ids = [p["id"] for p in out["not_round_tripped"]]
    assert ids.count(victim) == 1
    assert _ids_by_reason(out, "no usable date") == {victim}


def test_rows_that_all_lack_dates_are_unverified_not_an_empty_account(monkeypatch):
    """Non-empty lists pass the empty-read check and can still normalise to
    nothing. An empty account must not be reachable by that route either."""
    box = install(monkeypatch, Sandbox())
    account = seeded_account(seed=SEED, horizon_days=30)
    seed_and_read_back(account, CFG)
    everything = {
        f"n_{row['_id']}" for rows in box.rows.values() for row in rows
    }

    install(monkeypatch, Sandbox(omit_date_ids=everything))
    with pytest.raises(NessieUnavailable):
        seed_and_read_back(account, CFG)


# ---- read-only mode ----


def _seed_then_read_only(monkeypatch, **knobs):
    box = install(monkeypatch, Sandbox(**knobs))
    seed_and_read_back(seeded_account(seed=SEED, horizon_days=30), CFG)
    box.calls.clear()
    return box


def test_read_only_mode_writes_nothing(monkeypatch):
    box = _seed_then_read_only(monkeypatch, nickname=f"og {SEED} 2026-09-19 2026-10-18")
    out = read_back("acc_0", CFG, as_of="2026-09-19", horizon_end="2026-10-18")
    assert all(method == "GET" for method, _p, _b in box.calls)
    assert out["written"] == 0
    assert out["nessie"]["mode"] == "read_only"
    assert out["returned"] == len(out["scheduled"])


def test_read_only_takes_its_window_from_the_nickname(monkeypatch):
    """The rows and the frozen balance belong to the seeded window. Honouring
    the request's window instead would drop every row outside it."""
    _seed_then_read_only(monkeypatch, nickname="og 7 2026-09-19 2026-10-18")
    out = read_back("acc_0", CFG, as_of="2030-01-01", horizon_end="2030-01-30")
    assert out["seed"] == 7
    assert out["as_of"] == "2026-09-19"
    assert out["horizon_end"] == "2026-10-18"


def test_read_only_falls_back_to_the_requested_window_when_the_nickname_is_not_ours(monkeypatch):
    _seed_then_read_only(monkeypatch, nickname="Demo Checking")
    out = read_back("acc_0", CFG, as_of="2026-09-19", horizon_end="2026-10-18")
    assert out["seed"] == 0
    assert out["as_of"] == "2026-09-19"


def test_read_only_uses_the_frozen_creation_balance(monkeypatch):
    _seed_then_read_only(monkeypatch, nickname="Demo Checking", balance=498)
    out = read_back("acc_0", CFG, as_of="2026-09-19", horizon_end="2026-10-18")
    assert out["opening_balance_cents"] == 49800


def test_read_only_refuses_an_account_that_does_not_read_back(monkeypatch):
    _seed_then_read_only(monkeypatch, missing_account=True)
    with pytest.raises(NessieUnavailable):
        read_back("acc_0", CFG, as_of="2026-09-19", horizon_end="2026-10-18")


def test_read_only_refuses_an_account_whose_id_does_not_match(monkeypatch):
    install(monkeypatch, Sandbox(account_id="other"))
    with pytest.raises(NessieUnavailable):
        read_back("acc_0", CFG, as_of="2026-09-19", horizon_end="2026-10-18")


def test_read_only_refuses_an_account_with_nothing_in_it(monkeypatch):
    install(monkeypatch, Sandbox(empty_reads=True))
    with pytest.raises(NessieUnavailable):
        read_back("acc_0", CFG, as_of="2026-09-19", horizon_end="2026-10-18")


def test_read_only_refuses_when_no_row_has_a_usable_date(monkeypatch):
    box = _seed_then_read_only(monkeypatch, nickname="Demo Checking")
    everything = {f"n_{row['_id']}" for rows in box.rows.values() for row in rows}
    box.omit_date_ids = everything
    with pytest.raises(NessieUnavailable):
        read_back("acc_0", CFG, as_of="2026-09-19", horizon_end="2026-10-18")


def test_the_account_id_sends_the_route_down_the_read_only_path(monkeypatch):
    box = install(monkeypatch, Sandbox(nickname=f"og {SEED} 2026-09-19 2026-10-18"))
    seed_and_read_back(seeded_account(seed=SEED, horizon_days=30), CFG)
    box.calls.clear()
    cfg = NessieConfig(api_key="k" * 32, base_url="https://example.invalid", account_id="acc_0")
    out = account_from_nessie(SampleAccountRequest.model_validate({}), cfg)
    assert out["nessie"]["mode"] == "read_only"
    assert all(method == "GET" for method, _p, _b in box.calls)


# ---- the contract the client depends on ----


def test_the_response_validates_as_its_own_model(seeded):
    _, _, out = seeded
    NessieAccountResponse.model_validate(out)


def test_the_response_splits_into_the_two_requests_the_client_sends(seeded):
    """The response is not itself a request body: both request models forbid
    extras, so the client has to pick fields. This is that pick."""
    _, _, out = seeded
    CandidatesRequest.model_validate(
        {"as_of": out["as_of"], "horizon_end": out["horizon_end"], "scheduled": out["scheduled"], "limit": 18}
    )
    SolveRequest.model_validate(
        {
            "as_of": out["as_of"],
            "horizon_end": out["horizon_end"],
            "opening_balance_cents": out["opening_balance_cents"],
            "buffer_cents": out["buffer_cents"],
            "scheduled": out["scheduled"],
            "candidates": [],
            "locks": {"in": [], "out": []},
        }
    )


def test_a_round_tripped_account_still_produces_candidates(seeded):
    """Descriptors survive the sandbox and still classify; an account that came
    back unrecognisable would solve to an empty plan for no visible reason."""
    from app.candidates import generate

    _, _, out = seeded
    res = generate(
        CandidatesRequest.model_validate(
            {"as_of": out["as_of"], "horizon_end": out["horizon_end"], "scheduled": out["scheduled"]}
        )
    )
    assert len(res.candidates) > 0


# ---- wording ----


def test_no_new_string_breaks_the_wording_rules():
    """CLAUDE.md: "infeasible" never reaches the user, nothing is "guaranteed",
    and sandbox data is never called real bank data.

    Scoped to this module. `chat/prompt.py` is exempt by construction: it names
    both banned words in order to instruct the model never to use them, and its
    own account-source lines are checked in test_chat.py where they are built.
    """
    import pathlib

    import app.nessie.roundtrip as roundtrip_mod

    text = pathlib.Path(roundtrip_mod.__file__).read_text().lower()
    assert "infeasib" not in text
    assert "guarantee" not in text
    assert "real bank" not in text


# ---- the route ----


@pytest.fixture
def api(monkeypatch):
    """No key by default, and never a developer's .env: these tests must not
    depend on someone else's hackathon service being up."""
    monkeypatch.delenv("NESSIE_API_KEY", raising=False)
    monkeypatch.delenv("NESSIE_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(gemini, "_env_loaded", True)
    return TestClient(create_app(None))


@pytest.fixture
def api_with_site(monkeypatch, tmp_path_factory):
    monkeypatch.delenv("NESSIE_API_KEY", raising=False)
    monkeypatch.delenv("NESSIE_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(gemini, "_env_loaded", True)
    site = tmp_path_factory.mktemp("dist")
    (site / "index.html").write_text("<!doctype html><title>app</title>")
    (site / "app.js").write_text("console.log(1)")
    return TestClient(create_app(site))


def test_the_route_is_503_without_a_key(api, monkeypatch):
    monkeypatch.setattr(client.urllib.request, "urlopen", explode)
    r = api.post("/api/accounts/nessie", json={})
    assert r.status_code == 503
    assert isinstance(r.json()["detail"], str)


def test_the_route_answers_502_when_the_sandbox_fails(api, monkeypatch):
    monkeypatch.setenv("NESSIE_API_KEY", "k" * 32)
    install(monkeypatch, Sandbox(fail_at=7))
    r = api.post("/api/accounts/nessie", json={"seed": SEED})
    assert r.status_code == 502
    assert "k" * 32 not in r.text


def test_the_route_returns_an_account_that_says_where_it_came_from(api, monkeypatch):
    monkeypatch.setenv("NESSIE_API_KEY", "k" * 32)
    install(monkeypatch, Sandbox())
    r = api.post("/api/accounts/nessie", json={"seed": SEED})
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "nessie"


def test_the_route_is_not_shadowed_by_the_static_mount(api_with_site, monkeypatch):
    """A route registered below the StaticFiles mount answers 405, silently.
    main.py says so in a comment; every route gets this test."""
    monkeypatch.setattr(client.urllib.request, "urlopen", explode)
    r = api_with_site.post("/api/accounts/nessie", json={})
    assert r.status_code == 503, r.text  # reached the handler, not the mount
    assert r.status_code != 405


def test_the_route_forbids_unknown_fields(api):
    assert api.post("/api/accounts/nessie", json={"seed": 1, "extra": 1}).status_code == 422


def test_the_route_bounds_the_horizon(api):
    assert api.post("/api/accounts/nessie", json={"horizon_days": 46}).status_code == 422
    assert api.post("/api/accounts/nessie", json={"horizon_days": 13}).status_code == 422


# ---- the live sandbox, opt in with -m nessie ----


@pytest.mark.nessie
def test_the_live_sandbox_round_trips_an_account():
    config = NessieConfig.from_env()
    if not config.api_key:
        pytest.skip("no NESSIE_API_KEY configured")
    out = seed_and_read_back(seeded_account(seed=SEED, horizon_days=30), config)
    print(
        f"\nlive: customer={out['nessie']['customer_id']} account={out['nessie']['account_id']} "
        f"written={out['written']} returned={out['returned']} lost={out['not_round_tripped']}"
    )
    assert out["not_round_tripped"] == []
