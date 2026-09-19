"""The Nessie adapter.

Everything here is stubbed. The one test that touches the live sandbox is marked
`nessie` and is deselected by default (see pytest.ini) — the gate must never
depend on someone else's hackathon service being up, or on the laptop having
network.

The tests that matter most are the ones about the API's failure modes, because
they are not the usual ones: a wrong key answers 200 with an empty list, and a
missing key answers 502. Neither looks like an auth failure, so both have to be
caught deliberately.
"""

from __future__ import annotations

import json
import urllib.error
from decimal import Decimal
from io import BytesIO

import pytest

import app.nessie.client as client
from app.nessie import (
    NessieUnavailable,
    NessieUpstreamError,
    status,
    to_scheduled,
    verify,
)
from app.nessie.client import NessieConfig, NessieError, to_cents

CFG = NessieConfig(api_key="k" * 32, base_url="https://example.invalid")


def http_error(code: int, body: dict | None = None) -> urllib.error.HTTPError:
    payload = json.dumps(body or {}).encode()
    return urllib.error.HTTPError(
        "https://example.invalid/customers?key=SECRET", code, "err", {}, BytesIO(payload)
    )


class FakeResponse:
    def __init__(self, payload) -> None:
        self._raw = payload if isinstance(payload, str) else json.dumps(payload)

    def read(self) -> bytes:
        return self._raw.encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


# ---- the failure modes that do not look like failures ----


def test_a_wrong_key_returns_an_empty_list_and_must_not_read_as_empty_data(monkeypatch):
    """The whole reason verify() writes instead of reading.

    A wrong key and a valid key over an empty sandbox are byte-identical: both
    answer 200 []. Measured against the live API on 2026-09-19.
    """
    monkeypatch.setattr(client.urllib.request, "urlopen", lambda *a, **k: FakeResponse([]))
    assert client.get(CFG, "/customers") == []


def test_verify_refuses_when_the_write_comes_back_without_an_id(monkeypatch):
    monkeypatch.setattr(client.urllib.request, "urlopen", lambda *a, **k: FakeResponse({"code": 201}))
    with pytest.raises(NessieUpstreamError, match="cannot be confirmed"):
        verify(CFG)


