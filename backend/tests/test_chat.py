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
from app.chat import chat, descriptor_refs, mask_descriptors, scrub, unmask_descriptors
from app.chat.prompt import dollars, render_context, system_instruction
from app.chat.schemas import ChatRequest
from app.main import create_app
from app.ratelimit import RateLimiter
from app.schemas import SolveRequest
from app.solver.solve import solve
from tests.fixtures.scenarios import SCENARIOS


@pytest.fixture(scope="module")
def client():
    # This module posts about twenty times, well past the shipped burst. The
    # limit is exercised in test_ratelimit.py against a default-configured
    # app, so opting out here cannot hide a wiring mistake.
    return TestClient(create_app(None, chat_limiter=RateLimiter.disabled()))


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


def test_a_cushion_only_change_is_paraphrased_without_not_needed():
    """The paraphrase handed to the model must not restate the old reading.

    The reason line no longer says a cushion-only change is "not needed to clear
    zero" — at tier 3 nothing clears zero — so the context must not hand the
    model that reading either. What zero marginals actually prove is that
    removing the change would not change the worst day.
    """
    from tests.fixtures.scenarios import request as make

    raw = make(25_000, 2_500)
    res = solve(SolveRequest.model_validate(raw))
    assert any(not p.strictly_needed for p in res.plan), (
        "the fixture must put a change in the plan that only holds the cushion"
    )
    text = render_context(SolveRequest.model_validate(raw), res)
    assert "not load-bearing: removing it would not change the worst day" in text
    assert "not needed to clear zero" not in text


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


# ---- descriptors never reach the model, so nothing has to guess ----
#
# Three earlier versions of this were bypassable, each in the same way: they tried
# to recover provenance from the model's output. Protected spans, then an
# upper-case rule, then case-sensitive matching — all defeated, the last by
# `scrub("This plan IS GUARANTEED to clear.", ["IS GUARANTEED"])`. A string does
# not carry where it came from.
#
# Now the model never sees a descriptor. It sees [[M0]], everything it writes is
# scrubbed unconditionally, and the real text goes back afterwards.

_TRAP = "GUARANTEED AUTO PROTECTION"


def test_the_scrubber_has_no_exceptions_left_to_exploit():
    for crafted in ["IS GUARANTEED", "GUARANTEED SAVINGS", "guaranteed savings", "Guaranteed Rate"]:
        out = scrub(f"This plan {crafted} covers it.")
        assert "guarantee" not in out.lower(), f"{crafted!r} survived as {out!r}"


def test_a_descriptor_is_taken_out_before_the_model_sees_it():
    refs = descriptor_refs([_TRAP])
    masked = mask_descriptors(f"- 2026-09-22 {_TRAP}: -$38.59", refs)
    assert _TRAP not in masked
    assert refs == [_TRAP]


def test_a_descriptor_comes_back_intact_after_scrubbing():
    refs = descriptor_refs([_TRAP])
    masked = mask_descriptors(f"row {_TRAP} here", refs)
    assert unmask_descriptors(scrub(masked), refs) == f"row {_TRAP} here"


def test_a_reply_gets_both_treatments_and_they_do_not_interfere():
    refs = descriptor_refs([_TRAP])
    reply = mask_descriptors(f"Skipping {_TRAP} frees $38.59, and it is guaranteed.", refs)
    out = unmask_descriptors(scrub(reply), refs)
    assert _TRAP in out, "the merchant name must survive"
    assert "it is guaranteed" not in out, "the product's claim must not"
    assert "sufficient under the schedule shown" in out


def test_an_invented_reference_is_dropped_not_guessed():
    """Inventing a merchant name into a sentence about someone's money is worse
    than a clipped sentence."""
    refs = descriptor_refs([_TRAP])
    invented = unmask_descriptors(mask_descriptors(_TRAP, refs).replace("M0", "M7"), refs)
    assert invented == ""


def test_masking_does_not_depend_on_set_ordering():
    pair = [_TRAP, "GUARANTEED AUTO PROTECTIOX"]
    text = f"a {_TRAP} b"
    assert mask_descriptors(text, descriptor_refs(pair)) == \
           mask_descriptors(text, descriptor_refs(list(reversed(pair))))


def test_the_longer_descriptor_wins_when_one_contains_another():
    refs = descriptor_refs(["KROGER #382", "KROGER #382 STORE"])
    masked = mask_descriptors("KROGER #382 STORE", refs)
    assert unmask_descriptors(masked, refs) == "KROGER #382 STORE"
    assert "KROGER" not in masked


def test_a_short_descriptor_cannot_clobber_the_references():
    """Replacing one descriptor at a time let a later one rewrite the placeholders
    an earlier one had just inserted. A merchant named "M" was enough."""
    refs = descriptor_refs([_TRAP, "M"])
    text = f"row {_TRAP} and M here"
    assert unmask_descriptors(mask_descriptors(text, refs), refs) == text


