"""The rate limit on the explainer, and the address it counts against.

The endpoint spends the server's Gemini key on every call, so the thing being
protected is the key, not the CPU. Every count below is a literal: no test
recomputes the limiter's own arithmetic and then agrees with it, which is the
failure mode that let a payday bug ship (see 70bac4d).
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import app.chat.gemini as gemini
from app.main import create_app
from app.ratelimit import RateLimiter, client_key
from app.schemas import SolveRequest
from app.solver.solve import solve
from app.solver.wording import BANNED
from tests.fixtures.scenarios import SCENARIOS

PEER = ("198.51.100.7", 4321)


class Clock:
    """A clock that only moves when a test says so."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class CountingLock:
    """A real lock that records how often the critical section was entered."""

    def __init__(self) -> None:
        self.entered = 0
        self._lock = threading.Lock()

    def __enter__(self):
        self.entered += 1
        return self._lock.__enter__()

    def __exit__(self, *exc):
        return self._lock.__exit__(*exc)


def limited_app(**kwargs):
    """An app whose chat limit is small enough to exhaust in a few lines."""
    return create_app(None, chat_limiter=RateLimiter(**kwargs))


def chat_post(client: TestClient):
    """A chat request that is valid JSON but not a valid solve.

    The limiter runs as a route dependency, so it answers before the body is
    ever validated: a refusal is 429 and anything that gets past the limiter
    is 422. That makes the limit testable without solving anything.
    """
    return client.post("/api/chat", json={})


@pytest.fixture(scope="module")
def chat_body():
    """A real request and the solver's own answer to it, solved once."""
    raw = SCENARIOS["clears"]
    res = solve(SolveRequest.model_validate(raw)).model_dump(by_alias=True)
    return {
        "messages": [{"role": "user", "text": "Why these changes?"}],
        "request": raw,
        "response": res,
    }


# --------------------------------------------------------------------------
# Stage 1 — the bucket
# --------------------------------------------------------------------------


def test_exactly_the_burst_is_admitted_then_one_is_refused():
    limiter = RateLimiter(per_minute=20, burst=10, clock=Clock())
    assert [limiter.check("a").allowed for _ in range(10)] == [True] * 10
    assert limiter.check("a").allowed is False


def test_two_limiters_hold_independent_budgets():
    clock = Clock()
    one = RateLimiter(per_minute=20, burst=2, clock=clock)
    two = RateLimiter(per_minute=20, burst=2, clock=clock)
    for _ in range(2):
        assert one.check("a").allowed is True
    assert one.check("a").allowed is False
    # The second limiter has never seen this address.
    assert two.check("a").allowed is True


def test_two_applications_hold_independent_budgets():
    """The one above proves two limiter objects do not share. This proves the
    factory builds two of them.

    A module-level limiter would pass the test above and fail this one: the
    same address would arrive at the second application already spent, and
    one process serving two apps — which the test suite itself does — would
    leak a budget between them.
    """
    first = TestClient(create_app(None), client=PEER)
    second = TestClient(create_app(None), client=PEER)

    assert [chat_post(first).status_code for _ in range(11)] == [422] * 10 + [429]
    assert chat_post(second).status_code == 422  # a fresh budget, same address


def test_the_budget_returns_after_the_window():
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=2, clock=clock)
    assert limiter.check("a").allowed is True
    assert limiter.check("a").allowed is True
    assert limiter.check("a").allowed is False
    clock.advance(3)  # 20/minute is one token every three seconds
    assert limiter.check("a").allowed is True


def test_a_long_idle_does_not_bank_more_than_the_burst():
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=10, clock=clock)
    limiter.check("a")
    clock.advance(86_400)  # a day
    assert [limiter.check("a").allowed for _ in range(10)] == [True] * 10
    assert limiter.check("a").allowed is False


def test_a_clock_that_goes_backwards_grants_nothing():
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=2, clock=clock)
    limiter.check("a")
    limiter.check("a")
    assert limiter.check("a").allowed is False
    clock.advance(-600)  # an NTP step, or a wall clock someone reached for
    assert limiter.check("a").allowed is False


