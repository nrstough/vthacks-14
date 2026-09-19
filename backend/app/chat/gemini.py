"""A thin client for the Gemini API.

Plain REST over the standard library, on purpose. It is one endpoint and one
JSON shape, the SDK would be the only new dependency in the service, and
installing packages on venue wifi is not something to depend on.

Configuration is read from the environment at call time, so a key added to
`.env` while the server is running is picked up on the next request. The
`.env` at the repository root is loaded once, and only fills variables that
are not already set.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-3.8-flash"
# Tried in order when the model above is overloaded or missing. Every one is on
# the free tier. Override with GEMINI_FALLBACK_MODELS, comma separated.
DEFAULT_FALLBACKS = ("gemini-3.5-flash", "gemini-2.5-flash")
# Gemini statuses worth one more attempt on the same model before moving on.
TRANSIENT = {429, 500, 502, 503, 504}
# The key is wrong or forbidden: no other model will do better, stop at once.
FATAL = {401, 403}
RETRY_PAUSE_S = 1.5
DEFAULT_TIMEOUT_S = 25.0
MAX_OUTPUT_TOKENS = 600

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
_env_loaded = False


def load_dotenv_once(path: Path = _ENV_FILE) -> None:
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str | None
    model: str
    timeout_s: float
    fallbacks: tuple[str, ...] = DEFAULT_FALLBACKS

    @classmethod
    def from_env(cls) -> GeminiConfig:
        load_dotenv_once()
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None
        raw = os.environ.get("GEMINI_FALLBACK_MODELS")
        fallbacks = (
            tuple(m.strip() for m in raw.split(",") if m.strip()) if raw is not None else DEFAULT_FALLBACKS
        )
        return cls(
            api_key=key.strip() if key else None,
            model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            timeout_s=float(os.environ.get("GEMINI_TIMEOUT_S", DEFAULT_TIMEOUT_S)),
            fallbacks=fallbacks,
        )

    def models(self) -> list[str]:
        """The primary, then each fallback once, in order, without repeats."""
        out: list[str] = []
        for m in (self.model, *self.fallbacks):
            if m and m not in out:
                out.append(m)
        return out


class GeminiError(Exception):
    """The upstream call failed. `status` is the HTTP status Gemini returned, if any."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _post_json(url: str, headers: dict[str, str], body: dict, timeout_s: float) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            payload = json.loads(e.read().decode())
            detail = payload.get("error", {}).get("message", "") or ""
        except Exception:  # noqa: BLE001 - the body is best-effort context
            pass
        raise GeminiError(detail or f"Gemini returned HTTP {e.code}", status=e.code) from e
    except urllib.error.URLError as e:
        raise GeminiError(f"Could not reach Gemini: {e.reason}") from e
    except TimeoutError as e:
        raise GeminiError("Gemini did not answer in time") from e


def generate(
    config: GeminiConfig,
    system_instruction: str,
    turns: list[tuple[str, str]],
    temperature: float = 0.4,
    model: str | None = None,
) -> str:
    """One completion. `turns` is (role, text) with roles 'user' | 'assistant'."""
    if not config.api_key:
        raise GeminiError("GEMINI_API_KEY is not set")
    model = model or config.model

    body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [
            {"role": "model" if role == "assistant" else "user", "parts": [{"text": text}]}
            for role, text in turns
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": config.api_key,
    }
    payload = _post_json(ENDPOINT.format(model=model), headers, body, config.timeout_s)
    return extract_text(payload)


def generate_with_fallback(
    config: GeminiConfig,
    system_instruction: str,
    turns: list[tuple[str, str]],
    sleep=time.sleep,
) -> tuple[str, str]:
    """Try the primary model, then each fallback. Returns (text, model that answered).

    "High demand" on one model during a demo should cost a second, not the
    answer. A transient status gets one retry on the same model after a short
    pause, then the next model. A key problem stops everything at once, and
    the last error is what the caller sees.
    """
    last: GeminiError | None = None
    for model in config.models():
        for attempt in range(2):
            try:
                return generate(config, system_instruction, turns, model=model), model
            except GeminiError as e:
                last = e
                if e.status in FATAL:
                    raise
                if e.status in TRANSIENT and attempt == 0:
                    sleep(RETRY_PAUSE_S)
                    continue
                break
    assert last is not None
    raise last


def extract_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        reason = (payload.get("promptFeedback") or {}).get("blockReason")
        raise GeminiError(f"Gemini returned no answer{f' ({reason})' if reason else ''}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    if not text:
        raise GeminiError("Gemini returned an empty answer")
    return text
