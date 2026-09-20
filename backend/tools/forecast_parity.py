"""Prove the NumPy runtime computes what the Torch reference computes.

Run with the RESEARCH interpreter, which has torch:

    R=/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast
    "$R/forecasting/.venv-v3/bin/python" backend/tools/forecast_parity.py

Read-only against the research worktree: it imports the frozen modules and
reads the frozen checkpoints, and writes nothing there.

Without this, the runtime is an unchecked reimplementation of someone
else's model — it would run, produce plausible numbers, and there would be
no way to tell whether they were the model's numbers or mine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RESEARCH = Path("/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast")
CHECKPOINTS = RESEARCH / "forecasting/artifacts/forecast-v3/runs"
HERE = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(RESEARCH))

from app.forecast import runtime  # noqa: E402

TOLERANCE = dict(rtol=1e-5, atol=1e-5)


def torch_reference(path: Path, sequence: np.ndarray, auxiliary: np.ndarray) -> np.ndarray:
    import torch
    from forecasting.v3.models import load_model

    model, _metadata = load_model(path, device="cpu")
    with torch.inference_mode():
        out = model(
            torch.from_numpy(sequence.astype(np.float32)),
            torch.from_numpy(auxiliary.astype(np.float32)),
        )
    return out.numpy().astype(np.float64)


def batches(rng: np.random.Generator) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Ordinary inputs and the shapes most likely to expose a wrong formula."""
    n = 24
    cases: list[tuple[str, np.ndarray, np.ndarray]] = []
    cases.append(
        ("random", rng.normal(size=(n, runtime.CONTEXT, 3)), rng.normal(size=(n, runtime.AUXILIARY)))
    )
    cases.append(("zeros", np.zeros((4, runtime.CONTEXT, 3)), np.zeros((4, runtime.AUXILIARY))))
    cases.append(("ones", np.ones((4, runtime.CONTEXT, 3)), np.ones((4, runtime.AUXILIARY))))
    # A constant sequence makes attention uniform; a spike makes it peaked.
    spike = np.zeros((2, runtime.CONTEXT, 3))
    spike[:, 30, 0] = 40.0
    cases.append(("spike", spike, rng.normal(size=(2, runtime.AUXILIARY))))
    big = rng.normal(size=(2, runtime.CONTEXT, 3)) * 50
    cases.append(("large", big, rng.normal(size=(2, runtime.AUXILIARY)) * 50))
    cases.append(
        ("single", rng.normal(size=(1, runtime.CONTEXT, 3)), rng.normal(size=(1, runtime.AUXILIARY)))
    )
    return cases


def preprocessing_parity() -> int:
    """The transform must match the reference's, not merely look like it."""
    from forecasting.v3.corpus import transform_input_arrays

    from app.forecast import preprocess

    checkpoint = runtime.load_checkpoint(CHECKPOINTS / "direct_small_seed_11" / "forecast.npz")
    mean, std, fallbacks = preprocess.normalisation(checkpoint.metadata)
    rng = np.random.default_rng(23)
    failures = 0

    keys = sorted(fallbacks)
    for label, history in (
        ("typical", np.abs(rng.normal(size=(16, 56)) * 80)),
        ("all zero", np.zeros((3, 56))),
        ("sparse", np.where(rng.random((8, 56)) < 0.15, rng.random((8, 56)) * 500, 0.0)),
        ("one spike", np.eye(56)[None, :6, :].reshape(6, 56) * 900),
        ("huge", np.abs(rng.normal(size=(4, 56))) * 1e6),
    ):
        n = len(history)
        origins = rng.integers(19000, 21000, size=n)
        chosen = [keys[i % len(keys)] for i in range(n)]
        source, currency, channel = zip(*(json.loads(k) for k in chosen))
        batch = {
            "history": history,
            "origin": origins,
            "source": np.array(source),
            "currency": np.array(currency),
            "channel": np.array(channel),
        }
        reference = transform_input_arrays(batch, fallbacks, mean, std)
        sequence, auxiliary, scale, anchor = preprocess.transform(
            history, origins, np.array([fallbacks[k] for k in chosen]), mean, std
        )
        expected_anchor = (reference["auxiliary"].astype(np.float64) * std + mean)[:, :14]
        for name, mine, theirs in (
            ("sequence", sequence, reference["sequence"].astype(np.float64)),
            ("auxiliary", auxiliary, reference["auxiliary"].astype(np.float64)),
            ("scale", scale, reference["scale"].astype(np.float64)),
            ("baseline", anchor, expected_anchor),
        ):
            close = np.allclose(mine, theirs, **TOLERANCE)
            if not close:
                failures += 1
            print(
                f"  {'ok  ' if close else 'FAIL'} transform {label:9s} {name:9s} "
                f"max|diff| = {float(np.abs(mine - theirs).max()):.3e}"
            )
    return failures


FOLLOWUP = RESEARCH / "forecasting/artifacts/forecast-small-followup/runs"


