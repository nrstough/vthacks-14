"""The statement stays private (A2) and the wording stays honest (A11).

An imported account is the only place in this product where real merchant
names exist. They are needed to detect and classify, and they are needed
nowhere else — so nothing that leaves this process may contain one. That
includes the response, every later solve request built from it, the chat
request sent to Gemini, validation error bodies, and the logs.
"""

from __future__ import annotations

import datetime
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.chat.prompt import ACCOUNT_SOURCE, render_context
from app.history.labels import CATEGORY_DISPLAY
from app.main import create_app
from app.schemas import SolveRequest
from app.solver.solve import solve
from tests.fixtures import histories as H

AS_OF = "2026-09-21"

# Two kinds of payee, because they leak by different routes. The high-entropy
# ones catch a verbatim copy; the recognised ones catch the lexicon's BRAND
# reaching a candidate label, which a random string never would.
SECRET = "ZZQ7K4XM"
RECOGNISED = ("NETFLIX", "PLANET FIT", "KROGER", "OAKWOOD", "DOORDASH", "SPOTIFY")


@pytest.fixture
def client():
    return TestClient(create_app(None))


def rows_with_secrets():
    rows = H.weekly_income(datetime.date(2026, 9, 18), weeks=30, description=f"{SECRET}-EMPLOYER LLC")
    rows += H.monthly_bill(datetime.date(2026, 1, 1), 9, 1, -120000, "OAKWOOD PROPERTIES")
    rows += H.monthly_bill(datetime.date(2026, 1, 15), 9, 15, -1599, "NETFLIX.COM", weekend_shift=False)
    rows += H.monthly_bill(datetime.date(2026, 1, 12), 9, 12, -3499, "PLANET FIT CLUB FEES", weekend_shift=False)
    rows += H.monthly_bill(datetime.date(2026, 1, 8), 9, 8, -2200, f"{SECRET}-LANDLORD", weekend_shift=False)
    rows += H.everyday_spending(datetime.date(2026, 6, 1), datetime.date(2026, 9, 18))
    return rows


