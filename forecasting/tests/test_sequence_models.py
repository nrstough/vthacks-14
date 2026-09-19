"""Admission tests for fixed architectures and leakage-sensitive SSL contracts."""
import json

import numpy as np
import pytest
import torch

from forecasting.models import features
from forecasting.sequence_models import KINDS, CausalBlock, make_model, parameter_count
from forecasting.sequence_training import (
    ForecastPredictor, fit_model, input_arrays, load_predictor,
    masked_ssl_inputs, pretrain_ssl,
)


@pytest.fixture(autouse=True)
def small_thread_pool():
    previous = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(previous)


def sample_data(n=20):
    rng = np.random.default_rng(147)
    history = rng.gamma(2., 3., (n, 56))
    origins = np.arange(n, dtype=np.int64) * 15 + 17000
    target = rng.gamma(2., 3., (n, 14))
    return history, target, origins


@pytest.mark.parametrize("kind", KINDS)
def test_architecture_shapes_finite_nonnegative_and_autograd(kind):
    history, target, origins = sample_data(4)
    x, _, _ = features(history, origins)
    sequence, auxiliary, flat, _ = input_arrays(history, origins, x.mean(0), np.maximum(x.std(0), .1))
    model = make_model(kind, 11)
    model.train()
    predicted = model(sequence, auxiliary, flat)
    assert predicted.shape == (4, 14)
    assert torch.isfinite(predicted).all() and (predicted >= 0).all()
    loss = ((predicted - torch.tensor(target, dtype=torch.float32)) ** 2).mean()
    loss.backward()
    gradients = [p.grad for p in model.parameters() if p.grad is not None]
    assert gradients and all(torch.isfinite(g).all() for g in gradients)
    assert any(torch.any(g != 0) for g in gradients)
    assert 0 < parameter_count(model) < 50_000
    # Independently perturb the last bias, away from any ReLU boundaries.
    parameter = model.head[-2].bias
    analytic = float(parameter.grad[0])
    original, epsilon = float(parameter.detach()[0]), .01
    with torch.no_grad():
        parameter[0] = original + epsilon
        plus = float(((model(sequence, auxiliary, flat) - torch.tensor(target, dtype=torch.float32)) ** 2).mean())
        parameter[0] = original - epsilon
        minus = float(((model(sequence, auxiliary, flat) - torch.tensor(target, dtype=torch.float32)) ** 2).mean())
        parameter[0] = original
    assert analytic == pytest.approx((plus - minus) / (2 * epsilon), rel=.02, abs=.001)


def test_frozen_parameter_counts_and_rng_isolation():
    expected = {"mlp": 8942, "tcn": 15238, "gru": 11038, "transformer": 18702}
    state = torch.random.get_rng_state().clone()
    for kind in KINDS:
        model = make_model(kind, 23)
        assert parameter_count(model) == expected[kind]
        for a, b in zip(model.parameters(), make_model(kind, 23).parameters()):
            assert torch.equal(a, b)
    assert torch.equal(state, torch.random.get_rng_state())


def test_causal_convolution_cannot_read_later_history():
    torch.manual_seed(7)
    block = CausalBlock(3, 24, 8)
    original = torch.randn(2, 3, 56)
    changed = original.clone()
    changed[:, :, 40:] += 100
    torch.testing.assert_close(block(original)[:, :, :40], block(changed)[:, :, :40], rtol=0, atol=0)


def test_sequence_chronology_and_auxiliary_alignment():
    history = np.arange(56, dtype=float)[None, :]
    origins = np.array([4])  # 1970-01-05 was Monday.
    x, scale, _ = features(history, origins)
    sequence, aux, flat, observed_scale = input_arrays(history, origins, np.zeros(99), np.ones(99))
    np.testing.assert_allclose(sequence[0, :, 0], history[0] / scale[0])
    np.testing.assert_allclose(sequence[0, :, 1], np.sin(2 * np.pi * (np.arange(56) % 7) / 7), atol=1e-6)
    np.testing.assert_allclose(aux.numpy(), x[:, 56:], rtol=1e-6)
    np.testing.assert_allclose(flat.numpy(), x, rtol=1e-6)
    np.testing.assert_array_equal(observed_scale, scale)


def test_masked_values_cannot_leak_through_inputs_or_scale():
    history, _, origins = sample_data(50)
    starts = np.arange(50)
    original = masked_ssl_inputs(history, origins, starts)
    altered = history.copy()
    mask = original[1].numpy()
    altered[mask] = 9_999_999.
    changed = masked_ssl_inputs(altered, origins, starts)
    for ix in (0, 1):
        torch.testing.assert_close(original[ix], changed[ix], rtol=0, atol=0)
    np.testing.assert_array_equal(original[3], changed[3])
    assert (mask.sum(axis=1) == 7).all()
    assert torch.all(original[0][:, :, 0][original[1]] == 0)
    assert not torch.equal(original[2][original[1]], changed[2][changed[1]])
    np.testing.assert_allclose(original[3][49], max(history[49, 28:49].mean(), 1))