def anchored_parity() -> int:
    """The anchored recipes have a DIFFERENT forward pass, same tensors.

    Loading them with the direct path runs cleanly and returns the wrong
    numbers, which is the entire reason this file exists.
    """
    import torch

    from forecasting.small_followup.models import load_model as load_followup

    rng = np.random.default_rng(47)
    failures = 0
    for size in ("small", "medium", "large"):
        for seed in (11, 23, 47):
            path = FOLLOWUP / f"anchor_prefix_mae_{size}_seed_{seed}" / "forecast.npz"
            if not path.exists():
                continue
            mine_checkpoint = runtime.load_checkpoint(path)
            model, _meta = load_followup(path, device="cpu")
            for label, baseline in (
                ("zero base", np.zeros((6, 14))),
                ("small base", np.abs(rng.normal(size=(6, 14))) * 0.4),
                # Large enough that `baseline + raw` cannot go negative, and
                # small enough elsewhere that the clamp does bite.
                ("large base", np.abs(rng.normal(size=(6, 14))) * 40),
                ("negative-ish", rng.normal(size=(6, 14)) * 3),
            ):
                sequence = rng.normal(size=(6, runtime.CONTEXT, 3))
                auxiliary = rng.normal(size=(6, runtime.AUXILIARY))
                with torch.inference_mode():
                    theirs = model(
                        torch.from_numpy(sequence.astype(np.float32)),
                        torch.from_numpy(auxiliary.astype(np.float32)),
                        torch.from_numpy(baseline.astype(np.float32)),
                    ).numpy().astype(np.float64)
                mine = runtime.forward(mine_checkpoint, sequence, auxiliary, baseline)
                close = np.allclose(mine, theirs, **TOLERANCE)
                if not close:
                    failures += 1
                print(
                    f"  {'ok  ' if close else 'FAIL'} anchor {size}/seed {seed:2d} {label:12s} "
                    f"max|diff| = {float(np.abs(mine - theirs).max()):.3e}"
                )
    if failures == 0:
        # And prove the direct path would have been WRONG, so the branch is
        # load-bearing rather than decorative.
        path = FOLLOWUP / "anchor_prefix_mae_small_seed_11" / "forecast.npz"
        if path.exists():
            checkpoint = runtime.load_checkpoint(path)
            sequence = rng.normal(size=(4, runtime.CONTEXT, 3))
            auxiliary = rng.normal(size=(4, runtime.AUXILIARY))
            base = np.abs(rng.normal(size=(4, 14)))
            anchored = runtime.forward(checkpoint, sequence, auxiliary, base)
            object.__setattr__(checkpoint, "metadata", {**checkpoint.metadata, "recipe": "direct_mse"})
            direct = runtime.forward(checkpoint, sequence, auxiliary)
            print(
                f"  ok   the two paths really differ: max|anchored - direct| = "
                f"{float(np.abs(anchored - direct).max()):.3e}"
            )
    return failures


def main() -> int:
    rng = np.random.default_rng(11)
    failures = 0
    for size, seeds in (("small", (11, 23, 47)), ("tiny", (11,)), ("medium", (11,)), ("large", (11,))):
        for seed in seeds:
            path = CHECKPOINTS / f"direct_{size}_seed_{seed}" / "forecast.npz"
            if not path.exists():
                print(f"  {size}/{seed}: absent, skipped")
                continue
            checkpoint = runtime.load_checkpoint(path)
            for name, sequence, auxiliary in batches(rng):
                reference = torch_reference(path, sequence, auxiliary)
                mine = runtime.forward(checkpoint, sequence, auxiliary)
                close = np.allclose(mine, reference, **TOLERANCE)
                worst = float(np.abs(mine - reference).max())
                status = "ok  " if close else "FAIL"
                if not close:
                    failures += 1
                print(f"  {status} {size}/seed {seed:2d} {name:8s} max|diff| = {worst:.3e}")

    # The ensemble is a mean of PREDICTIONS; check that too, not just members.
    members = [runtime.load_checkpoint(CHECKPOINTS / f"direct_small_seed_{s}" / "forecast.npz") for s in (11, 23, 47)]
    sequence, auxiliary = rng.normal(size=(8, runtime.CONTEXT, 3)), rng.normal(size=(8, runtime.AUXILIARY))
    mine = runtime.ensemble(members, sequence, auxiliary)
    reference = np.mean(
        [torch_reference(CHECKPOINTS / f"direct_small_seed_{s}" / "forecast.npz", sequence, auxiliary) for s in (11, 23, 47)],
        axis=0,
    )
    close = np.allclose(mine, reference, **TOLERANCE)
    failures += 0 if close else 1
    print(f"  {'ok  ' if close else 'FAIL'} ensemble of three   max|diff| = {float(np.abs(mine - reference).max()):.3e}")

    failures += preprocessing_parity()
    failures += anchored_parity()

    print("\nPARITY PASSED" if failures == 0 else f"\nPARITY FAILED: {failures} case(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