def test_a_clock_that_oscillates_cannot_manufacture_tokens():
    """The guarantee is one way, and this is the direction that matters.

    An earlier draft resynced the timestamp on a backwards step so an address
    could not be stranded. That let a clock which steps back and then forward
    again mint a full burst per round trip while no time passed at all: fifty
    tokens, with the clock finishing exactly where it started. A limiter that
    can be wound is not a limiter.
    """
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=10, clock=clock)
    for _ in range(10):
        limiter.check("a")
    assert limiter.check("a").allowed is False

    granted = 0
    for _ in range(5):
        clock.advance(-600)
        limiter.check("a")
        clock.advance(600)  # back to the very instant the burst was spent
        while limiter.check("a").allowed:
            granted += 1

    assert granted == 0


def test_the_budget_resumes_once_the_clock_passes_where_it_had_been():
    """The cost of that choice, stated rather than left to be discovered.

    After a backwards step the bucket waits for the clock to pass its previous
    reading. `time.monotonic` never goes backwards, so this cannot arise in
    the service; where the two guarantees conflict, a guard on spending
    someone's API key fails closed.
    """
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=1, clock=clock)
    limiter.check("a")
    assert limiter.check("a").allowed is False

    clock.advance(-600)
    assert limiter.check("a").allowed is False  # nothing granted, nothing recorded
    clock.advance(3)
    assert limiter.check("a").allowed is False  # still behind the high-water mark

    clock.advance(600)  # past it, and the ordinary refill resumes
    assert limiter.check("a").allowed is True


def test_the_reported_wait_is_honest_even_while_the_clock_is_behind():
    """The wait it reports is the wait it enforces, in the odd case too.

    The deficit alone would promise three seconds in the middle of a
    ten-minute wait, because refilling has not even resumed yet.
    """
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=1, clock=clock)
    limiter.check("a")
    assert limiter.check("a").retry_after_s == 3  # the ordinary case

    clock.advance(-600)
    reported = limiter.check("a").retry_after_s
    assert reported == 603  # 600 to catch up, then 3 for the token

    clock.advance(reported - 1)
    assert limiter.check("a").allowed is False  # not a second early
    clock.advance(1)
    assert limiter.check("a").allowed is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"per_minute": 0},
        {"per_minute": -1},
        {"burst": 0},
        {"burst": -1},
        {"max_keys": 0},
        {"max_keys": -5},
    ],
)
def test_a_limiter_cannot_be_configured_into_a_hole(kwargs):
    """`disabled()` is the off switch; none of these is.

    Zero `per_minute` divides by zero on the first refusal. Zero `max_keys`
    evicts each bucket as fast as it is made and silently admits everything,
    which is worse than raising. A negative `max_keys` raises out of
    `popitem`. All three are a 500 or a hole rather than a limit.
    """
    with pytest.raises(ValueError, match="disabled"):
        RateLimiter(**kwargs)


def test_a_refused_request_is_not_charged():
    """Charging a refusal would let a loop extend its own lockout for ever."""
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=1, clock=clock)
    assert limiter.check("a").allowed is True
    for _ in range(50):  # hammering while locked out
        assert limiter.check("a").allowed is False
    clock.advance(3)  # one token's worth, and one only
    assert limiter.check("a").allowed is True
    assert limiter.check("a").allowed is False


def test_the_sustained_rate_matches_what_was_configured():
    """Twenty a minute means twenty a minute, not nineteen or twenty-two."""
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=10, clock=clock)
    for _ in range(10):  # spend the burst
        limiter.check("a")
    admitted = 0
    for _ in range(20):
        clock.advance(3)
        if limiter.check("a").allowed:
            admitted += 1
    assert admitted == 20  # over the 60 seconds just elapsed


def test_the_wait_it_reports_is_the_wait_it_enforces():
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=1, clock=clock)
    limiter.check("a")
    refusal = limiter.check("a")
    assert refusal.allowed is False and refusal.retry_after_s == 3
    clock.advance(refusal.retry_after_s - 1)
    assert limiter.check("a").allowed is False  # not yet
    clock.advance(1)
    assert limiter.check("a").allowed is True  # exactly then


def test_the_critical_section_is_locked():
    lock = CountingLock()
    limiter = RateLimiter(per_minute=20, burst=2, clock=Clock(), lock=lock)
    limiter.check("a")
    limiter.check("a")
    assert lock.entered == 2


