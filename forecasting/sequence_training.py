"""Reproducible CPU training, leak-resistant masked SSL and safe NPZ predictors.

The caller freezes source membership and target windows before calling this
module. No file paths, test splits or external case-study rows are discovered
automatically. Targets/amounts are in native major units, never converted.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

import numpy as np
import torch
from torch import nn

from forecasting.models import features
from forecasting.sequence_models import KINDS, SequenceModel, make_model, parameter_count

ARTIFACT_VERSION = "forecast-sequence-v2"


def _float32(array: np.ndarray) -> torch.Tensor:
    result = np.asarray(array, dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError("array is nonfinite or overflows float32")
    return torch.from_numpy(np.ascontiguousarray(result))


def _calendar(origins: np.ndarray) -> np.ndarray:
    weekdays = (origins[:, None] + np.arange(-56, 0) + 3) % 7
    return np.stack((np.sin(2 * np.pi * weekdays / 7),
                     np.cos(2 * np.pi * weekdays / 7)), axis=-1)


def input_arrays(history: np.ndarray, origins: np.ndarray,
                 feature_mean: np.ndarray, feature_std: np.ndarray):
    x, scale, _ = features(history, origins)
    mean, std = np.asarray(feature_mean), np.asarray(feature_std)
    if mean.shape != (99,) or std.shape != (99,) or not np.isfinite(mean).all() \
            or not np.isfinite(std).all() or (std <= 0).any():
        raise ValueError("invalid train-fitted standardizer")
    normalized = (x - mean) / std
    sequence = np.concatenate((x[:, :56, None], _calendar(np.asarray(origins))), axis=-1)
    return (_float32(sequence), _float32(normalized[:, 56:]),
            _float32(normalized), scale)


def masked_ssl_inputs(history: np.ndarray, origins: np.ndarray,
                      starts: np.ndarray):
    """Hide seven days and derive scale only from visible final-28-day amounts.

    Returned inputs and scale are invariant to any change in the hidden values.
    The target necessarily changes; it is used only inside the masked loss.
    """
    # Validation intentionally does not compute a hidden-dependent statistic.
    history = np.asarray(history, dtype=np.float64)
    origins, starts = np.asarray(origins), np.asarray(starts)
    n = len(history)
    if history.shape != (n, 56) or not n or not np.isfinite(history).all() or (history < 0).any():
        raise ValueError("history must be nonempty finite nonnegative N x 56")
    if origins.shape != (n,) or origins.dtype.kind not in "iu":
        raise ValueError("origins must be integer Unix days")
    if starts.shape != (n,) or starts.dtype.kind not in "iu" or ((starts < 0) | (starts > 49)).any():
        raise ValueError("mask starts must be integer offsets from zero through 49")
    days = np.arange(56)[None, :]
    mask = (days >= starts[:, None]) & (days < starts[:, None] + 7)
    visible = np.where(mask, 0., history)
    scale = np.maximum(visible[:, -28:].sum(axis=1) / (~mask[:, -28:]).sum(axis=1), 1.)
    sequence = np.concatenate(((visible / scale[:, None])[:, :, None], _calendar(origins)), axis=-1)
    return _float32(sequence), torch.from_numpy(mask), _float32(history / scale[:, None]), scale


def _state_copy(model: nn.Module) -> dict[str, torch.Tensor]:
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def _load_state_strict(model: nn.Module, state: dict[str, Any]) -> None:
    expected = model.state_dict()
    if set(state) != set(expected):
        raise ValueError("checkpoint keys do not match the frozen architecture")
    converted = {}
    for key, reference in expected.items():
        value = torch.as_tensor(state[key]).detach().cpu()
        if value.shape != reference.shape or value.dtype != reference.dtype or not torch.isfinite(value).all():
            raise ValueError(f"invalid checkpoint tensor: {key}")
        if key.endswith("position_encoding") and not torch.equal(value, reference):
            raise ValueError("fixed positional encoding was changed")
        converted[key] = value.clone()
    model.load_state_dict(converted, strict=True)


@dataclass
class ForecastPredictor:
    model: SequenceModel
    feature_mean: np.ndarray
    feature_std: np.ndarray
    metadata: dict[str, Any]

    @property
    def kind(self) -> str:
        return self.model.kind

    def predict(self, history: np.ndarray, origins: np.ndarray,
                batch_size: int = 1024) -> np.ndarray:
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        sequence, auxiliary, flat, scale = input_arrays(history, origins, self.feature_mean, self.feature_std)
        self.model.eval()
        predictions = []
        with torch.inference_mode():
            for start in range(0, len(sequence), batch_size):
                end = start + batch_size
                predictions.append(self.model(sequence[start:end], auxiliary[start:end], flat[start:end]).numpy())
        predicted = np.concatenate(predictions).astype(np.float64) * scale[:, None]
        if not np.isfinite(predicted).all() or (predicted < 0).any():
            raise ValueError("predictor produced invalid forecasts")
        return predicted

    def encoder_state(self) -> dict[str, torch.Tensor]:
        if self.kind != "transformer":
            raise ValueError("transfer study accepts the Transformer trunk only")
        return _state_copy(self.model.trunk)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        if path.suffix != ".npz":
            raise ValueError("predictor artifact path must end with .npz")
        # Reject malformed in-memory models as well as corrupt disk artifacts.
        _load_state_strict(make_model(self.kind), _state_copy(self.model))
        input_arrays(np.zeros((1, 56)), np.array([0]), self.feature_mean, self.feature_std)
        metadata = {**self.metadata, "artifact_version": ARTIFACT_VERSION, "kind": self.kind,
                    "context_days": 56, "horizon_days": 14,
                    "parameter_count": parameter_count(self.model)}
        arrays = {"metadata": np.frombuffer(json.dumps(metadata, allow_nan=False, sort_keys=True).encode(), dtype=np.uint8),
                  "feature_mean": np.asarray(self.feature_mean, dtype=np.float64),
                  "feature_std": np.asarray(self.feature_std, dtype=np.float64)}
        arrays.update({"weight::" + key: value.numpy() for key, value in _state_copy(self.model).items()})
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **arrays)
        return path


def load_predictor(path: str | Path) -> ForecastPredictor:
    with np.load(path, allow_pickle=False) as archive:
        metadata_bytes = archive["metadata"]
        if metadata_bytes.dtype != np.uint8 or metadata_bytes.ndim != 1 or len(metadata_bytes) > 1_000_000:
            raise ValueError("invalid checkpoint metadata")
        metadata = json.loads(metadata_bytes.tobytes().decode())
        if not isinstance(metadata, dict) or metadata.get("artifact_version") != ARTIFACT_VERSION \
                or metadata.get("kind") not in KINDS or metadata.get("context_days") != 56 \
                or metadata.get("horizon_days") != 14:
            raise ValueError("unsupported predictor metadata")
        model = make_model(metadata["kind"])
        if metadata.get("parameter_count") != parameter_count(model):
            raise ValueError("parameter count disagrees with architecture")
        keys = {"metadata", "feature_mean", "feature_std"} | {"weight::" + key for key in model.state_dict()}
        if set(archive.files) != keys or len(archive.files) != len(keys):
            raise ValueError("unexpected, duplicate or missing checkpoint arrays")
        _load_state_strict(model, {key: archive["weight::" + key] for key in model.state_dict()})
        mean, std = archive["feature_mean"].copy(), archive["feature_std"].copy()
        if mean.dtype != np.float64 or std.dtype != np.float64:
            raise ValueError("invalid standardizer dtype")
        input_arrays(np.zeros((1, 56)), np.array([0]), mean, std)
    return ForecastPredictor(model.eval(), mean, std, metadata)


def _config(config: dict[str, Any]) -> dict[str, Any]:
    result = {"max_epochs": 60, "patience": 10, "batch_size": 256, "learning_rate": .001,
              "gradient_norm_clip": 5., "max_seconds": 240., **config}
    for key in ("max_epochs", "patience", "batch_size"):
        if not isinstance(result[key], int) or isinstance(result[key], bool) or result[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    for key in ("learning_rate", "gradient_norm_clip", "max_seconds"):
        if not np.isfinite(result[key]) or result[key] <= 0:
            raise ValueError(f"{key} must be finite and positive")
    return result


def _target(target: np.ndarray, n: int) -> np.ndarray:
    target = np.asarray(target, dtype=np.float64)
    if target.shape != (n, 14) or not np.isfinite(target).all() or (target < 0).any():
        raise ValueError("target must be finite nonnegative N x 14")
    return target


def fit_model(kind: str, train_history: np.ndarray, train_y: np.ndarray,
              train_origins: np.ndarray, val_history: np.ndarray, val_y: np.ndarray,
              val_origins: np.ndarray, config: dict[str, Any], seed: int,
              init_encoder: dict[str, torch.Tensor] | None = None,
              fixed_updates: int | None = None):
    """Train only supplied training rows; checkpoint on validation cumulative MAE.

    fixed_updates disables patience/max-epoch stopping and runs that exact number
    of updates unless the explicitly supplied wall-time cap intervenes. A partial
    final epoch is validated, but does not count as a completed epoch.
    """
    config = _config(config)
    if fixed_updates is not None and (not isinstance(fixed_updates, int) or isinstance(fixed_updates, bool) or fixed_updates <= 0):
        raise ValueError("fixed_updates must be a positive integer")
    preparation_start = time.monotonic()
    model = make_model(kind, seed)
    if init_encoder is not None:
        if kind != "transformer":
            raise ValueError("encoder initialization is supported only for Transformer")
        _load_state_strict(model.trunk, init_encoder)
    train_x, _, _ = features(train_history, train_origins)
    mean, std = train_x.mean(axis=0), np.maximum(train_x.std(axis=0), .1)
    train_sequence, train_aux, train_flat, train_scale = input_arrays(train_history, train_origins, mean, std)
    train_y = _target(train_y, len(train_history))
    val_y = _target(val_y, len(val_history))
    target = _float32(train_y / train_scale[:, None])
    val_sequence, val_aux, val_flat, val_scale = input_arrays(val_history, val_origins, mean, std)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    rng = np.random.default_rng(seed)
    predictor = ForecastPredictor(model, mean, std, {"seed": seed, "config": config})
    preparation_seconds = time.monotonic() - preparation_start
    started = time.monotonic()
    best_score, best_epoch, best_update, bad = float("inf"), 0, 0, 0
    checkpoint = _state_copy(model)
    updates = examples = completed_epochs = 0
    records = []
    stop_reason = "max_epochs"
    epoch = 0
    while fixed_updates is not None or epoch < config["max_epochs"]:
        epoch += 1
        model.train()
        order = rng.permutation(len(train_y))
        epoch_loss, epoch_examples = 0., 0
        batches = 0
        complete = True
        for start in range(0, len(order), config["batch_size"]):
            if time.monotonic() - started >= config["max_seconds"]:
                stop_reason, complete = "time_cap", False
                break
            ix = order[start:start + config["batch_size"]]
            optimizer.zero_grad(set_to_none=True)
            prediction = model(train_sequence[ix], train_aux[ix], train_flat[ix])
            loss = torch.mean((prediction - target[ix]) ** 2)
            if not torch.isfinite(loss):
                raise ValueError("nonfinite training loss")
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), config["gradient_norm_clip"], error_if_nonfinite=True)
            optimizer.step()
            updates += 1
            batches += 1
            examples += len(ix)
            epoch_examples += len(ix)
            epoch_loss += float(loss.detach()) * len(ix)
            if fixed_updates is not None and updates >= fixed_updates:
                stop_reason = "fixed_updates"
                complete = start + config["batch_size"] >= len(order)
                break
        if complete:
            completed_epochs += 1
        if batches:
            model.eval()
            errors = []
            with torch.inference_mode():
                for start in range(0, len(val_y), 1024):
                    end = start + 1024
                    prediction = model(val_sequence[start:end], val_aux[start:end], val_flat[start:end]).numpy()
                    errors.append(np.abs((prediction * val_scale[start:end, None]).sum(axis=1) - val_y[start:end].sum(axis=1)))
            score = float(np.concatenate(errors).mean())
            if not np.isfinite(score):
                raise ValueError("nonfinite validation score")
            record = {"epoch": epoch, "completed": complete, "updates": updates,
                      "normalized_train_mse": epoch_loss / epoch_examples,
                      "validation_14day_mae": score,
                      "elapsed_seconds": time.monotonic() - started}
            records.append(record)
            if score < best_score:
                best_score, best_epoch, best_update, bad = score, epoch, updates, 0
                checkpoint = _state_copy(model)
            else:
                bad += 1
        if stop_reason in ("time_cap", "fixed_updates"):
            break
        if fixed_updates is None and bad >= config["patience"]:
            stop_reason = "patience"
            break
    elapsed = time.monotonic() - started
    if not updates:
        raise RuntimeError("training time cap reached before any optimizer update")
    _load_state_strict(model, checkpoint)
    model.eval()
    log = {"kind": kind, "seed": seed, "parameter_count": parameter_count(model),
           "best_epoch": best_epoch, "best_update": best_update, "epochs_run": completed_epochs,
           "epochs_started": epoch, "validation_14day_mae": best_score,
           "validation_history": records, "optimizer_updates": updates,
           "updates": updates, "selected_checkpoint_updates": best_update,
           "examples_processed": examples, "unique_training_examples": len(train_y),
           "examples_seen": examples,
           "stop_reason": stop_reason, "fixed_updates_requested": fixed_updates,
           "fixed_updates_reached": fixed_updates is not None and updates == fixed_updates,
           "preparation_seconds": preparation_seconds, "training_seconds": elapsed,
           "eligible_three_epochs": completed_epochs >= 3}
    predictor.metadata["training"] = log
    return predictor, log


def pretrain_ssl(train_history: np.ndarray, train_origins: np.ndarray,
                 config: dict[str, Any], seed: int,
                 init_encoder: dict[str, torch.Tensor] | None = None):
    """Train masked reconstruction on exactly the supplied training histories.

    Returns final encoder weights. No validation/test data or future targets are
    accepted. The forecast head is excluded from optimization and remains equal
    to its seeded scratch initialization, enabling paired downstream controls.
    """
    config = _config(config)
    max_updates = config.get("max_updates")
    if max_updates is not None and (not isinstance(max_updates, int) or isinstance(max_updates, bool) or max_updates <= 0):
        raise ValueError("max_updates must be a positive integer")
    # Check the complete arrays before a timed run, without fitting a normalizer.
    history = np.asarray(train_history, dtype=np.float64)
    origins = np.asarray(train_origins)
    masked_ssl_inputs(history, origins, np.zeros(len(history), dtype=np.int64))
    model = make_model("transformer", seed)
    if init_encoder is not None:
        _load_state_strict(model.trunk, init_encoder)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed + 100_003)
        reconstruction_head = nn.Linear(32, 1)
    initial_forecast_head = _state_copy(model.head)
    parameters = list(model.trunk.parameters()) + list(reconstruction_head.parameters())
    optimizer = torch.optim.Adam(parameters, lr=config["learning_rate"])
    rng = np.random.default_rng(seed)
    started = time.monotonic()
    updates = examples = completed_epochs = 0
    records = []
    stop_reason = "max_epochs"
    for epoch in range(1, config["max_epochs"] + 1):
        order = rng.permutation(len(history))
        epoch_loss, epoch_examples = 0., 0
        complete = True
        for start in range(0, len(order), config["batch_size"]):
            if time.monotonic() - started >= config["max_seconds"]:
                stop_reason, complete = "time_cap", False
                break
            ix = order[start:start + config["batch_size"]]
            starts = rng.integers(0, 50, size=len(ix))
            sequence, mask, target, _ = masked_ssl_inputs(history[ix], origins[ix], starts)
            optimizer.zero_grad(set_to_none=True)
            reconstruction = reconstruction_head(model.trunk(sequence, mask)).squeeze(-1)
            loss = torch.mean((reconstruction[mask] - target[mask]) ** 2)
            if not torch.isfinite(loss):
                raise ValueError("nonfinite SSL reconstruction loss")
            loss.backward()
            nn.utils.clip_grad_norm_(parameters, config["gradient_norm_clip"], error_if_nonfinite=True)
            optimizer.step()
            updates += 1
            examples += len(ix)
            epoch_examples += len(ix)
            epoch_loss += float(loss.detach()) * len(ix)
            if max_updates is not None and updates >= max_updates:
                stop_reason = "max_updates"
                complete = start + config["batch_size"] >= len(order)
                break
        if complete:
            completed_epochs += 1
        if epoch_examples:
            records.append({"epoch": epoch, "completed": complete, "updates": updates,
                            "masked_normalized_mse": epoch_loss / epoch_examples,
                            "elapsed_seconds": time.monotonic() - started})
        if stop_reason in ("time_cap", "max_updates"):
            break
    if not updates:
        raise RuntimeError("SSL time cap reached before any optimizer update")
    if any(not torch.equal(value, model.head.state_dict()[key]) for key, value in initial_forecast_head.items()):
        raise AssertionError("SSL modified the forecast head")
    return _state_copy(model.trunk), {
        "kind": "transformer_masked_ssl", "seed": seed,
        "encoder_parameters": parameter_count(model.trunk),
        "reconstruction_parameters": parameter_count(reconstruction_head),
        "optimizer_updates": updates, "examples_processed": examples,
        "updates": updates, "examples_seen": examples,
        "unique_training_examples": len(history), "epochs_run": completed_epochs,
        "training_seconds": time.monotonic() - started, "stop_reason": stop_reason,
        "training_history": records, "forecast_head_unchanged": True,
        "checkpoint_selection": "last completed optimizer update; no validation/test inputs",
        "mask_policy": "one uniformly located contiguous 7-day patch in each 56-day history",
        "scale_policy": "max(mean(visible final 28 days), 1); no hidden-value summaries",
    }