def imported(client, rows=None):
    payload = {
        "rows": rows or rows_with_secrets(),
        "as_of": AS_OF,
        "opening_balance_cents": 60000,
        "buffer_cents": 2500,
    }
    r = client.post("/api/accounts/import", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_no_payee_and_no_brand_appears_anywhere_in_the_response(client):
    out = imported(client)
    blob = json.dumps(out).upper()
    assert SECRET not in blob
    for brand in RECOGNISED:
        assert brand not in blob, f"{brand} reached the response"


def test_the_response_still_says_enough_to_be_useful(client):
    # A privacy test that passes because the response is empty proves nothing.
    out = imported(client)
    assert len(out["streams"]) >= 4
    labels = " ".join(s["label"] for s in out["streams"]).lower()
    assert "income" in labels
    assert any(CATEGORY_DISPLAY[c] in labels for c in ("rent or mortgage", "streaming subscription") if c in CATEGORY_DISPLAY) or "rent" in labels


def test_candidate_labels_and_details_carry_a_category_not_a_brand(client):
    out = imported(client)
    assert out["candidates"], "the fixture must produce candidates or this proves nothing"
    for candidate in out["candidates"]:
        text = f"{candidate['label']} {candidate['detail']}".upper()
        assert SECRET not in text
        for brand in RECOGNISED:
            assert brand not in text


def test_a_solve_request_built_from_an_import_carries_no_payee(client):
    out = imported(client)
    request = SolveRequest.model_validate(
        {
            "as_of": out["as_of"],
            "horizon_end": out["horizon_end"],
            "opening_balance_cents": out["opening_balance_cents"],
            "buffer_cents": out["buffer_cents"],
            "scheduled": out["scheduled"],
            "candidates": out["candidates"],
            "locks": {"in": [], "out": []},
        }
    )
    blob = request.model_dump_json().upper()
    assert SECRET not in blob
    for brand in RECOGNISED:
        assert brand not in blob


def test_the_chat_context_carries_no_payee_and_names_the_assumption(client):
    out = imported(client)
    request = SolveRequest.model_validate(
        {
            "as_of": out["as_of"],
            "horizon_end": out["horizon_end"],
            "opening_balance_cents": out["opening_balance_cents"],
            "buffer_cents": out["buffer_cents"],
            "scheduled": out["scheduled"],
            "candidates": out["candidates"],
            "locks": {"in": [], "out": []},
        }
    )
    context = render_context(request, solve(request), source="server", account_source="import")
    upper = context.upper()
    assert SECRET not in upper
    for brand in RECOGNISED:
        assert brand not in upper
    assert "assumption" in context.lower() or "assumed" in context.lower()


def test_the_chat_source_table_knows_what_an_import_is():
    text = ACCOUNT_SOURCE["import"].lower()
    assert "assum" in text
    assert "never call them scheduled charges" in text


def test_a_validation_error_never_echoes_a_row(client):
    # FastAPI's default 422 echoes the offending value: for a missing field
    # that is the whole row, and for a list over its cap it is the whole list.
    r = client.post(
        "/api/accounts/import",
        json={"rows": [{"date": "2026-01-01", "description": f"{SECRET} PAYEE"}], "opening_balance_cents": 1},
    )
    assert r.status_code == 422
    assert SECRET not in json.dumps(r.json()).upper()
    assert set(r.json()["detail"][0]) == {"type", "loc", "msg"}


def test_an_oversized_upload_does_not_return_the_statement(client):
    row = {"date": "2026-01-01", "description": f"{SECRET} PAYEE", "amount_cents": -1}
    r = client.post("/api/accounts/import", json={"rows": [row] * 20001, "opening_balance_cents": 1})
    assert r.status_code == 422
    assert SECRET not in json.dumps(r.json()).upper()


def test_other_routes_keep_the_error_body_they_have_today(client):
    r = client.post(
        "/api/solve",
        json={
            "as_of": "2026-09-19",
            "horizon_end": "2026-10-02",
            "opening_balance_cents": 200.5,
            "buffer_cents": 0,
            "scheduled": [],
            "candidates": [],
            "locks": {"in": [], "out": []},
        },
    )
    assert r.status_code == 422
    assert set(r.json()["detail"][0]) == {"type", "loc", "msg", "input"}
    assert r.json()["detail"][0]["input"] == 200.5


def test_nothing_is_logged_during_an_import(client, caplog):
    with caplog.at_level(logging.DEBUG):
        imported(client)
        client.post("/api/accounts/import", json={"rows": [{"date": "2026-01-01"}], "opening_balance_cents": 1})
    text = caplog.text.upper()
    assert SECRET not in text
    for brand in RECOGNISED:
        assert brand not in text


# --------------------------------------------------------------------------
# A11: wording

BANNED = ("infeasib", "guarantee", "predict", "forecast")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_the_import_never_uses_a_word_the_product_does_not_say(client):
    out = imported(client)
    for text in _strings(out):
        low = text.lower()
        for word in BANNED:
            assert word not in low, f"{word!r} in {text!r}"


def test_every_category_display_name_is_safe_to_show():
    for word in BANNED:
        assert all(word not in name.lower() for name in CATEGORY_DISPLAY.values())


def test_assumed_rows_say_they_are_assumed_on_their_face(client):
    out = imported(client)
    assumed = [t for t in out["scheduled"] if t["id"].startswith("f_")]
    assert assumed
    for row in assumed:
        assert "assumed" in row["description"].lower()


def test_candidate_sentences_are_grammatical_for_plural_categories():
    # "Trimming this groceries" reads as a bug, and a person who sees one
    # stops trusting the number beside it.
    from app.history.labels import CATEGORY_DISPLAY, candidate_detail, candidate_label

    for category in CATEGORY_DISPLAY:
        for action in ("skip", "defer", "downgrade", "cancel"):
            sentence = f"{candidate_label(action, category)}. {candidate_detail(action, category, 1234)}"
            assert " this " not in sentence, sentence
            assert sentence.endswith(".")
