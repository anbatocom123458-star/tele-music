"""Credit cost abstraction (spec §17).

Every handler calls calculate_*_cost() then users.try_charge(). No handler
hard-codes deduction logic, and clients can never push credit/usage values.
"""
from __future__ import annotations

from dataclasses import dataclass

# Pricing table (USD). Tune via ENV-free constants for now — single source of truth.
VOICE_COST_PER_1K_CHARS = 0.05  # $ per 1000 normalized characters
VOICE_MIN_COST = 0.02
SVG_BASE_COST = 0.10
SVG_PER_ELEMENT_COST = 0.0005


class InsufficientCredit(Exception):
    def __init__(self, balance: float, cost: float):
        self.balance = round(balance, 2)
        self.cost = round(cost, 4)
        super().__init__(f"Insufficient credit: balance={self.balance}, cost={self.cost}")


@dataclass(frozen=True)
class VoiceCost:
    chars: int
    amount: float


@dataclass(frozen=True)
class SvgCost:
    amount: float


def round_cost(value: float) -> float:
    return round(float(value), 4)


def calculate_voice_cost(text: str) -> VoiceCost:
    """Cost scales with normalized character count; minimum floor applies."""
    chars = len(text)
    if chars <= 0:
        return VoiceCost(chars=0, amount=0.0)
    raw = (chars / 1000.0) * VOICE_COST_PER_1K_CHARS
    return VoiceCost(chars=chars, amount=round_cost(max(VOICE_MIN_COST, raw)))


def calculate_svg_cost(element_count: int = 0) -> SvgCost:
    raw = SVG_BASE_COST + max(0, int(element_count)) * SVG_PER_ELEMENT_COST
    return SvgCost(amount=round_cost(raw))


def format_usd(amount: float) -> str:
    return f"${amount:,.2f}"


def format_cost(amount: float) -> str:
    return f"${amount:.4f}".rstrip("0").rstrip(".") if amount < 1 else f"${amount:.2f}"
