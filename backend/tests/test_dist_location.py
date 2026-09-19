"""Where the service looks for the built frontend.

This has one job: stop the site from being a 404 in production while every check
reports success.

The original expression was `Path(__file__).resolve().parents[2] / "frontend" /
"dist"`, which is correct in the repo and wrong on the box. deploy.sh rsyncs
`backend/app/` to `$APP_DIR/app/`, so `backend/` is never recreated there and one
path level disappears: the app looked for /opt/frontend/dist while the bundle sat
in /opt/overdraft-guard/frontend/dist. The mount is guarded by `is_dir()`, so
nothing complained — the API answered, /health returned 200, and deploy.sh
printed "deployed".

Testing this needs no filesystem: the layout is decided by directory names, which
is the point. Probing for `dist/` instead would make the answer depend on whether
anyone had run a build, and `dist/` is gitignored.

The made-up paths below all sit under /opt or /Users on purpose. `_default_dist`
calls `.resolve()`, and on macOS /home and /var are symlinks (/var is
/private/var), so a test path under either resolves somewhere else and fails for
a reason that has nothing to do with the code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.main as main


def resolve_as(path: str, monkeypatch, env: str | None = None) -> Path:
    monkeypatch.setattr(main, "__file__", path)
    if env is None:
        monkeypatch.delenv("OVERDRAFT_DIST", raising=False)
    else:
        monkeypatch.setenv("OVERDRAFT_DIST", env)
    return main._default_dist()


def test_the_repo_layout_resolves_next_to_backend(monkeypatch):
    got = resolve_as("/opt/dev/vthacks/backend/app/main.py", monkeypatch)
    assert got == Path("/opt/dev/vthacks/frontend/dist")


def test_the_box_layout_resolves_inside_the_app_dir(monkeypatch):
    """The regression. parents[2] here is /opt, which is not where anything is."""
    got = resolve_as("/opt/overdraft-guard/app/main.py", monkeypatch)
    assert got == Path("/opt/overdraft-guard/frontend/dist")
    assert got != Path("/opt/frontend/dist"), "this is the bug that served a silent 404"


def test_an_explicit_override_wins(monkeypatch):
    got = resolve_as("/opt/overdraft-guard/app/main.py", monkeypatch, env="/srv/site")
    assert got == Path("/srv/site")


def test_a_repo_checked_out_somewhere_odd_still_works(monkeypatch):
    got = resolve_as("/Users/n/Desktop/VT Hacks/backend/app/main.py", monkeypatch)
    assert got == Path("/Users/n/Desktop/VT Hacks/frontend/dist")


@pytest.mark.parametrize("app_dir", ["/opt/overdraft-guard", "/srv/app", "/opt/www/guard"])
def test_any_app_dir_name_works_on_the_box(app_dir, monkeypatch):
    got = resolve_as(f"{app_dir}/app/main.py", monkeypatch)
    assert got == Path(app_dir) / "frontend" / "dist"