def test_mask_embedding_distinguishes_masked_from_observed_zero():
    model = make_model("transformer", 11)
    history = np.zeros((2, 56))
    sequence, mask, _, _ = masked_ssl_inputs(history, np.zeros(2, dtype=np.int64), np.array([0, 49]))
    with torch.no_grad():
        prediction = model.trunk(sequence, mask)
    assert not torch.equal(prediction[0], prediction[1])


@pytest.mark.parametrize("kind", KINDS)
def test_safe_serialization_roundtrip_and_corruption(tmp_path, kind):
    history, _, origins = sample_data(8)
    x, _, _ = features(history, origins)
    predictor = ForecastPredictor(make_model(kind, 47), x.mean(0), np.maximum(x.std(0), .1), {"source": "fixture"})
    path = predictor.save(tmp_path / f"{kind}.npz")
    expected = predictor.predict(history, origins)
    np.testing.assert_allclose(load_predictor(path).predict(history, origins), expected, rtol=0, atol=0)
    with np.load(path, allow_pickle=False) as artifact:
        arrays = {key: artifact[key].copy() for key in artifact.files}
    key = next(key for key in arrays if key.startswith("weight::") and key.endswith("bias"))
    arrays[key].flat[0] = np.nan
    np.savez_compressed(path, **arrays)
    with pytest.raises(ValueError, match="invalid checkpoint tensor"):
        load_predictor(path)


def test_artifact_rejects_shape_metadata_and_standardizer_corruption(tmp_path):
    predictor = ForecastPredictor(make_model("transformer", 11), np.zeros(99), np.ones(99), {})
    original = predictor.save(tmp_path / "original.npz")
    with np.load(original, allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in archive.files}
    for corruption in ("shape", "position", "std", "kind", "extra"):
        corrupted = {key: value.copy() for key, value in arrays.items()}
        if corruption == "shape":
            corrupted["weight::head.0.weight"] = np.zeros((16, 74), dtype=np.float32)
        elif corruption == "position":
            corrupted["weight::trunk.position_encoding"][0, 0] += 1
        elif corruption == "std":
            corrupted["feature_std"][0] = 0
        elif corruption == "kind":
            metadata = json.loads(corrupted["metadata"].tobytes())
            metadata["kind"] = "unsupported"
            corrupted["metadata"] = np.frombuffer(json.dumps(metadata).encode(), dtype=np.uint8)
        else:
            corrupted["arbitrary"] = np.ones(3)
        path = tmp_path / (corruption + ".npz")
        np.savez_compressed(path, **corrupted)
        with pytest.raises(ValueError):
            load_predictor(path)


def test_training_uses_train_only_statistics_and_exact_fixed_updates():
    history, target, origins = sample_data(20)
    val_history, val_target, val_origins = history[:4] * 1000, target[:4], origins[:4] + 1000
    config = {"max_epochs": 1, "patience": 1, "batch_size": 8, "max_seconds": 30}
    predictor, log = fit_model("mlp", history, target, origins, val_history, val_target, val_origins,
                               config, 11, fixed_updates=10)
    x, _, _ = features(history, origins)
    np.testing.assert_array_equal(predictor.feature_mean, x.mean(0))
    np.testing.assert_array_equal(predictor.feature_std, np.maximum(x.std(0), .1))
    assert log["optimizer_updates"] == 10 and log["fixed_updates_reached"]
    assert log["epochs_run"] == 3 and log["epochs_started"] == 4
    assert log["examples_processed"] == 68 and log["stop_reason"] == "fixed_updates"
    again, second = fit_model("mlp", history, target, origins, val_history, val_target, val_origins,
                              config, 11, fixed_updates=10)
    np.testing.assert_array_equal(predictor.predict(history, origins), again.predict(history, origins))
    assert second["validation_14day_mae"] == log["validation_14day_mae"]


def test_ssl_training_transfer_and_forecast_head_isolation(tmp_path):
    history, target, origins = sample_data(16)
    config = {"max_epochs": 2, "batch_size": 8, "max_seconds": 30}
    encoder, log = pretrain_ssl(history, origins, config, 11)
    initial = make_model("transformer", 11)
    assert log["forecast_head_unchanged"] and log["optimizer_updates"] == 4
    assert log["examples_processed"] == 32 and log["epochs_run"] == 2
    assert any(not torch.equal(value, initial.trunk.state_dict()[key]) for key, value in encoder.items())
    assert not any("head" in key for key in encoder)
    predictor, fine_tuning = fit_model("transformer", history, target, origins, history[:4], target[:4], origins[:4],
                                       config, 11, init_encoder=encoder)
    np.testing.assert_allclose(load_predictor(predictor.save(tmp_path / "ssl.npz")).predict(history, origins),
                               predictor.predict(history, origins), rtol=0, atol=0)
    assert fine_tuning["epochs_run"] == 2 and set(predictor.encoder_state()) == set(encoder)


def test_invalid_targets_and_mask_offsets_rejected():
    history, target, origins = sample_data(4)
    with pytest.raises(ValueError, match="mask starts"):
        masked_ssl_inputs(history, origins, np.array([0, 49, 50, 12]))
    with pytest.raises(ValueError, match="target"):
        fit_model("mlp", history, target[:, :13], origins, history, target, origins, {}, 11)
    with pytest.raises(ValueError, match="fixed_updates"):
        fit_model("mlp", history, target, origins, history, target, origins, {}, 11, fixed_updates=0)
