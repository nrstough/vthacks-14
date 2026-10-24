"""A synthetic stock market with an answer key.

    from market_sim import simulate
    market = simulate(seed=1)
    market.returns            # (days, assets) what a strategy sees
    market.signals            # (signals, days, assets) real ones hidden among decoys
    market.truth.real_signals # which of them are real: the answer key
"""

from .config import (
    TRADING_DAYS,
    GarchConfig,
    MarketConfig,
    MarketFactorConfig,
    RegimeConfig,
    SectorConfig,
    SignalConfig,
    StockConfig,
)
from .simulate import STREAMS, AnswerKey, Market, simulate
from .strategy import annualized_sharpe, oracle_returns, oracle_sharpe_theory, signal_returns

__all__ = [
    "STREAMS",
    "TRADING_DAYS",
    "AnswerKey",
    "GarchConfig",
    "Market",
    "MarketConfig",
    "MarketFactorConfig",
    "RegimeConfig",
    "SectorConfig",
    "SignalConfig",
    "StockConfig",
    "annualized_sharpe",
    "oracle_returns",
    "oracle_sharpe_theory",
    "signal_returns",
    "simulate",
]
