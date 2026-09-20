"""Run the frozen pooled-transformer checkpoints on CPU, in NumPy.

The research lane's models are PyTorch. Torch is 200-odd MB, needs a wheel
for the box's exact Python, and this service installs from PyPI over venue
wifi — so the runtime here reimplements the forward pass with the NumPy the
solver's own dependency already brings in.

That is only safe because it is checked: `tools/forecast_parity.py` runs the
Torch reference and this implementation over the same inputs and requires
them to agree. An unchecked reimplementation of someone else's model is a
confident wrong answer, which is worse than no answer.

Architecture, from `forecasting/v3/models.py`: a linear projection of three
input channels to `width`, plus a FIXED sinusoidal position encoding, then
`layers` post-norm Transformer encoder blocks (multi-head attention, then a
feed-forward of `2 * width`, each with a residual and a LayerNorm), then a
mean over positions, concatenated with 43 auxiliary features, through a
16-unit ReLU layer and a softplus output of 14 days.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CONTEXT, HORIZON, AUXILIARY = 56, 14, 43
# The frozen pooled study, and the follow-up that anchors on the person's own
# baseline. Their tensors are identical in name, shape and count; only the
# FORWARD PASS differs, which is exactly the kind of difference that runs
# fine and returns the wrong numbers. See `forward`.
ARTIFACT_VERSIONS = ("pooled-forecast-v3-1", "personal-followup-1")
ANCHORED_RECIPES = ("anchor_mse", "anchor_prefix_mae")
SIZES = {
    "tiny": {"width": 32, "layers": 2, "heads": 2, "parameters": 18702},
    "small": {"width": 64, "layers": 2, "heads": 4, "parameters": 69230},
    "medium": {"width": 128, "layers": 4, "heads": 8, "parameters": 533550},
    "large": {"width": 256, "layers": 4, "heads": 8, "parameters": 2114734},
}


def _layer_norm(x: np.ndarray, weight: np.ndarray, bias: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    mean = x.mean(axis=-1, keepdims=True)
    # Torch's LayerNorm uses the BIASED variance, and matching it is the
    # difference between agreeing to 1e-6 and drifting in the last places.
    variance = x.var(axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(variance + eps) * weight + bias


def _softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - x.max(axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


def _softplus(x: np.ndarray) -> np.ndarray:
    # The numerically stable form; np.log1p(np.exp(x)) overflows past ~700.
    return np.maximum(x, 0) + np.log1p(np.exp(-np.abs(x)))


def _position_encoding(width: int) -> np.ndarray:
    positions = np.arange(CONTEXT, dtype=np.float64)[:, None]
    rates = np.exp(np.arange(0, width, 2, dtype=np.float64) * (-np.log(10000.0) / width))
    encoding = np.zeros((CONTEXT, width), dtype=np.float64)
    encoding[:, 0::2] = np.sin(positions * rates)
    encoding[:, 1::2] = np.cos(positions * rates)
    return encoding


@dataclass(frozen=True)
class Checkpoint:
    size: str
    seed: int
    weights: dict[str, np.ndarray]
    metadata: dict

    @property
    def spec(self) -> dict:
        return SIZES[self.size]

    @property
    def recipe(self) -> str:
        return self.metadata.get("recipe", "direct_mse")

    @property
    def anchored(self) -> bool:
        return self.recipe in ANCHORED_RECIPES


def load_checkpoint(path: str | Path) -> Checkpoint:
    """Strict, pickle-free load. Mirrors the reference loader's checks."""
    path = Path(path)
    with zipfile.ZipFile(path) as container:
        if sum(item.file_size for item in container.infolist()) > 64 * 1024 * 1024:
            raise ValueError("checkpoint exceeds the frozen model memory bound")
    with np.load(path, allow_pickle=False) as archive:
        raw = archive["metadata"]
        if raw.dtype != np.uint8 or raw.ndim != 1 or len(raw) > 2_000_000:
            raise ValueError("invalid checkpoint metadata")
        metadata = json.loads(raw.tobytes().decode())
        if metadata.get("artifact_version") not in ARTIFACT_VERSIONS:
            raise ValueError(f"unsupported checkpoint version: {metadata.get('artifact_version')}")
        if metadata.get("kind") != "forecast":
            raise ValueError("not a forecast checkpoint")
        size = metadata["size"]
        if size not in SIZES or metadata.get("architecture") != SIZES[size]:
            raise ValueError("checkpoint architecture metadata mismatch")
        if metadata.get("context_days") != CONTEXT or metadata.get("horizon_days") != HORIZON:
            raise ValueError("checkpoint window mismatch")
        weights = {
            key[len("weight::") :]: np.asarray(archive[key], dtype=np.float64)
            for key in archive.files
            if key.startswith("weight::")
        }
    expected = _expected_tensors(size)
    if set(weights) != expected:
        raise ValueError(f"unexpected or missing tensors: {sorted(set(weights) ^ expected)}")
    for name, value in weights.items():
        if not np.isfinite(value).all():
            raise ValueError(f"non-finite tensor: {name}")
    # A sanity check, not an equality: the reference builds this table in
    # float32, so `sin(positions * rates)` accumulates about 2e-6 of error
    # against the same expression in float64. The STORED table is what the
    # forward pass uses; this only catches a checkpoint whose fixed encoding
    # is not the canonical sinusoid at all.
    reference = _position_encoding(SIZES[size]["width"])
    if not np.allclose(weights["trunk.position_encoding"], reference, rtol=0, atol=1e-4):
        raise ValueError("the fixed position encoding is not the canonical sinusoid")
    return Checkpoint(size=size, seed=metadata.get("seed", -1), weights=weights, metadata=metadata)


