"""Transport for the Capital One Nessie sandbox.

Plain REST over the standard library, for the same reason `chat/gemini.py` is:
it is a handful of endpoints and one JSON shape, and an SDK would be the only new
dependency in the service. `backend/requirements.txt` records why that matters —
every package is one more way the box's `pip install` dies, and the box has no
`wheels/` to fall back on.

Three things about this API, all measured against it on 2026-09-19 rather than
read in the docs:

  * A **wrong** key returns `200 []`, byte-identical to a valid key over an empty
    sandbox. There is no 401 and no 403.
  * A **missing** key returns `502 {"message": "Internal server error"}`, which
    looks exactly like an upstream outage.
  * Creation returns `201` with the created object and its `_id`, so no follow-up
    list call is needed. (The published docs say otherwise; they are wrong.)

The first of those is the important one: **a read can never confirm the key is
good**, so credentials are verified write-then-read and an empty list is treated
as unverified rather than as empty data. Anything else means a misconfigured box
shows a judge a blank account and no error.

Money never becomes a float. Nessie sends dollars as a JSON number, and
`json.loads` would hand back 19.99 as a float whose product with 100 is
1998.9999999999998 — `int()` of that is 1998, a cent short, silently. Decoding
uses `parse_float=Decimal` so the float is never constructed at all.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.chat.gemini import load_dotenv_once
from app.schemas import CENTS_ABS

DEFAULT_BASE_URL = "https://prod-api.nessieisreal.com"
DEFAULT_TIMEOUT_S = 20.0

# Worth one more attempt; the sandbox is a hackathon service and wobbles.
TRANSIENT = {429, 500, 503, 504}


class NessieError(Exception):
    """Transport-level failure. Never escapes this package; see __init__.py."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class NessieNotConfigured(NessieError):
    """The key is absent, or present and provably not working."""


@dataclass(frozen=True)
class NessieConfig:
    api_key: str | None
    base_url: str = DEFAULT_BASE_URL
    timeout_s: float = DEFAULT_TIMEOUT_S

    @classmethod
    def from_env(cls) -> NessieConfig:
        """Read at call time, so a key added to .env while the server is running
        is picked up on the next request. Same contract as GeminiConfig."""
        load_dotenv_once()
        key = os.environ.get("NESSIE_API_KEY") or None
        return cls(
            api_key=key.strip() if key else None,
            base_url=(os.environ.get("NESSIE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
            timeout_s=float(os.environ.get("NESSIE_TIMEOUT_S", DEFAULT_TIMEOUT_S)),
        )


def _url(config: NessieConfig, path: str) -> str:
    key = urllib.parse.quote(config.api_key or "", safe="")
    return f"{config.base_url}{path}?key={key}"


def _redact(url: str) -> str:
    """The key rides in the query string, so nothing may carry a full URL into a
    log, an exception message, or a traceback."""
    return url.split("?", 1)[0] + "?key=<redacted>"


def _request(config: NessieConfig, method: str, path: str, body: dict | None = None) -> Any:
    url = _url(config, path)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=config.timeout_s) as resp:
            raw = resp.read().decode()
            # parse_float=Decimal: see the module docstring. The float is never built.
            return json.loads(raw, parse_float=Decimal) if raw.strip() else None
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            payload = json.loads(e.read().decode())
            detail = payload.get("message", "") or ""
        except Exception:  # noqa: BLE001 - the body is best-effort context
            pass
        if e.code == 502 and not config.api_key:
            raise NessieNotConfigured(
                "No Nessie API key is configured on the server."
            ) from e
        raise NessieError(
            detail or f"Nessie returned HTTP {e.code} for {_redact(url)}", status=e.code
        ) from e
    except urllib.error.URLError as e:
        raise NessieError(f"Could not reach Nessie: {e.reason}") from e
    except TimeoutError as e:
        raise NessieError("Nessie did not answer in time") from e


def get(config: NessieConfig, path: str) -> Any:
    return _request(config, "GET", path)


def post(config: NessieConfig, path: str, body: dict) -> Any:
    return _request(config, "POST", path, body)


def to_cents(amount: Any) -> int:
    """Dollars from Nessie into integer cents, exactly or not at all.

    `_request` decodes with `parse_float=Decimal`, so `amount` arrives as a
    Decimal and no float has been constructed. A value with sub-cent precision is
    refused rather than rounded: this product's whole claim is that its
    arithmetic is exact, and a silently dropped tenth of a cent is the sort of
    thing that is only noticed when a balance disagrees with a bank's.
    """
    try:
        value = Decimal(amount) if not isinstance(amount, Decimal) else amount
    except (InvalidOperation, TypeError, ValueError) as e:
        raise NessieError(f"Nessie sent an amount that is not a number: {amount!r}") from e
    if not value.is_finite():
        raise NessieError(f"Nessie sent a non-finite amount: {amount!r}")
    cents = value * 100
    if cents != cents.to_integral_value():
        raise NessieError(f"Nessie sent a sub-cent amount that cannot be exact: {amount!r}")
    out = int(cents)
    if abs(out) > CENTS_ABS:
        raise NessieError(f"Nessie sent an amount outside the supported range: {amount!r}")
    return out
