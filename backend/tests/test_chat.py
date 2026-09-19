"""The explainer, POST /api/chat.

Gemini is never called here. The transport is replaced so the tests can see
exactly what the model would be sent, and assert the two things that matter:
every figure the model may use is in the instruction, and the words the
product never says cannot come back out.
"""

from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient

import app.chat.gemini as gemini
from app.chat import scrub
from app.chat.prompt import dollars, render_context, system_instruction
from app.main import create_app
from app.schemas import SolveRequest
from app.solver.solve import solve
from tests.fixtures.scenarios import SCENARIOS


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(None))


@pytest.fixture(scope="module")
def solved():
    """A request and the solver's own answer to it, for each demo account."""
    out = {}
    for name, raw in SCENARIOS.items():
        req = SolveRequest.model_validate(raw)
        out[name] = (raw, solve(req).model_dump(by_alias=True))
    return out


def body(solved, name="clears", messages=None):
    raw, res = solved[name]
    return {
        "messages": messages or [{"role": "user", "text": "Why these changes?"}],
        "request": raw,
        "response": res,
    }


class FakeGemini:
    """Stands in for the HTTP call; records what it was sent."""

    def __init__(self, reply="Because the 24th is the tight day.", error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def __call__(self, url, headers, payload, timeout_s):
        self.calls.append({"url": url, "headers": headers, "body": payload, "timeout_s": timeout_s})
        if self.error:
            raise self.error
        return {"candidates": [{"content": {"parts": [{"text": self.reply}]}, "finishReason": "STOP"}]}


@pytest.fixture
def fake(monkeypatch):
    f = FakeGemini()
    monkeypatch.setattr(gemini, "_post_json", f)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    return f


# --------------------------------------------------------------------------
# without a key
# --------------------------------------------------------------------------


def test_status_says_off_without_a_key(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(gemini, "_env_loaded", True)  # do not read a developer's .env
    r = client.get("/api/chat/status")
    assert r.status_code == 200
    assert r.json() == {"configured": False, "model": None}


def test_chat_is_503_without_a_key(client, solved, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(gemini, "_env_loaded", True)
    r = client.post("/api/chat", json=body(solved))
    assert r.status_code == 503
    assert "key" in r.json()["detail"].lower()


# --------------------------------------------------------------------------
# with a key
# --------------------------------------------------------------------------


def test_status_names_the_model(client, fake):
    r = client.get("/api/chat/status")
    assert r.json() == {"configured": True, "model": gemini.DEFAULT_MODEL}


def test_reply_comes_back_with_the_model(client, solved, fake):
    r = client.post("/api/chat", json=body(solved))
    assert r.status_code == 200
    assert r.json() == {"reply": fake.reply, "model": gemini.DEFAULT_MODEL}
    assert len(fake.calls) == 1


def test_the_model_is_sent_the_key_in_a_header_not_the_url(client, solved, fake):
    client.post("/api/chat", json=body(solved))
    call = fake.calls[0]
    assert call["headers"]["x-goog-api-key"] == "test-key"
    assert "key=" not in call["url"]
    assert gemini.DEFAULT_MODEL in call["url"]


def test_history_is_sent_in_order_with_gemini_roles(client, solved, fake):
    msgs = [
        {"role": "user", "text": "first"},
        {"role": "assistant", "text": "second"},
        {"role": "user", "text": "third"},
    ]
    client.post("/api/chat", json=body(solved, messages=msgs))
    contents = fake.calls[0]["body"]["contents"]
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert [c["parts"][0]["text"] for c in contents] == ["first", "second", "third"]


def test_the_instruction_carries_every_figure_from_the_solve(client, solved, fake):
    raw, res = solved["clears"]
    client.post("/api/chat", json=body(solved, "clears"))
    text = fake.calls[0]["body"]["systemInstruction"]["parts"][0]["text"]
    assert res["verdict"] in text
    assert res["certificate"]["sentence"] in text
    for item in res["plan"]:
        assert item["label"] in text
        assert dollars(item["freed_cents"]) in text
    for row in res["balances"]:
        assert row["date"] in text
        assert dollars(row["with_plan_cents"]) in text
    for c in raw["candidates"]:
        assert c["id"] in text


def test_the_instruction_names_outside_cash_at_tier_3(solved):
    raw, res = solved["gap"]
    assert res["tier"] == 3, "the fixture is meant to be the one that cannot clear"
    text = render_context(SolveRequest.model_validate(raw), _resp(res))
    need = res["external_cash_needed"]
    assert dollars(need["amount_cents"]) in text
    assert need["by_date"] in text


def test_the_instruction_never_uses_the_forbidden_words(solved):
    for name, (raw, res) in solved.items():
        text = system_instruction(SolveRequest.model_validate(raw), _resp(res)).lower()
        # The brief mentions the words only to forbid them.
        forbidden = text.replace('never use the word "infeasible"', "").replace(
            'never say "guaranteed" or "guarantee"', ""
        )
        assert "infeasib" not in forbidden, name
        assert "guarantee" not in forbidden, name


def test_a_ruled_out_change_is_marked_as_the_users_call(client, solved, fake):
    raw, _ = solved["clears"]
    raw = copy.deepcopy(raw)
    victim = raw["candidates"][0]["id"]
    raw["locks"] = {"in": [], "out": [victim]}
    res = solve(SolveRequest.model_validate(raw)).model_dump(by_alias=True)
    client.post("/api/chat", json={"messages": [{"role": "user", "text": "hi"}], "request": raw, "response": res})
    text = fake.calls[0]["body"]["systemInstruction"]["parts"][0]["text"]
    assert f"{victim}:" in text
    assert "RULED OUT by the user" in text


def test_source_local_is_disclosed_to_the_model(client, solved, fake):
    client.post("/api/chat?source=local", json=body(solved))
    text = fake.calls[0]["body"]["systemInstruction"]["parts"][0]["text"]
    assert "built-in local solver" in text


def test_source_must_be_server_or_local(client, solved, fake):
    r = client.post("/api/chat?source=guess", json=body(solved))
    assert r.status_code == 422


# --------------------------------------------------------------------------
# failure paths
# --------------------------------------------------------------------------


def test_an_upstream_failure_is_a_502_with_the_reason(client, solved, monkeypatch):
    f = FakeGemini(error=gemini.GeminiError("quota exceeded", status=429))
    monkeypatch.setattr(gemini, "_post_json", f)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    r = client.post("/api/chat", json=body(solved))
    assert r.status_code == 502
    assert r.json()["detail"] == "quota exceeded"


def test_an_empty_answer_is_a_502(client, solved, monkeypatch):
    monkeypatch.setattr(gemini, "_post_json", lambda *a, **k: {"candidates": []})
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    r = client.post("/api/chat", json=body(solved))
    assert r.status_code == 502


def test_the_last_message_must_be_the_users(client, solved, fake):
    msgs = [{"role": "user", "text": "a"}, {"role": "assistant", "text": "b"}]
    r = client.post("/api/chat", json=body(solved, messages=msgs))
    assert r.status_code == 422


def test_an_empty_conversation_is_rejected(client, solved, fake):
    r = client.post("/api/chat", json={**body(solved), "messages": []})
    assert r.status_code == 422


def test_the_solve_is_validated_like_the_solver_would(client, solved, fake):
    b = copy.deepcopy(body(solved))  # the fixture is module-scoped; never mutate it
    b["response"]["tier"] = 4
    r = client.post("/api/chat", json=b)
    assert r.status_code == 422


# --------------------------------------------------------------------------
# wording
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expect",
    [
        ("This plan is infeasible.", "This plan is not fully coverable."),
        ("The plan is guaranteed to work.", "The plan is sufficient under the schedule shown to work."),
        ("It guarantees you stay above zero.", "It holds under the schedule shown you stay above zero."),
        ("Infeasibility means a gap.", "the gap means a gap."),
        ("Nothing to change here.", "Nothing to change here."),
    ],
)
def test_scrub_removes_the_words_the_product_never_says(text, expect):
    assert scrub(text) == expect


def test_a_reply_using_the_forbidden_words_is_scrubbed_over_http(client, solved, monkeypatch):
    f = FakeGemini(reply="It is infeasible, but the plan is guaranteed.")
    monkeypatch.setattr(gemini, "_post_json", f)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    r = client.post("/api/chat", json=body(solved))
    assert r.status_code == 200, r.text
    reply = r.json()["reply"].lower()
    assert "infeasib" not in reply
    assert "guarantee" not in reply


# --------------------------------------------------------------------------
# the client itself
# --------------------------------------------------------------------------


def test_extract_text_joins_parts():
    payload = {"candidates": [{"content": {"parts": [{"text": "a "}, {"text": "b"}]}}]}
    assert gemini.extract_text(payload) == "a b"


def test_extract_text_reports_a_block_reason():
    with pytest.raises(gemini.GeminiError, match="SAFETY"):
        gemini.extract_text({"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})


def test_dotenv_fills_only_unset_variables(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nGEMINI_API_KEY="from-file"\nGEMINI_MODEL=file-model\n\nJUNK\n')
    monkeypatch.setenv("GEMINI_MODEL", "already-set")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(gemini, "_env_loaded", False)
    gemini.load_dotenv_once(env)
    assert gemini.GeminiConfig.from_env().api_key == "from-file"
    assert gemini.GeminiConfig.from_env().model == "already-set"


def test_generate_serialises_a_request_gemini_accepts(monkeypatch):
    seen = {}

    def fake(url, headers, payload, timeout_s):
        seen.update(url=url, body=payload)
        return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    monkeypatch.setattr(gemini, "_post_json", fake)
    cfg = gemini.GeminiConfig(api_key="k", model="m", timeout_s=1.0)
    assert gemini.generate(cfg, "sys", [("user", "q")]) == "ok"
    json.dumps(seen["body"])  # must be plain JSON
    assert seen["body"]["systemInstruction"] == {"parts": [{"text": "sys"}]}
    assert seen["body"]["generationConfig"]["maxOutputTokens"] == gemini.MAX_OUTPUT_TOKENS
    assert seen["url"].endswith("/models/m:generateContent")


def _resp(res: dict):
    from app.schemas import SolveResponse

    return SolveResponse.model_validate(res)


# --------------------------------------------------------------------------
# overloaded: retry, then fall back
# --------------------------------------------------------------------------


class Flaky:
    """Answers per model according to a script of statuses; None means success."""

    def __init__(self, script: dict[str, list[int | None]]):
        self.script = {m: list(v) for m, v in script.items()}
        self.calls: list[str] = []

    def __call__(self, url, headers, payload, timeout_s):
        model = url.rsplit("/models/", 1)[1].split(":")[0]
        self.calls.append(model)
        status = self.script[model].pop(0)
        if status is not None:
            raise gemini.GeminiError(f"{model} said {status}", status=status)
        return {"candidates": [{"content": {"parts": [{"text": f"answer from {model}"}]}}]}


def _cfg(model="a", fallbacks=("b", "c")):
    return gemini.GeminiConfig(api_key="k", model=model, timeout_s=1.0, fallbacks=fallbacks)


def test_high_demand_is_retried_once_then_the_next_model_answers(monkeypatch):
    f = Flaky({"a": [503, 503], "b": [None]})
    monkeypatch.setattr(gemini, "_post_json", f)
    naps = []
    text, model = gemini.generate_with_fallback(_cfg(), "sys", [("user", "q")], sleep=naps.append)
    assert (text, model) == ("answer from b", "b")
    assert f.calls == ["a", "a", "b"]
    assert naps == [gemini.RETRY_PAUSE_S]


def test_a_transient_that_clears_on_retry_stays_on_the_primary(monkeypatch):
    f = Flaky({"a": [429, None]})
    monkeypatch.setattr(gemini, "_post_json", f)
    text, model = gemini.generate_with_fallback(_cfg(), "sys", [("user", "q")], sleep=lambda _: None)
    assert (text, model) == ("answer from a", "a")


def test_a_missing_model_moves_on_without_a_retry(monkeypatch):
    f = Flaky({"a": [404], "b": [None]})
    monkeypatch.setattr(gemini, "_post_json", f)
    naps = []
    _, model = gemini.generate_with_fallback(_cfg(), "sys", [("user", "q")], sleep=naps.append)
    assert model == "b"
    assert f.calls == ["a", "b"]
    assert naps == []


def test_a_bad_key_stops_at_once(monkeypatch):
    f = Flaky({"a": [403], "b": [None]})
    monkeypatch.setattr(gemini, "_post_json", f)
    with pytest.raises(gemini.GeminiError, match="403"):
        gemini.generate_with_fallback(_cfg(), "sys", [("user", "q")], sleep=lambda _: None)
    assert f.calls == ["a"]


def test_when_every_model_fails_the_last_error_is_reported(monkeypatch):
    f = Flaky({"a": [503, 503], "b": [503, 503], "c": [500, 500]})
    monkeypatch.setattr(gemini, "_post_json", f)
    with pytest.raises(gemini.GeminiError, match="c said 500"):
        gemini.generate_with_fallback(_cfg(), "sys", [("user", "q")], sleep=lambda _: None)
    assert f.calls == ["a", "a", "b", "b", "c", "c"]


def test_the_model_that_answered_is_what_the_client_sees(client, solved, monkeypatch):
    f = Flaky({gemini.DEFAULT_MODEL: [503, 503], gemini.DEFAULT_FALLBACKS[0]: [None]})
    monkeypatch.setattr(gemini, "_post_json", f)
    monkeypatch.setattr(gemini.time, "sleep", lambda _: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_FALLBACK_MODELS", raising=False)
    r = client.post("/api/chat", json=body(solved))
    assert r.status_code == 200
    assert r.json()["model"] == gemini.DEFAULT_FALLBACKS[0]


def test_fallbacks_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "x")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", " y , x ,, z ")
    monkeypatch.setattr(gemini, "_env_loaded", True)
    assert gemini.GeminiConfig.from_env().models() == ["x", "y", "z"]
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    assert gemini.GeminiConfig.from_env().models() == ["x"]
