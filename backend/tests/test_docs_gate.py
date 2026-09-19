"""The interactive API console, and the two settings the box depends on.

Not a vulnerability — the contract is in the repository and no endpoint takes
a credential — but there is no reason for a demo box to serve a live request
console against the solver.

Two of these read the systemd unit. A setting the application reads and a
setting the unit writes can drift apart silently, and nothing else in the
suite would notice.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import DOCS_ENV, create_app, docs_enabled

DOC_URLS = ("/api/docs", "/api/openapi.json", "/redoc")

REPO = Path(__file__).resolve().parents[2]
UNIT = REPO / "deploy" / "overdraft-guard.service"
ENV_EXAMPLE = REPO / ".env.example"


def test_unset_means_the_docs_are_served():
    """Development is unchanged by this switch."""
    client = TestClient(create_app(None, docs=docs_enabled({})))
    assert [client.get(u).status_code for u in DOC_URLS] == [200, 200, 200]


def test_all_three_documentation_urls_are_gone_when_off():
    """Including /redoc, which the app never set and which answered 200.

    Gating the schema is what closes all three, since FastAPI mounts both
    consoles only when openapi_url is set; redoc_url is stated as well so the
    intent does not depend on that nesting.
    """
    client = TestClient(create_app(None, docs=False))
    assert [client.get(u).status_code for u in DOC_URLS] == [404, 404, 404]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, True),
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("FALSE", False),
        ("No", False),
        ("off", False),
        ("", False),
        ("  0  ", False),
    ],
)
def test_the_switch_reads_the_usual_falsey_spellings(raw, expected):
    """`bool("0")` is True, which is exactly how this gets written wrong."""
    env = {} if raw is None else {DOCS_ENV: raw}
    assert docs_enabled(env) is expected


def test_the_unit_file_sets_the_name_the_app_reads():
    """The one way to catch the unit and the application drifting apart."""
    assert f"Environment={DOCS_ENV}=0" in UNIT.read_text()


def test_the_unit_enables_proxy_headers_for_both_loopbacks():
    """The rate limit counts whatever uvicorn resolves as the client.

    Without these the peer is Caddy, every request shares one bucket, and the
    limit turns into a cap on the whole room.
    """
    # Directives only. A comment that mentions a flag does not set it, and the
    # first draft of this test was satisfied by the comment above ExecStart.
    directives = [ln for ln in UNIT.read_text().splitlines() if not ln.lstrip().startswith("#")]
    assert any("--proxy-headers" in ln for ln in directives)
    line = next(ln for ln in directives if "--forwarded-allow-ips" in ln)
    allowed = line.split("--forwarded-allow-ips", 1)[1].split()[0]
    assert "127.0.0.1" in allowed
    assert "::1" in allowed  # a loopback peer over IPv6 is not trusted by default


def test_the_switch_is_not_advertised_in_the_env_example():
    """It would not work from there, so it must not be listed there.

    The app reads this when it is built; `load_dotenv_once` does not run until
    the first chat request, long after.
    """
    assert DOCS_ENV not in ENV_EXAMPLE.read_text()