def test_a_thread_hammer_never_admits_more_than_the_burst():
    # A rate slow enough that nothing refills while the threads run, so the
    # only way to exceed ten is a lost update.
    limiter = RateLimiter(per_minute=1, burst=10)
    start = threading.Barrier(50)
    admitted: list[bool] = []
    guard = threading.Lock()

    def hammer() -> None:
        start.wait()
        allowed = limiter.check("a").allowed
        with guard:
            admitted.append(allowed)

    threads = [threading.Thread(target=hammer) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(admitted) == 10


def test_the_map_never_exceeds_its_ceiling():
    limiter = RateLimiter(per_minute=20, burst=10, max_keys=8, clock=Clock())
    for i in range(500):
        limiter.check(f"addr-{i}")
        assert len(limiter) <= 8


def test_eviction_forgets_the_least_recently_used():
    """The oldest quiet address is dropped, never the newest arrival.

    Pins the direction. Evicting the most recent instead would hold the first
    few addresses for ever and forget everyone who arrived after them.
    """
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=2, max_keys=4, clock=clock)
    limiter.check("old")
    limiter.check("old")
    assert limiter.check("old").allowed is False

    for i in range(20):  # twenty other addresses, "old" never touched again
        limiter.check(f"new-{i}")

    assert limiter.check("old").allowed is True  # long since forgotten


def test_a_busy_address_is_never_the_one_evicted():
    """Filling the map must not be a way to clear your own record.

    Pins the recency tracking: without it the map is insertion-ordered and the
    first address in — the one hammering — is the first one dropped.
    """
    clock = Clock()
    limiter = RateLimiter(per_minute=20, burst=2, max_keys=4, clock=clock)
    limiter.check("busy")
    limiter.check("busy")
    assert limiter.check("busy").allowed is False

    for i in range(200):  # churn far past the ceiling
        limiter.check(f"passer-{i}")
        assert limiter.check("busy").allowed is False  # still remembered


def test_disabled_allows_everything():
    limiter = RateLimiter.disabled()
    assert all(limiter.check("a").allowed for _ in range(1000))


# --------------------------------------------------------------------------
# Stage 2 — the address, in the shape the box actually runs
#
# uvicorn's ProxyHeadersMiddleware is on by default and is what resolves the
# client behind Caddy. These drive that composition, not the bare app, so the
# path under test is the path in production.
# --------------------------------------------------------------------------


def proxied(**kwargs):
    return ProxyHeadersMiddleware(limited_app(**kwargs), trusted_hosts="127.0.0.1")


def test_two_ports_on_one_host_share_a_budget():
    """The peer is a (host, port) pair and the port changes every connection.

    Keying on the pair would hand out a fresh budget per request: a limiter
    that does nothing while looking like it works.
    """
    app = limited_app(per_minute=20, burst=2, clock=Clock())
    first = TestClient(app, client=("198.51.100.7", 1111))
    second = TestClient(app, client=("198.51.100.7", 2222))
    assert chat_post(first).status_code == 422
    assert chat_post(second).status_code == 422
    assert chat_post(second).status_code == 429


def test_a_client_cannot_choose_its_own_key_by_forwarding():
    """Caddy appends, so the hop it wrote is the last one.

    A client that prepends its own value is choosing a name for a hop that is
    ignored. If the first hop were taken instead, each request below would be
    a different key and none would ever be refused.
    """
    app = proxied(per_minute=20, burst=2, clock=Clock())
    client = TestClient(app, client=("127.0.0.1", 5))
    codes = [
        client.post("/api/chat", json={}, headers={"X-Forwarded-For": f"10.0.0.{i}, 198.51.100.7"}).status_code
        for i in range(3)
    ]
    assert codes == [422, 422, 429]


def test_two_clients_behind_the_proxy_hold_separate_budgets():
    app = proxied(per_minute=20, burst=2, clock=Clock())
    client = TestClient(app, client=("127.0.0.1", 5))

    def post(addr: str):
        return client.post("/api/chat", json={}, headers={"X-Forwarded-For": addr}).status_code

    assert [post("198.51.100.7") for _ in range(3)] == [422, 422, 429]
    assert post("203.0.113.9") == 422  # a different person, unaffected


