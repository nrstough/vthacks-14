"""Measure the simulator: stylized facts, the answer key, and the decoy problem.

    ../../.venv/bin/python report.py                       # simulator only
    ../../.venv/bin/python report.py --sp500 sp500.csv.gz  # side by side with a real index
    ../../.venv/bin/python report.py --json out.json       # also write the numbers

`--sp500` takes any daily price CSV, gzipped or not, with a Date column and
an Adj Close or Close column. The figures in the README came from the S&P 500
file that ships inside the `arch` wheel on PyPI (arch/data/sp500/sp500.csv.gz,
1999-2018). It is not committed here: download the wheel and unzip that one
file.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import gzip
import json
import time

import numpy as np

from market_sim import (
    MarketConfig,
    StockConfig,
    annualized_sharpe,
    oracle_returns,
    oracle_sharpe_theory,
    signal_returns,
    simulate,
)
from market_sim.facts import acf, check_cross_section, check_index

YEARS = (1, 3, 5, 10)
BLOCK = 250


def load_prices(path: str) -> np.ndarray:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", newline="") as f:
        rows = list(csv.DictReader(f))
    column = "Adj Close" if "Adj Close" in rows[0] else "Close"
    return np.array([float(r[column]) for r in rows])


def block_bootstrap(x: np.ndarray, n: int, seed: int = 1) -> list[np.ndarray]:
    """Resample whole 250-day blocks, which keeps volatility clustering intact."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        starts = rng.integers(0, len(x) - BLOCK, len(x) // BLOCK + 1)
        out.append(np.concatenate([x[s : s + BLOCK] for s in starts])[: len(x)])
    return out


def market_factor(n_days: int, seed: int) -> np.ndarray:
    # The market factor has its own streams, so it is the same series the
    # default market gets; skipping the stocks and signals only saves time.
    cfg = MarketConfig(n_days=n_days, stocks=StockConfig(n_assets=2), signals=(), n_decoys=0)
    return simulate(cfg, seed=seed).truth.market_return


def facts_section(real: np.ndarray | None, n_seeds: int) -> tuple[list[str], dict]:
    n_days = len(real) if real is not None else 20 * 252
    sims = [check_index(market_factor(n_days, s)) for s in range(n_seeds)]
    names = [f.name for f in sims[0]]
    raw_rules = [f.rule for f in sims[0]]
    # Rules like max |ACF(r)| carry pipes, which would split a markdown cell.
    rules = [r.replace("|", "\\|") for r in raw_rules]
    values = np.array([[f.value for f in row] for row in sims])
    passed = np.array([[f.passed for f in row] for row in sims])
    gaussian = check_index(np.random.default_rng(0).standard_normal(n_days) * 0.012)

    lines = [f"## Stylized facts: {n_seeds} simulated paths of {n_days} days", ""]
    data = {"n_days": n_days, "facts": []}
    if real is not None:
        real_facts = check_index(real)
        boot = np.array([[f.value for f in check_index(b)] for b in block_bootstrap(real, 200)])
        lo, hi = np.percentile(boot, 5, axis=0), np.percentile(boot, 95, axis=0)
        inside = ((values >= lo) & (values <= hi)).mean(axis=0)
        lines += [
            "| Fact | Rule | S&P 500 | its 90% band | Simulated median | Sim in band | Sim passes | Gaussian |",
            "|---|---|---:|---|---:|---:|---:|---:|",
        ]
        for i, name in enumerate(names):
            lines.append(
                f"| {name} | {rules[i]} | {real_facts[i].value:.3f} | {lo[i]:.3f} to {hi[i]:.3f} "
                f"| {np.median(values[:, i]):.3f} | {inside[i]:.0%} | {passed[:, i].mean():.0%} "
                f"| {gaussian[i].value:.3f}{'' if gaussian[i].passed else ' (fails)'} |"
            )
            data["facts"].append(
                dict(
                    name=name,
                    rule=raw_rules[i],
                    real=real_facts[i].value,
                    band=[lo[i], hi[i]],
                    sim_median=float(np.median(values[:, i])),
                    sim_in_band=float(inside[i]),
                    sim_pass=float(passed[:, i].mean()),
                    gaussian=gaussian[i].value,
                )
            )
        lines += [
            "",
            "The band is the 5th to 95th percentile of the index's own statistic over 200 block-bootstrap",
            f"resamples ({BLOCK}-day blocks). A perfect simulator would not land in it every time: the band is",
            "centred on the one real sample rather than on the truth, so with equal noise on both sides the",
            "expected in-band share is about 75%.",
        ]
    else:
        lines += ["| Fact | Rule | Simulated median | Sim passes | Gaussian |", "|---|---|---:|---:|---:|"]
        for i, name in enumerate(names):
            lines.append(
                f"| {name} | {rules[i]} | {np.median(values[:, i]):.3f} | {passed[:, i].mean():.0%} "
                f"| {gaussian[i].value:.3f}{'' if gaussian[i].passed else ' (fails)'} |"
            )
            data["facts"].append(
                dict(
                    name=name,
                    rule=raw_rules[i],
                    sim_median=float(np.median(values[:, i])),
                    sim_pass=float(passed[:, i].mean()),
                    gaussian=gaussian[i].value,
                )
            )
    return lines, data


