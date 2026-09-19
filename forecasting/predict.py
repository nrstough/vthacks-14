"""Load an explicit saved model and emit dated, provenance-bearing forecasts."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from .models import predict_arrays

EPOCH = date(1970, 1, 1)


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("dates must be YYYY-MM-DD strings")
    return date.fromisoformat(value)


class Predictor:
    """Experimental point estimates; no calibrated uncertainty or solvency claim."""

    def __init__(self, model_path):
        self.path = Path(model_path)
        self.metadata = json.loads(self.path.read_text())
        required = {"format_version", "context_days", "horizon_days", "model_id", "kind", "source", "target", "currency", "experimental", "weights", "weights_sha256"}
        if not required <= self.metadata.keys():
            raise ValueError("incomplete model metadata")
        for field, expected in (("format_version", 1), ("context_days", 56), ("horizon_days", 14)):
            if type(self.metadata[field]) is not int or self.metadata[field] != expected:
                raise ValueError(f"unsupported model {field}")
        for field in ("model_id", "source", "currency"):
            if not isinstance(self.metadata[field], str) or not self.metadata[field].strip():
                raise ValueError(f"model {field} must be nonempty text")
        if self.metadata["target"] not in {"residual_outflow", "total_posted_outflow", "card_spending"}:
            raise ValueError("unsupported model target")
        if type(self.metadata["experimental"]) is not bool:
            raise ValueError("experimental must be boolean")
        weights_name = self.metadata["weights"]
        if not isinstance(weights_name, str) or Path(weights_name).name != weights_name:
            raise ValueError("weights must be a filename next to the metadata")
        weights_path = self.path.parent / weights_name
        if hashlib.sha256(weights_path.read_bytes()).hexdigest() != self.metadata["weights_sha256"]:
            raise ValueError("weights checksum mismatch")
        with np.load(weights_path, allow_pickle=False) as weights:
            self.state = {k: weights[k] for k in weights.files}
        kind = self.metadata["kind"]
        shapes = {}
        if kind == "neural":
            shapes = {"w1": (99, 64), "b1": (64,), "w2": (64, 32), "b2": (32,),
                      "w3": (32, 14), "b3": (14,)}
        elif kind == "ridge":
            shapes = {"coef": (100, 14)}
        elif kind not in {"recent_28day_mean", "weekday_8week_mean"}:
            raise ValueError("unsupported model kind")
        if kind in {"neural", "ridge"}:
            shapes.update(feature_mean=(99,), feature_std=(99,))
        if set(self.state) != set(shapes):
            raise ValueError("model weight names do not match declared kind")
        for key, shape in shapes.items():
            value = self.state[key]
            if value.shape != shape or value.dtype.kind not in "fiu" or not np.isfinite(value).all():
                raise ValueError(f"invalid model weight: {key}")
        if "feature_std" in self.state and np.any(self.state["feature_std"] <= 0):
            raise ValueError("model feature standard deviations must be positive")

    def predict(self, history, *, currency):
        """Require exactly 56 observed calendar days ending immediately before horizon.

        Each row has date, nonnegative amount in model currency, and observed=True.
        Missing dates, unobserved rows, and zero-by-imputation are not accepted.
        Caller is responsible for matching the model's target/accounting definition.
        """
        if currency != self.metadata["currency"]:
            raise ValueError("currency must match the saved model; conversion is not provided")
        if not isinstance(history, list) or len(history) != 56:
            raise ValueError("exactly 56 daily history rows required")
        dates, amounts = [], []
        for row in history:
            if not isinstance(row, dict) or set(row) != {"date", "amount", "observed"}:
                raise ValueError("history rows require exactly date, amount, observed")
            if row["observed"] is not True:
                raise ValueError("missing observations cannot be treated as zero spending")
            if isinstance(row["amount"], bool) or not isinstance(row["amount"], (int, float, str)):
                raise ValueError("amount must be numeric and not boolean")
            try:
                amount = float(row["amount"])
            except (ValueError, OverflowError) as error:
                raise ValueError("invalid amount") from error
            if not np.isfinite(amount) or amount < 0:
                raise ValueError("amounts must be finite and nonnegative")
            dates.append(iso_date(row["date"]))
            amounts.append(amount)
        if any(b != a + timedelta(days=1) for a, b in zip(dates, dates[1:])):
            raise ValueError("history must be sorted and contain every consecutive calendar date")
        origin = dates[-1] + timedelta(days=1)
        prediction = predict_arrays(self.metadata["kind"], self.state,
                                    np.asarray([amounts]), np.asarray([(origin - EPOCH).days]))[0]
        return {
            "model_id": self.metadata["model_id"], "source": self.metadata["source"],
            "target": self.metadata["target"], "currency": self.metadata["currency"],
            "experimental": self.metadata["experimental"], "context_end": dates[-1].isoformat(),
            "days": [{"date": (origin + timedelta(days=i)).isoformat(), "amount": float(value)}
                     for i, value in enumerate(prediction)],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True, help="JSON {currency, days:[{date,amount,observed}]}")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    history = json.loads(args.history.read_text())
    result = Predictor(args.model).predict(history["days"], currency=history["currency"])
    payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