def test_a_direct_peer_is_keyed_by_its_own_address():
    """An untrusted peer's own header is not honoured, so it cannot bypass."""
    app = proxied(per_minute=20, burst=2, clock=Clock())
    client = TestClient(app, client=("203.0.113.9", 4321))
    codes = [
        client.post("/api/chat", json={}, headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code
        for i in range(3)
    ]
    assert codes == [422, 422, 429]


def test_a_request_with_no_client_does_not_raise():
    assert client_key(SimpleNamespace(client=None)) == "unknown"
    assert client_key(SimpleNamespace(client=SimpleNamespace(host=None))) == "unknown"
    assert client_key(SimpleNamespace()) == "unknown"


def test_the_key_is_the_host_alone():
    assert client_key(SimpleNamespace(client=SimpleNamespace(host="198.51.100.7", port=1111))) == "198.51.100.7"


# --------------------------------------------------------------------------
# Stage 3 — scope: the limit is on the explainer and nothing else
# --------------------------------------------------------------------------


@pytest.fixture
def exhausted():
    """An app whose chat budget is spent, and a client that spent it."""
    app = limited_app(per_minute=20, burst=1, clock=Clock())
    client = TestClient(app, client=PEER)
    assert chat_post(client).status_code == 422
    assert chat_post(client).status_code == 429
    return client


def test_the_status_endpoint_is_never_limited(exhausted):
    """A prefix test on "/api/chat" would also catch "/api/chat/status"."""
    for _ in range(5):
        assert exhausted.get("/api/chat/status").status_code == 200


def test_health_is_never_limited(exhausted):
    for _ in range(5):
        assert exhausted.get("/health").status_code == 200


def test_the_solver_routes_are_never_limited(exhausted, chat_body):
    for _ in range(5):
        # Malformed on purpose: 422 proves the request reached validation
        # rather than being turned away by the limiter.
        assert exhausted.post("/api/solve", json={}).status_code == 422
        assert exhausted.post("/api/candidates", json={}).status_code == 422
    # And a real solve still answers.
    assert exhausted.post("/api/solve", json=chat_body["request"]).status_code == 200


def test_a_second_address_is_unaffected(exhausted):
    other = TestClient(exhausted.app, client=("203.0.113.9", 9999))
    assert chat_post(other).status_code == 422


# --------------------------------------------------------------------------
# Stage 4 — the refusal itself
# --------------------------------------------------------------------------


def test_the_default_app_allows_ten_then_refuses():
    """The shipped numbers, not a test-only configuration: 20/min, burst 10."""
    client = TestClient(create_app(None), client=PEER)
    codes = [chat_post(client).status_code for _ in range(11)]
    assert codes == [422] * 10 + [429]


def test_the_refusal_carries_a_retry_after_header(exhausted):
    r = chat_post(exhausted)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_the_refusal_has_the_same_shape_as_every_other_error(exhausted):
    r = chat_post(exhausted)
    assert set(r.json()) == {"detail"} and isinstance(r.json()["detail"], str)


def test_the_refusal_uses_no_banned_word(exhausted):
    """A thrown message reaching the screen verbatim is the 70bac4d defect."""
    detail = chat_post(exhausted).json()["detail"].lower()
    for word in BANNED:
        assert word not in detail, f"{word!r} in {detail!r}"


def test_the_refusal_says_how_long_in_words(exhausted):
    detail = chat_post(exhausted).json()["detail"]
    assert "resting" in detail and "seconds" in detail


def test_a_limited_address_is_refused_before_its_body_is_validated(exhausted):
    """The cheaper rejection wins: a limited address never reaches validation."""
    assert exhausted.post("/api/chat", json={"messages": "not a list"}).status_code == 429


def test_unparseable_json_is_still_a_422(exhausted):
    """The boundary, recorded rather than discovered later.

    A body that is not JSON at all is rejected by the parser before any
    dependency runs, so it answers 422 even from a limited address.
    """
    r = exhausted.post("/api/chat", content=b"{", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_the_limit_applies_even_with_no_key_configured(monkeypatch, chat_body):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(gemini, "_env_loaded", True)
    client = TestClient(limited_app(per_minute=20, burst=2, clock=Clock()), client=PEER)
    assert [client.post("/api/chat", json=chat_body).status_code for _ in range(3)] == [503, 503, 429]


def test_a_refused_request_never_reaches_the_model(monkeypatch, chat_body):
    calls: list[int] = []

    def fake_post(url, headers, payload, timeout_s):
        calls.append(1)
        return {"candidates": [{"content": {"parts": [{"text": "Because the 24th is tight."}]}}]}

    monkeypatch.setattr(gemini, "_post_json", fake_post)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client = TestClient(limited_app(per_minute=20, burst=2, clock=Clock()), client=PEER)

    assert [client.post("/api/chat", json=chat_body).status_code for _ in range(2)] == [200, 200]
    assert len(calls) == 2
    assert client.post("/api/chat", json=chat_body).status_code == 429
    assert len(calls) == 2  # the refusal cost nothing upstream