def _expected_tensors(size: str) -> set[str]:
    names = {"trunk.mask_embedding", "trunk.position_encoding", "trunk.projection.weight", "trunk.projection.bias"}
    for layer in range(SIZES[size]["layers"]):
        stem = f"trunk.layers.{layer}."
        names.update(
            {
                stem + "self_attn.in_proj_weight",
                stem + "self_attn.in_proj_bias",
                stem + "self_attn.out_proj.weight",
                stem + "self_attn.out_proj.bias",
                stem + "linear1.weight",
                stem + "linear1.bias",
                stem + "linear2.weight",
                stem + "linear2.bias",
                stem + "norm1.weight",
                stem + "norm1.bias",
                stem + "norm2.weight",
                stem + "norm2.bias",
            }
        )
    names.update({"head.0.weight", "head.0.bias", "head.2.weight", "head.2.bias"})
    return names


def _attention(x: np.ndarray, w: dict[str, np.ndarray], stem: str, heads: int) -> np.ndarray:
    """Self-attention with no mask. Batch-first, exactly as the reference."""
    n, length, width = x.shape
    in_w = w[stem + "self_attn.in_proj_weight"]
    in_b = w[stem + "self_attn.in_proj_bias"]
    qkv = x @ in_w.T + in_b
    q, k, v = np.split(qkv, 3, axis=-1)
    head_dim = width // heads

    def split(t: np.ndarray) -> np.ndarray:
        return t.reshape(n, length, heads, head_dim).transpose(0, 2, 1, 3)

    q, k, v = split(q), split(k), split(v)
    scores = q @ k.transpose(0, 1, 3, 2) / np.sqrt(head_dim)
    context = _softmax(scores) @ v
    merged = context.transpose(0, 2, 1, 3).reshape(n, length, width)
    return merged @ w[stem + "self_attn.out_proj.weight"].T + w[stem + "self_attn.out_proj.bias"]


def forward(
    checkpoint: Checkpoint,
    sequence: np.ndarray,
    auxiliary: np.ndarray,
    baseline: np.ndarray | None = None,
) -> np.ndarray:
    """Normalised 14-day predictions for a batch.

    Two output paths, and choosing the wrong one still returns plausible
    numbers:

    * `direct_*`  -> softplus(head)
    * `anchor_*`  -> max(baseline + head, 0), with NO softplus

    The anchored recipes are the personalised ones. They are handed the
    person's own normalised weekday baseline and learn only its error —
    their output head is initialised to zeros, so an untrained anchored
    model IS the baseline. `baseline` is required for them and refused for
    the others, because silently ignoring it would hide a caller's mistake.
    """
    sequence = np.asarray(sequence, dtype=np.float64)
    auxiliary = np.asarray(auxiliary, dtype=np.float64)
    if sequence.ndim != 3 or sequence.shape[1:] != (CONTEXT, 3):
        raise ValueError("sequence must be N x 56 x 3")
    if auxiliary.shape != (sequence.shape[0], AUXILIARY):
        raise ValueError("auxiliary must be N x 43")

    w = checkpoint.weights
    spec = checkpoint.spec
    hidden = sequence @ w["trunk.projection.weight"].T + w["trunk.projection.bias"]
    hidden = hidden + w["trunk.position_encoding"][None]

    for layer in range(spec["layers"]):
        stem = f"trunk.layers.{layer}."
        # Post-norm: residual first, then the norm. Pre-norm would run and
        # give plausible, wrong numbers.
        attended = _attention(hidden, w, stem, spec["heads"])
        hidden = _layer_norm(hidden + attended, w[stem + "norm1.weight"], w[stem + "norm1.bias"])
        inner = np.maximum(hidden @ w[stem + "linear1.weight"].T + w[stem + "linear1.bias"], 0.0)
        projected = inner @ w[stem + "linear2.weight"].T + w[stem + "linear2.bias"]
        hidden = _layer_norm(hidden + projected, w[stem + "norm2.weight"], w[stem + "norm2.bias"])

    pooled = hidden.mean(axis=1)
    joined = np.concatenate((pooled, auxiliary), axis=1)
    head = np.maximum(joined @ w["head.0.weight"].T + w["head.0.bias"], 0.0)
    raw = head @ w["head.2.weight"].T + w["head.2.bias"]

    if not checkpoint.anchored:
        if baseline is not None:
            raise ValueError("a direct checkpoint takes no baseline")
        return _softplus(raw)

    if baseline is None:
        raise ValueError(f"{checkpoint.recipe} needs the normalised weekday baseline")
    baseline = np.asarray(baseline, dtype=np.float64)
    if baseline.shape != raw.shape:
        raise ValueError("baseline must be N x 14, matching the horizon")
    combined = baseline + raw
    return np.where(combined >= 0, combined, 0.0)


def ensemble(
    checkpoints: list[Checkpoint],
    sequence: np.ndarray,
    auxiliary: np.ndarray,
    baseline: np.ndarray | None = None,
) -> np.ndarray:
    """Equal-weight mean of the members' PREDICTIONS, never of their weights.

    Averaging predictions is not the same as averaging the members' scores,
    and it is not the same as picking the best member. Picking would be
    selection on the very data being scored.
    """
    if not checkpoints:
        raise ValueError("an ensemble needs at least one member")
    stacked = np.stack(
        [forward(c, sequence, auxiliary, baseline if c.anchored else None) for c in checkpoints]
    )
    return stacked.mean(axis=0)
