"""deploy.sh must refuse to deploy without a DOMAIN.

The bug this pins: deploy.sh rsyncs the repo's `Caddyfile` over
`/etc/caddy/Caddyfile` on every run, and the site address written into it comes
from `DOMAIN`. `DOMAIN` is read from `.deploy.env`, which is gitignored — so it
exists in the checkout it was typed into and in no other. A deploy from any other
worktree used to substitute `:80` instead, take the live site off HTTPS, print
"deployed" and exit 0. The script's own smoke checks compute their origin from
`DOMAIN` too, so with it empty they checked the box's bare IP over plain HTTP and
passed.

Sixteen worktrees existed on 2026-09-19 and two had a `.deploy.env`.

These tests run the real script rather than only grepping it, because the thing
worth pinning is the exit status and the ordering — that it refuses *before* the
build, the rsync and the first ssh, not partway through, leaving a template in
`/etc/caddy`. The script is copied to a tmp dir (it `cd`s to its own directory,
so the copy neither sees nor needs this repo's `.deploy.env`, and a developer who
has one cannot make these tests pass or fail by accident), and `npm`, `ssh`,
`rsync` and `curl` are replaced with stubs that record being called and fail.
Nothing here can touch the network or the box.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DEPLOY = REPO / "deploy.sh"

# Anything that would leave the machine. Each stub records the call and fails, so
# a run that reaches one dies there and the marker says which.
STUBBED = ("npm", "ssh", "rsync", "curl", "scp")


@pytest.fixture
def deploy(tmp_path):
    """A runnable copy of deploy.sh with every outbound command stubbed."""
    work = tmp_path / "checkout"
    work.mkdir()
    shutil.copy(DEPLOY, work / "deploy.sh")
    (work / "deploy.sh").chmod(0o755)
    shutil.copy(REPO / "Caddyfile", work / "Caddyfile")

    calls = tmp_path / "calls"
    calls.mkdir()

    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name in STUBBED:
        stub = stubs / name
        stub.write_text(
            "#!/bin/sh\n"
            f'printf "%s\\n" "$*" >> "{calls}/{name}"\n'
            f'echo "STUB {name} called" >&2\n'
            "exit 1\n"
        )
        stub.chmod(0o755)

    def run(*args, domain=None):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("DOMAIN", "TARGET", "APP_DIR")
        }
        env["PATH"] = f"{stubs}:{env.get('PATH', '')}"
        if domain is not None:
            env["DOMAIN"] = domain
        return subprocess.run(
            ["bash", str(work / "deploy.sh"), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

    run.called = lambda name: (calls / name).exists()  # type: ignore[attr-defined]
    run.any_called = lambda: [n for n in STUBBED if (calls / n).exists()]  # type: ignore[attr-defined]
    run.dir = work  # type: ignore[attr-defined]
    return run


def test_the_script_is_syntactically_valid():
    assert subprocess.run(["bash", "-n", str(DEPLOY)]).returncode == 0


def test_no_domain_refuses(deploy):
    """The regression. Empty DOMAIN must be a refusal, not a `:80` fallback.

    The exit status alone is not enough to pin this: under the stubs the old
    buggy script also exited non-zero, just later and only because the stubbed
    `npm` failed. So assert the guard is what spoke.
    """
    got = deploy("root@203.0.113.10")
    assert got.returncode != 0, "a deploy with no DOMAIN exited 0 and took HTTPS down"
    assert "refusing" in got.stderr, (
        "it failed, but not at the guard:\n" + got.stderr
    )
    assert not deploy.called("npm"), "it got as far as building"


def test_it_refuses_before_doing_anything_at_all(deploy):
    """Ordering is the half that matters.

    Refusing partway through would still leave /etc/caddy/Caddyfile overwritten
    with the literal `__DOMAIN__` template, which Caddy reads as a hostname
    matcher and serves nothing for. The guard has to land before the build, the
    rsync and the first ssh.
    """
    deploy("root@203.0.113.10")
    assert deploy.any_called() == [], (
        "the no-DOMAIN path ran outbound commands before refusing: "
        f"{deploy.any_called()}"
    )


def test_the_refusal_says_where_to_fix_it(deploy):
    """A refusal nobody can act on just gets worked around."""
    err = deploy("root@203.0.113.10").stderr
    assert "DOMAIN" in err
    assert ".deploy.env" in err, "say which file is missing"
    assert "safetospend.study" in err, "say what to put in it"
    assert "--no-domain" in err, "say how to ask for plain HTTP on purpose"
    assert "gitignored" in err, "say why a fresh worktree does not have one"


def test_a_domain_gets_past_the_guard(deploy):
    """The control: the guard refuses the empty case, not every case."""
    got = deploy("root@203.0.113.10", domain="safetospend.study")
    assert deploy.called("npm"), (
        "a configured deploy never reached the build:\n" + got.stderr
    )


def test_no_domain_flag_is_an_explicit_opt_in(deploy):
    """`:80` is still reachable — it just has to be chosen out loud."""
    got = deploy("root@203.0.113.10", "--no-domain")
    assert deploy.called("npm"), (
        "--no-domain did not get past the guard:\n" + got.stderr
    )
    assert "WARNING" in got.stderr, "downgrading to plain HTTP must be loud"


def test_an_unset_domain_is_not_quietly_read_as_no_domain(deploy):
    """The two cases must not collapse back into one.

    This is the whole fix in one assertion: absent means refuse, `--no-domain`
    means proceed. If a later edit makes absent mean `:80` again, this fails.
    """
    absent = deploy("root@203.0.113.10")
    assert absent.returncode != 0, "absent DOMAIN must refuse"
    assert not deploy.called("npm"), "absent DOMAIN must not start a deploy"

    deploy("root@203.0.113.10", "--no-domain")
    assert deploy.called("npm"), "--no-domain must proceed"


def test_an_unusable_domain_is_refused(deploy):
    """DOMAIN is written into a config through a sed delimited by `|`."""
    for bad in ("two words", "has|a|pipe", "__DOMAIN__"):
        got = deploy("root@203.0.113.10", domain=bad)
        assert got.returncode != 0, f"accepted {bad!r} as a site address"


def test_the_silent_fallback_is_gone_from_the_text():
    """Belt and braces, in the style of test_dist_location's deploy.sh grep.

    The runtime tests above cover behaviour; this one names the specific dead
    line so a revert is obvious in review rather than only at deploy time.
    """
    text = DEPLOY.read_text()
    assert 's|__DOMAIN__|:80|g' not in text, (
        "the silent :80 fallback is back; that is the site-down bug"
    )
    assert "--no-domain" in text, "the deliberate opt-in must stay reachable"


def test_the_caddyfile_is_rendered_before_it_ships():
    """No window where the box holds an unsubstituted template.

    Substituting on the box meant that any later failure — pip, systemd, the
    network — left /etc/caddy/Caddyfile as a literal `__DOMAIN__`, and the next
    reload from any source served nothing.
    """
    text = DEPLOY.read_text()
    assert "rendered_caddyfile" in text
    assert 'rsync -az Caddyfile ' not in text, "the raw template must not be shipped"
    # `sed -i` itself is fine and still used to pin OVERDRAFT_DIST in
    # /etc/overdraft-guard.env. It is editing the box's Caddyfile in place that
    # reopens the window.
    in_place_on_caddy = [
        line for line in text.splitlines()
        if "sed -i" in line and "caddy" in line.lower()
    ]
    assert not in_place_on_caddy, in_place_on_caddy