def test_verify_refuses_when_the_read_back_does_not_match(monkeypatch):
    """An empty or mismatched read-back is exactly how a wrong key looks."""
    calls = {"n": 0}

    def fake(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse({"objectCreated": {"_id": "abc"}})
        return FakeResponse({})

    monkeypatch.setattr(client.urllib.request, "urlopen", fake)
    with pytest.raises(NessieUnavailable, match="not confirmed"):
        verify(CFG)


def test_verify_succeeds_only_on_a_matching_write_then_read(monkeypatch):
    calls = {"n": 0}

    def fake(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse({"objectCreated": {"_id": "abc"}})
        return FakeResponse({"_id": "abc"})

    monkeypatch.setattr(client.urllib.request, "urlopen", fake)
    assert verify(CFG) == {"verified": True, "customer_id": "abc"}
    assert calls["n"] == 2, "verification must write AND read back, never just one"


def test_a_missing_key_is_a_configuration_error_not_an_outage(monkeypatch):
    """Nessie answers a keyless request with a generic 502, which reads as an
    upstream problem. It is not; it is us."""
    monkeypatch.setattr(
        client.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(http_error(502, {"message": "Internal server error"})),
    )
    with pytest.raises(NessieUnavailable):
        verify(NessieConfig(api_key=None))


def test_no_key_at_all_never_reaches_the_network(monkeypatch):
    def explode(*_a, **_k):
        raise AssertionError("must not call out without a key")

    monkeypatch.setattr(client.urllib.request, "urlopen", explode)
    with pytest.raises(NessieUnavailable):
        verify(NessieConfig(api_key=None))


# ---- the key must not leak ----


def test_the_key_never_appears_in_an_error_message(monkeypatch):
    secret = "s3cr3t" * 5
    cfg = NessieConfig(api_key=secret, base_url="https://example.invalid")
    monkeypatch.setattr(
        client.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(http_error(500)),
    )
    with pytest.raises(NessieError) as caught:
        client.get(cfg, "/customers")
    assert secret not in str(caught.value)
    assert "<redacted>" in str(caught.value)


def test_redaction_keeps_the_path_so_the_error_is_still_useful():
    out = client._redact("https://example.invalid/customers/abc?key=SECRET")
    assert out == "https://example.invalid/customers/abc?key=<redacted>"
    assert "SECRET" not in out


# ---- money ----


def test_dollars_become_exact_cents():
    assert to_cents(Decimal("19.99")) == 1999
    assert to_cents(Decimal("12.34")) == 1234
    assert to_cents(Decimal("0")) == 0
    assert to_cents(Decimal("-5.05")) == -505


def test_the_float_is_never_constructed(monkeypatch):
    """19.99 as a float times 100 is 1998.9999999999998, and int() of that is
    1998 — a cent short, silently. parse_float=Decimal means the float never
    exists in the first place."""
    monkeypatch.setattr(
        client.urllib.request, "urlopen", lambda *a, **k: FakeResponse('{"amount": 19.99}')
    )
    body = client.get(CFG, "/x")
    assert isinstance(body["amount"], Decimal)
    assert to_cents(body["amount"]) == 1999


def test_a_sub_cent_amount_is_refused_rather_than_rounded():
    with pytest.raises(NessieError, match="sub-cent"):
        to_cents(Decimal("1.005"))


def test_a_non_finite_amount_is_refused():
    with pytest.raises(NessieError, match="non-finite"):
        to_cents(Decimal("NaN"))


def test_an_absurd_amount_is_refused():
    with pytest.raises(NessieError, match="supported range"):
        to_cents(Decimal("1e17"))


def test_a_non_numeric_amount_is_refused():
    with pytest.raises(NessieError, match="not a number"):
        to_cents("twelve dollars")


# ---- normalisation ----


def test_ids_are_derived_from_nessie_so_a_refetch_does_not_renumber():
    """Renumbering invalidates every candidate id the client holds, and a lock
    naming a vanished id is a 422 on the whole solve, not a missing row."""
    rows = [{"_id": "abc123", "transaction_date": "2026-09-20", "amount": Decimal("10.00")}]
    once = to_scheduled(rows, "income", True)
    twice = to_scheduled(rows, "income", True)
    assert once == twice
    assert once[0]["id"] == "n_abc123"


def test_a_row_without_an_id_is_dropped_rather_than_given_a_made_up_one():
    assert to_scheduled([{"amount": Decimal("1.00")}], "income", True) == []


def test_charges_are_negative_and_income_is_positive():
    row = [{"_id": "a", "payment_date": "2026-09-20", "payment_amount": Decimal("25.00")}]
    assert to_scheduled(row, "bill", True)[0]["amount_cents"] == -2500
    assert to_scheduled(row, "income", True)[0]["amount_cents"] == 2500


# ---- status ----


def test_status_reports_configuration_without_writing(monkeypatch):
    def explode(*_a, **_k):
        raise AssertionError("status must not call out; it would write on every poll")

    monkeypatch.setattr(client.urllib.request, "urlopen", explode)
    assert status(CFG)["configured"] is True
    assert status(NessieConfig(api_key=None))["configured"] is False


def test_status_never_returns_the_key():
    assert "k" * 32 not in json.dumps(status(CFG))


# ---- the live probe, deselected by default ----


@pytest.mark.nessie
def test_the_live_sandbox_accepts_a_write_then_read():
    cfg = NessieConfig.from_env()
    if not cfg.api_key:
        pytest.skip("no NESSIE_API_KEY configured")
    assert verify(cfg)["verified"] is True


def test_precision_is_checked_before_scaling_not_after():
    """`value * 100` runs in the default 28-digit context, so this rounds to
    exactly 1999 during the multiply and the sub-cent check finds nothing wrong.
    Checking the exponent first needs no arithmetic and cannot be rounded away."""
    with pytest.raises(NessieError, match="sub-cent"):
        to_cents(Decimal("19.99000000000000000000000000001"))


def test_a_float_is_refused_rather_than_converted():
    """One reaching here means a caller built it outside _request, and accepting
    it would quietly reintroduce 1998.9999999999998."""
    with pytest.raises(NessieError, match="must not be floats"):
        to_cents(1.0)


def test_a_boolean_amount_is_refused():
    with pytest.raises(NessieError, match="boolean"):
        to_cents(True)


def test_whole_and_exponent_notation_still_convert():
    assert to_cents(Decimal("1E+2")) == 10_000
    assert to_cents(5) == 500
    assert to_cents(Decimal("-5")) == -500