def answer_key_section(seed: int) -> tuple[list[str], dict]:
    m = simulate(seed=seed)
    t = m.truth
    j = t.real_signals[0]
    x = m.signals[j, :-1].ravel()
    y = (t.idio_return[1:] / t.idio_vol[1:]).ravel()
    measured_ic = float(np.corrcoef(x, y)[0, 1])
    theory = oracle_sharpe_theory(t.ic, m.config.stocks.n_assets)
    oracle = annualized_sharpe(oracle_returns(m))
    plain = annualized_sharpe(signal_returns(m.signals[j], m.returns))
    cross = check_cross_section(m.returns)
    planted = m.config.signals[0].ic
    lines = [
        f"## The answer key, default market, seed {seed}",
        "",
        "| | Value |",
        "|---|---:|",
        f"| Planted IC | {planted:.4f} |",
        f"| Measured IC (yesterday's signal vs today's vol-scaled residual, pooled) | {measured_ic:.4f} "
        f"(SE {1 / np.sqrt(len(x)):.4f}) |",
        f"| Oracle Sharpe, theory | {theory:.2f} |",
        f"| Oracle Sharpe, realized | {oracle:.2f} |",
        f"| Plain strategy on the real signal | {plain:.2f} |",
        f"| Real signal's position among the {len(m.signals)} | {j} |",
        f"| Pairwise correlation rise, turbulent minus calm | {cross.value:.2f} |",
    ]
    data = dict(
        seed=seed,
        planted_ic=planted,
        measured_ic=measured_ic,
        oracle_theory=theory,
        oracle_realized=oracle,
        plain_real=plain,
    )
    return lines, data


def decoy_section(n_seeds: int) -> tuple[list[str], dict]:
    """How often does the real signal have the best backtest of the twenty?"""
    first = {y: [] for y in YEARS}
    real_sr = {y: [] for y in YEARS}
    best_decoy_sr = {y: [] for y in YEARS}
    for s in range(n_seeds):
        m = simulate(seed=s)
        real = m.truth.real_signals[0]
        for y in YEARS:
            n = y * 252
            sr = np.array([annualized_sharpe(signal_returns(sig[:n], m.returns[:n])) for sig in m.signals])
            decoys = np.delete(sr, real)
            first[y].append(sr[real] > decoys.max())
            real_sr[y].append(sr[real])
            best_decoy_sr[y].append(decoys.max())
    m = simulate(seed=0)
    oracle = oracle_sharpe_theory(m.truth.ic, m.config.stocks.n_assets)
    lines = [
        f"## Can a backtest find the real signal? {n_seeds} markets, 1 real signal and 19 decoys each",
        "",
        "Each signal traded the plain way; the winner is the highest in-sample Sharpe ratio.",
        f"The oracle's Sharpe ratio on the real signal is {oracle:.2f}.",
        "",
        "| History | Real signal wins | Real signal, median Sharpe | Best decoy, median Sharpe |",
        "|---|---:|---:|---:|",
    ]
    data = {"n_seeds": n_seeds, "rows": []}
    for y in YEARS:
        lines.append(
            f"| {y} year{'s' if y > 1 else ''} | {np.mean(first[y]):.0%} | {np.median(real_sr[y]):.2f} "
            f"| {np.median(best_decoy_sr[y]):.2f} |"
        )
        data["rows"].append(
            dict(
                years=y,
                real_wins=float(np.mean(first[y])),
                real_median_sharpe=float(np.median(real_sr[y])),
                best_decoy_median_sharpe=float(np.median(best_decoy_sr[y])),
            )
        )
    lines += [
        "",
        "A decoy has no skill by construction, so every row where it wins is a backtest that would have",
        "been believed and was wrong.",
    ]
    return lines, data


def chart_data(real: np.ndarray | None, seed: int) -> dict:
    """The series behind the report, for drawing it."""
    m = simulate(seed=seed)
    t = m.truth
    n = len(real) if real is not None else 20 * 252
    sim = market_factor(n, seed)
    gaussian = np.random.default_rng(0).standard_normal(n) * sim.std()
    lags = range(1, 101)
    out = {
        "seed": seed,
        "market_log_level": np.cumsum(t.market_return).round(5).tolist(),
        "market_vol_annual": (t.market_vol * np.sqrt(252)).round(4).tolist(),
        "regimes": t.regimes.tolist(),
        "acf_abs": {
            "simulated": acf(np.abs(sim), lags).round(4).tolist(),
            "gaussian": acf(np.abs(gaussian), lags).round(4).tolist(),
        },
        "signal_pnl": [],
    }
    if real is not None:
        out["acf_abs"]["sp500"] = acf(np.abs(real), lags).round(4).tolist()
    for j, sig in enumerate(m.signals):
        out["signal_pnl"].append(
            {"real": j in t.real_signals, "cumulative": np.cumsum(signal_returns(sig, m.returns)).round(5).tolist()}
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sp500", help="daily price CSV to compare against")
    parser.add_argument("--seed", type=int, default=20261024, help="seed for the single-market sections")
    parser.add_argument("--fact-seeds", type=int, default=40)
    parser.add_argument("--decoy-seeds", type=int, default=100)
    parser.add_argument("--json", help="also write the numbers and chart series here")
    args = parser.parse_args()

    started = time.time()
    real = np.diff(np.log(load_prices(args.sp500))) if args.sp500 else None
    sections, payload = [], {}
    for key, (lines, data) in (
        ("facts", facts_section(real, args.fact_seeds)),
        ("answer_key", answer_key_section(args.seed)),
        ("decoys", decoy_section(args.decoy_seeds)),
    ):
        sections.append("\n".join(lines))
        payload[key] = data
    print("\n\n".join(sections))
    print(f"\n_{time.time() - started:.0f} seconds._")
    if args.json:
        payload["charts"] = chart_data(real, args.seed)
        payload["config"] = dataclasses.asdict(MarketConfig())
        with open(args.json, "w") as f:
            json.dump(payload, f, default=float)


if __name__ == "__main__":
    main()
