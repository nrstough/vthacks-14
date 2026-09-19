"""The three demo accounts, ported verbatim from frontend/src/fixtures/scenarios.ts.

Kept byte-identical in content to the frontend's copy so the parity tests compare
this service against the reference solver on exactly the data a judge will see.
Each preset carries a cushion as well as a balance, because the tier depends on
both.
"""

from __future__ import annotations

from typing import Any

AS_OF = "2026-09-19"
HORIZON_END = "2026-10-02"
BUFFER = 2500

SCHEDULED: list[dict[str, Any]] = [
    {"id": "t_spotify", "date": "2026-09-20", "description": "SPOTIFY USA", "amount_cents": -1199, "kind": "bill", "recurring": True},
    {"id": "t_kroger_1", "date": "2026-09-21", "description": "KROGER #382", "amount_cents": -6418, "kind": "discretionary", "recurring": False},
    {"id": "t_dd_chipotle", "date": "2026-09-22", "description": "DOORDASH*CHIPOTLE", "amount_cents": -3180, "kind": "discretionary", "recurring": False},
    {"id": "t_gym", "date": "2026-09-22", "description": "PLANET FIT CLUB FEES", "amount_cents": -3499, "kind": "bill", "recurring": True},
    {"id": "t_shell", "date": "2026-09-23", "description": "SHELL OIL 57442891", "amount_cents": -4120, "kind": "discretionary", "recurring": False},
    {"id": "t_card", "date": "2026-09-24", "description": "CHASE CARD EPAY 8812", "amount_cents": -12844, "kind": "bill", "recurring": True},
    {"id": "t_starbucks", "date": "2026-09-24", "description": "STARBUCKS #0714", "amount_cents": -745, "kind": "discretionary", "recurring": False},
    {"id": "t_pay_1", "date": "2026-09-25", "description": "HARRIS TEETER PAYROLL", "amount_cents": 31240, "kind": "income", "recurring": True},
    {"id": "t_verizon", "date": "2026-09-26", "description": "VERIZON WIRELESS PMT", "amount_cents": -8500, "kind": "bill", "recurring": True},
    {"id": "t_amzn", "date": "2026-09-27", "description": "AMZN MKTP US*2K41Z", "amount_cents": -5230, "kind": "discretionary", "recurring": False},
    {"id": "t_kroger_2", "date": "2026-09-28", "description": "KROGER #382", "amount_cents": -7105, "kind": "discretionary", "recurring": False},
    {"id": "t_netflix", "date": "2026-09-29", "description": "NETFLIX.COM", "amount_cents": -2299, "kind": "bill", "recurring": True},
    {"id": "t_shell_2", "date": "2026-09-30", "description": "SHELL OIL 57442891", "amount_cents": -3860, "kind": "discretionary", "recurring": False},
    {"id": "t_dd_panera", "date": "2026-10-01", "description": "DOORDASH*PANERA", "amount_cents": -2840, "kind": "discretionary", "recurring": False},
    {"id": "t_pay_2", "date": "2026-10-02", "description": "HARRIS TEETER PAYROLL", "amount_cents": 29810, "kind": "income", "recurring": True},
]

CANDIDATES: list[dict[str, Any]] = [
    {"id": "c_card_min", "label": "Pay the card minimum", "detail": "CHASE CARD EPAY 8812, $128.44 statement", "action": "downgrade", "target_txn_id": "t_card", "freed_cents": 8000, "effective_date": "2026-09-24", "recharge_date": None, "lead_time_days": 0, "pain": 3},
    {"id": "c_dd_chipotle", "label": "Skip the DoorDash order", "detail": "DOORDASH*CHIPOTLE, $31.80", "action": "skip", "target_txn_id": "t_dd_chipotle", "freed_cents": 3180, "effective_date": "2026-09-22", "recharge_date": None, "lead_time_days": 0, "pain": 2},
    {"id": "c_gym", "label": "Cancel the gym membership", "detail": "PLANET FIT CLUB FEES, $34.99 monthly", "action": "cancel", "target_txn_id": "t_gym", "freed_cents": 3499, "effective_date": "2026-09-22", "recharge_date": None, "lead_time_days": 3, "pain": 1},
    {"id": "c_shell_defer", "label": "Put off the gas fill to the 26th", "detail": "SHELL OIL, $41.20 moved past payday", "action": "defer", "target_txn_id": "t_shell", "freed_cents": 4120, "effective_date": "2026-09-23", "recharge_date": "2026-09-26", "lead_time_days": 0, "pain": 3},
    {"id": "c_starbucks", "label": "Skip the coffee run", "detail": "STARBUCKS #0714, $7.45", "action": "skip", "target_txn_id": "t_starbucks", "freed_cents": 745, "effective_date": "2026-09-24", "recharge_date": None, "lead_time_days": 0, "pain": 1},
    {"id": "c_spotify", "label": "Drop Spotify to the free tier", "detail": "SPOTIFY USA, $11.99 monthly", "action": "downgrade", "target_txn_id": "t_spotify", "freed_cents": 1199, "effective_date": "2026-09-20", "recharge_date": None, "lead_time_days": 0, "pain": 2},
    {"id": "c_kroger_1", "label": "Trim the Sep 21 grocery run", "detail": "KROGER #382, $64.18 down to $39.18", "action": "downgrade", "target_txn_id": "t_kroger_1", "freed_cents": 2500, "effective_date": "2026-09-21", "recharge_date": None, "lead_time_days": 0, "pain": 3},
    {"id": "c_amzn", "label": "Cancel the Amazon order", "detail": "AMZN MKTP US, $52.30, ships the 27th", "action": "skip", "target_txn_id": "t_amzn", "freed_cents": 5230, "effective_date": "2026-09-27", "recharge_date": None, "lead_time_days": 1, "pain": 2},
    {"id": "c_kroger_2", "label": "Trim the Sep 28 grocery run", "detail": "KROGER #382, $71.05 down to $46.05", "action": "downgrade", "target_txn_id": "t_kroger_2", "freed_cents": 2500, "effective_date": "2026-09-28", "recharge_date": None, "lead_time_days": 0, "pain": 3},
    {"id": "c_netflix", "label": "Pause Netflix for a cycle", "detail": "NETFLIX.COM, $22.99 monthly", "action": "cancel", "target_txn_id": "t_netflix", "freed_cents": 2299, "effective_date": "2026-09-29", "recharge_date": None, "lead_time_days": 2, "pain": 1},
    {"id": "c_dd_panera", "label": "Skip the Oct 1 DoorDash order", "detail": "DOORDASH*PANERA, $28.40", "action": "skip", "target_txn_id": "t_dd_panera", "freed_cents": 2840, "effective_date": "2026-10-01", "recharge_date": None, "lead_time_days": 0, "pain": 2},
]


def request(opening_balance_cents: int, buffer_cents: int = BUFFER, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "as_of": AS_OF,
        "horizon_end": HORIZON_END,
        "opening_balance_cents": opening_balance_cents,
        "buffer_cents": buffer_cents,
        "scheduled": SCHEDULED,
        "candidates": CANDIDATES,
        "locks": {"in": [], "out": []},
        "previous_plan": [],
    }
    return {**base, **overrides}


# (opening, cushion) per the frontend's presets.
SCENARIOS: dict[str, dict[str, Any]] = {
    "clears": request(20000, 2500),
    "tight": request(18000, 10000),
    "gap": request(6000, 2500),
}
