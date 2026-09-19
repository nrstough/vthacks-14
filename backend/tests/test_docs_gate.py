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


def test_the_environment_variable_actually_reaches_the_app(monkeypatch):
    """The one line the box depends on, and the only one that reads os.environ.

    Every other test here passes `docs=` explicitly, so all of them would
    still pass if the environment were never consulted at all — and the box
    would serve the console it is configured not to.
    """
    monkeypatch.setenv(DOCS_ENV, "0")
    off = TestClient(create_app(None))
    assert [off.get(u).status_code for u in DOC_URLS] == [404, 404, 404]

    monkeypatch.delenv(DOCS_ENV, raising=False)
    on = TestClient(create_app(None))
    assert [on.get(u).status_code for u in DOC_URLS] == [200, 200, 200]


def unit_directives() -> dict[str, list[str]]:
    """The unit as systemd reads it, to the extent this test needs.

    Line-wise greps are not enough: a lost backslash leaves a unit systemd
    refuses to start while every assertion about the text still passes,
    because the flags are all still somewhere in the file.

    Three behaviours are modelled because getting them wrong makes this test
    reject a correct unit:
      * a line ending in a backslash continues onto the next;
      * a comment block *inside* a continuation is ignored and the
        continuation carries on past it;
      * keys repeat. `Environment=` and `EnvironmentFile=` accumulate rather
        than overwrite, so every value is kept and callers test membership.

    Not modelled, because nothing here uses them: quoting, escape sequences
    inside values, and `key=` with an empty value resetting a list. Section
    headers are skipped rather than scoped, so do not add a directive whose
    meaning depends on which section it is in.
    """
    out: dict[str, list[str]] = {}
    pending = ""
    for raw in UNIT.read_text().splitlines():
        line = raw.strip()
        if pending:
            # systemd ignores a comment block inside a continuation.
            if not line or line.startswith("#"):
                continue
        elif not line or line.startswith("#"):
            continue
        pending = f"{pending} {line}" if pending else line
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        line, pending = pending, ""
        if line.startswith("[") and line.endswith("]"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out.setdefault(key.strip(), []).append(value.strip())
    return out


def only(values: list[str]) -> str:
    assert len(values) == 1, f"expected one value, got {values!r}"
    return values[0]


def test_the_unit_parses_the_way_systemd_reads_it():
    """Each flag belongs to ExecStart, not merely to the file."""
    exec_start = only(unit_directives()["ExecStart"])
    assert exec_start.startswith("/opt/overdraft-guard/.venv/bin/uvicorn app.main:app")
    for flag in ("--host", "127.0.0.1", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips"):
        assert flag in exec_start, f"{flag} is not part of ExecStart"
    assert "\\" not in exec_start  # no continuation left unjoined


def test_the_unit_file_sets_the_name_the_app_reads():
    """The one way to catch the unit and the application drifting apart."""
    # Membership, not equality: Environment= accumulates in systemd, so a
    # second unrelated variable must not fail this.
    assert f"{DOCS_ENV}=0" in unit_directives().get("Environment", [])


def test_the_unit_enables_proxy_headers_for_both_loopbacks():
    """The rate limit counts whatever uvicorn resolves as the client.

    Without these the peer is Caddy, every request shares one bucket, and the
    limit turns into a cap on the whole room.
    """
    # Directives only. A comment that mentions a flag does not set it, and the
    # first draft of this test was satisfied by the comment above ExecStart.
    # Read as systemd reads it: a comment that mentions a flag does not set
    # it, and neither does a line orphaned by a lost continuation.
    exec_start = only(unit_directives()["ExecStart"])
    assert "--proxy-headers" in exec_start
    allowed = exec_start.split("--forwarded-allow-ips", 1)[1].split()[0]
    assert "127.0.0.1" in allowed
    assert "::1" in allowed  # a loopback peer over IPv6 is not trusted by default


def test_the_switch_is_not_advertised_in_the_env_example():
    """It would not work from there, so it must not be listed there.

    The app reads this when it is built; `load_dotenv_once` does not run until
    the first chat request, long after.
    """
    assert DOCS_ENV not in ENV_EXAMPLE.read_text()