def test_the_conversation_history_is_masked_too(monkeypatch):
    """A user who types a merchant's name into the chat puts it back in front of
    the model, which echoes it, and the scrubber corrupts it again — the original
    bug reached by a different road."""
    import app.chat as chat_mod

    seen: dict = {}

    def fake(config, instruction, turns, sleep=None):
        seen["instruction"] = instruction
        seen["turns"] = turns
        return turns[-1][1], "stub-model"

    monkeypatch.setattr(chat_mod, "generate_with_fallback", fake)
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["scheduled"][0]["description"] = _TRAP
    solved = solve(SolveRequest.model_validate(raw))
    req = ChatRequest.model_validate({
        "messages": [{"role": "user", "text": f"why skip {_TRAP}?"}],
        "request": raw,
        "response": json.loads(solved.model_dump_json()),
    })
    out = chat(req, config=gemini.GeminiConfig(api_key="x", model="stub", timeout_s=5.0))
    assert _TRAP not in seen["turns"][-1][1], "the model saw the raw descriptor"
    assert _TRAP in out.reply, "and it must still come back intact"




def test_the_fixed_brief_is_never_rewritten_by_a_descriptor(monkeypatch):
    """Masking the rendered instruction rewrote the product's own words.

    A transaction described as "a" produced 239 replacements in the fixed brief —
    "You ⸤M0⸥re the expl⸤M0⸥iner". Descriptors live in known fields, so they are
    replaced there and the brief is left alone.
    """
    import app.chat as chat_mod

    seen: dict = {}

    def fake(config, instruction, turns, sleep=None):
        seen["instruction"] = instruction
        return "ok", "stub-model"

    monkeypatch.setattr(chat_mod, "generate_with_fallback", fake)
    raw = copy.deepcopy(SCENARIOS["clears"])
    raw["scheduled"][0]["description"] = "a"
    solved = solve(SolveRequest.model_validate(raw))
    req = ChatRequest.model_validate({
        "messages": [{"role": "user", "text": "why?"}],
        "request": raw,
        "response": json.loads(solved.model_dump_json()),
    })
    chat(req, config=gemini.GeminiConfig(api_key="x", model="stub", timeout_s=5.0))
    assert "You are the explainer" in seen["instruction"]
    assert "expl⸤M" not in seen["instruction"]


def test_a_short_descriptor_only_matches_as_a_whole_word():
    refs = descriptor_refs(["a"])
    assert mask_descriptors("a plan and a rate", refs).count("⸤M0⸥") == 2
    assert "plan" in mask_descriptors("a plan and a rate", refs)


# --------------------------------------------------------------------------
# where the account came from
# --------------------------------------------------------------------------
#
# These go through the route rather than calling system_instruction directly.
# The whole point of the field is that it reaches the model; a test that builds
# the instruction itself would keep passing if chat() forgot to pass it on.


def _instruction(fake) -> str:
    return fake.calls[0]["body"]["systemInstruction"]["parts"][0]["text"]


def test_a_preset_account_is_named_as_the_built_in_sample(client, solved, fake):
    r = client.post("/api/chat", json=body(solved))
    assert r.status_code == 200, r.text
    text = _instruction(fake)
    assert "the built-in sample account" in text
    assert "demo data" not in text


def test_an_omitted_account_source_behaves_as_a_preset(client, solved, fake):
    payload = body(solved)
    assert "account_source" not in payload
    client.post("/api/chat", json=payload)
    assert "the built-in sample account" in _instruction(fake)


def test_a_modelled_account_is_declared_as_generated_data(client, solved, fake):
    client.post("/api/chat", json={**body(solved), "account_source": "modelled"})
    text = _instruction(fake)
    assert "generated demo data" in text
    assert "not anyone's account" in text


def test_a_sandbox_account_is_declared_as_sandbox_data(client, solved, fake):
    """The one question this field exists for is "is this my real account?"."""
    client.post("/api/chat", json={**body(solved), "account_source": "nessie"})
    text = _instruction(fake)
    assert "Nessie sandbox" in text
    assert "not anyone's account" in text
    assert "whole dollars" in text


def test_an_unknown_account_source_is_refused_at_the_edge(client, solved):
    r = client.post("/api/chat", json={**body(solved), "account_source": "my bank"})
    assert r.status_code == 422


def test_no_account_source_line_breaks_the_wording_rules():
    """CLAUDE.md: never "guaranteed", never "infeasible", and sandbox data is
    never called real bank data."""
    from app.chat.prompt import ACCOUNT_SOURCE

    for line in ACCOUNT_SOURCE.values():
        lowered = line.lower()
        assert "guarantee" not in lowered
        assert "infeasib" not in lowered
        assert "real bank" not in lowered
