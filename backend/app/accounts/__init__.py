"""Modelled accounts: the merchant table and the generation profiles over it.

`docs/features/accounts.md`. Nothing here is real bank data, and every account
this package produces is marked as modelled at the response boundary.
"""

from __future__ import annotations

from app.accounts.merchants import MERCHANTS
from app.accounts.profiles import window, windows

__all__ = ["MERCHANTS", "window", "windows"]
