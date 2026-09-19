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
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from app.chat.gemini import load_dotenv_once
from app.schemas import CENTS_ABS

DEFAULT_BASE_URL = "https://prod-api.nessieisreal.com"
DEFAULT_TIMEOUT_S = 20.0


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
    # Set NESSIE_ACCOUNT_ID to an account that was seeded earlier and the round
    # trip reads it instead of creating a new customer. Judging morning wants
    # reads, not twenty writes into someone else's sandbox.
    account_id: str | None = None

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
            account_id=(os.environ.get("NESSIE_ACCOUNT_ID") or "").strip() or None,
        )


def _url(config: NessieConfig, path: str) -> str:
    key = urllib.parse.quote(config.api_key or "", safe="")
    return f"{config.base_url}{path}?key={key}"


def _redact(url: str) -> str:
    """The key rides in the query string, so nothing may carry a full URL into a
    log, an exception message, or a traceback."""
    return url.split("?", 1)[0] + "?key=<redacted>"


def _scrub(config: NessieConfig, text: str) -> str:
    """Take the key out of anything the upstream or the socket layer wrote.

    `_redact` handles URLs we build. This handles strings we did not: Nessie
    echoes the request URL inside its own `message` on some errors, and a
    `URLError.reason` can carry it too. Either one lands in an exception the
    route turns into a 502 body, so the key would leave the box.
    """
    key = (config.api_key or "").strip()
    if not key:
        return text
    return text.replace(urllib.parse.quote(key, safe=""), "<redacted>").replace(
        key, "<redacted>"
    )


def _request(config: NessieConfig, method: str, path: str, body: dict | None = None) -> Any:
    url = _url(config, path)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=config.timeout_s) as resp:
            raw = resp.read().decode()
            if not raw.strip():
                return None
            try:
                # parse_float=Decimal: see the module docstring. The float is never built.
                return json.loads(raw, parse_float=Decimal)
            except ValueError as e:
                # An HTML error page or a proxy's plain text. Uncaught this is a
                # 500 with a stack trace; it is an upstream problem, not ours.
                raise NessieError(
                    f"Nessie answered with something other than JSON for {_redact(url)}"
                ) from e
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
            _scrub(config, detail) or f"Nessie returned HTTP {e.code} for {_redact(url)}",
            status=e.code,
        ) from e
    except urllib.error.URLError as e:
        raise NessieError(_scrub(config, f"Could not reach Nessie: {e.reason}")) from e
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
    # bool before anything else: bool is an int subclass, so a JSON `true` in an
    # amount field would otherwise become Decimal(1) and then $1.00, silently.
    if isinstance(amount, bool):
        raise NessieError(f"Nessie sent a boolean where an amount belongs: {amount!r}")
    # A float should never arrive — `_request` decodes with parse_float=Decimal —
    # so one reaching here means some other caller built it, and accepting it
    # would quietly reintroduce the 1998.9999999999998 problem this exists to
    # prevent. Refuse rather than convert.
    if isinstance(amount, float):
        raise NessieError(f"Nessie amounts must not be floats: {amount!r}")
    try:
        value = Decimal(amount) if not isinstance(amount, Decimal) else amount
    except (InvalidOperation, TypeError, ValueError) as e:
        raise NessieError(f"Nessie sent an amount that is not a number: {amount!r}") from e
    if not value.is_finite():
        raise NessieError(f"Nessie sent a non-finite amount: {amount!r}")

    # Check the precision BEFORE scaling, and check the DIGITS rather than the
    # exponent.
    #
    # Scaling first is wrong: `value * 100` runs in the default context of 28
    # significant digits, so Decimal("19.99000000000000000000000000001") rounds to
    # exactly 1999 during the multiply and the sub-cent check then finds nothing
    # wrong with it.
    #
    # The exponent alone is also wrong: Decimal("19.990") has exponent -3 and is
    # still exactly 1999 cents. Trailing zeros are precision, not value, and
    # refusing them would reject amounts a bank writes routinely.
    #
    # So: look at the digits past the hundredths place and require them to be
    # zero. This is exact arithmetic on the digit tuple, with no context and
    # nothing to round.
    digits = value.as_tuple().digits
    beyond_cents = -value.as_tuple().exponent - 2
    if beyond_cents > 0 and any(digits[-beyond_cents:]):
        raise NessieError(f"Nessie sent a sub-cent amount that cannot be exact: {amount!r}")

    # A local context wide enough for the whole coefficient, so the scale itself
    # cannot round what the check above just approved.
    with localcontext() as ctx:
        ctx.prec = len(digits) + 4
        out = int(value.scaleb(2).to_integral_value())
    if abs(out) > CENTS_ABS:
        raise NessieError(f"Nessie sent an amount outside the supported range: {amount!r}")
    return out
