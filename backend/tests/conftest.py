"""Shared fixtures.

The oracle runner batches and memoises. Each parity test hands over its whole
list at once and gets one Node process for the requests not already seen, rather
than one per request — process startup would otherwise cost more than all the
solving put together. It is not a single process for the entire session: tests
that ask for overlapping sets pay only for what is new.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

DUMP_TS = Path(__file__).parent / "oracle" / "dump.ts"


def node_available() -> bool:
    return shutil.which("node") is not None


requires_node = pytest.mark.skipif(not node_available(), reason="needs Node >= 22 on PATH")


def run_oracle(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Solve a batch with the frontend's reference solver."""
    proc = subprocess.run(
        ["node", "--no-warnings", "--experimental-strip-types", str(DUMP_TS)],
        input=json.dumps(requests),
        capture_output=True,
        text=True,
        timeout=180,
        cwd=DUMP_TS.parent,
    )
    if proc.returncode != 0:
        raise AssertionError(f"oracle failed ({proc.returncode}):\n{proc.stderr[:2000]}")
    results = json.loads(proc.stdout)
    for i, r in enumerate(results):
        if not r["ok"]:
            raise AssertionError(f"oracle rejected request {i}: {r['error']}")
    return [r["response"] for r in results]


@pytest.fixture(scope="session")
def oracle():
    """Memoised batch solver: identical requests are only sent to Node once."""
    cache: dict[str, dict[str, Any]] = {}

    def solve_all(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        keys = [json.dumps(r, sort_keys=True) for r in requests]
        missing = [(k, r) for k, r in zip(keys, requests) if k not in cache]
        if missing:
            fresh = run_oracle([r for _, r in missing])
            for (k, _), response in zip(missing, fresh):
                cache[k] = response
        return [cache[k] for k in keys]

    return solve_all


def pytest_collection_modifyitems(config, items):
    """Keep the live Nessie tests off the network unless they are asked for.

    `addopts` in pytest.ini cannot do this on its own: a `-m` on the command line
    REPLACES the one in addopts rather than combining with it, so the documented
    gate `-m "not perf"` was quietly running the live sandbox test. It passed,
    which is the worst way to find out — a suite that depends on someone else's
    hackathon service being up, and on this laptop having wifi, is not a gate.

    Opt in with `-m nessie`, or by naming the test directly.
    """
    wanted = "nessie" in (config.getoption("-m") or "")
    if wanted:
        return
    skip = pytest.mark.skip(reason="live Nessie sandbox; opt in with -m nessie")
    for item in items:
        if "nessie" in item.keywords:
            item.add_marker(skip)
