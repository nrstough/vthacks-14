"""A per-address rate limit for the one endpoint that costs money upstream.

`POST /api/chat` spends the server's Gemini key on every call. The request
body is already bounded — 40 turns of 4,000 characters — but the number of
requests is not, so anyone with the URL could loop the explainer until the
free tier is gone. During judging that reads as the explainer being broken.

Stateless for the user, like the rest of the service. A bucket holds a token
count and a timestamp per address: no request content, no conversation, no
identity, nothing written down. It dies with the process. This exists to stop
a loop from spending the key, not to identify anyone.

No new dependency. `slowapi` would be the obvious pick, but installing on
venue wifi is the recurring hazard every handoff in this repository names.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from math import ceil
from typing import Callable, NamedTuple

# Twenty a minute sustained, ten available at once. The judging room shares
# one NAT, so a tight limit breaks the demo; the failure this guards against
# is a loop, not a crowd. A person asking a question every few seconds never
# comes close.
SUSTAINED_PER_MINUTE = 20
BURST = 10

# A ceiling on the map of buckets, so the map itself is not a way to grow the
# process. See `_evict`.
MAX_KEYS = 4096


class Decision(NamedTuple):
    allowed: bool
    retry_after_s: int


@dataclass
class _Bucket:
    tokens: float
    at: float


class RateLimiter:
    """A token bucket per key, refilled continuously, safe across threads.

    The clock and the lock are injectable so the tests can be deterministic
    about time and explicit about the critical section.
    """

    def __init__(
        self,
        *,
        per_minute: int = SUSTAINED_PER_MINUTE,
        burst: int = BURST,
        max_keys: int = MAX_KEYS,
        clock: Callable[[], float] = time.monotonic,
        lock=None,
    ) -> None:
        self._rate = per_minute / 60.0
        self._burst = float(burst)
        self._max_keys = max_keys
        self._clock = clock
        self._lock = lock if lock is not None else threading.Lock()
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()
        self._off = False

    @classmethod
    def disabled(cls) -> RateLimiter:
        """A limiter that allows everything.

        For fixtures that post in bulk. Spelled out at the call site so an
        opt-out is never mistaken for the real thing.
        """
        limiter = cls()
        limiter._off = True
        return limiter

    def __len__(self) -> int:
        return len(self._buckets)

    def check(self, key: str) -> Decision:
        """Spend one token for `key`, or report how long until one exists."""
        if self._off:
            return Decision(True, 0)

        with self._lock:
            now = self._clock()
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=self._burst, at=now)
                self._buckets[key] = bucket
            else:
                self._buckets.move_to_end(key)
                elapsed = now - bucket.at
                # A clock that has not advanced adds nothing, and one that has
                # gone backwards — an NTP step — must not hand out free
                # requests. `time.monotonic` should make this impossible; the
                # guard costs one comparison.
                if elapsed > 0:
                    bucket.tokens = min(self._burst, bucket.tokens + elapsed * self._rate)
                    bucket.at = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                decision = Decision(True, 0)
            else:
                # A refused request is NOT charged. Charging it would let a
                # loop extend its own lockout indefinitely, which turns a rate
                # limit into a ban.
                wait = (1.0 - bucket.tokens) / self._rate
                decision = Decision(False, max(1, ceil(wait)))

            self._evict()
            return decision

    def _evict(self) -> None:
        """Hold the map to its ceiling. Caller holds the lock.

        A bucket at full capacity carries no information — forgetting it and
        meeting that address fresh are the same thing — so those go first.
        Past that it is least-recently-used, and every attempt moves its own
        key to the end, so an address that is currently hammering is never
        the one dropped.

        An actor with thousands of source addresses can force eviction, but
        such an actor defeats any per-address limit by rotating addresses
        anyway. This ceiling is a memory bound, not a security boundary.
        """
        if len(self._buckets) <= self._max_keys:
            return

        for key in [k for k, b in self._buckets.items() if b.tokens >= self._burst]:
            del self._buckets[key]
            if len(self._buckets) <= self._max_keys:
                return

        while len(self._buckets) > self._max_keys:
            self._buckets.popitem(last=False)


def client_key(request) -> str:
    """The address to count against.

    Host only, never the port: `request.client` is a (host, port) pair and the
    port changes with every connection, so keying on the pair would hand out a
    fresh budget per request and produce a limiter that does nothing while
    looking like it works.

    Behind Caddy the peer is loopback and the real address arrives in
    `X-Forwarded-For`. That header is NOT parsed here: uvicorn's
    ProxyHeadersMiddleware is on by default, trusts only the loopback peers
    named in the unit file, and resolves the list in reverse to the first
    untrusted hop — so a client that sends its own header cannot choose its
    key. One owner for that decision, and it is not this module.
    """
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return host or "unknown"
