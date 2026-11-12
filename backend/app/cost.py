"""Cost calculation. PURE CODE, exact Decimal arithmetic."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

PER_TOKENS = Decimal(1_000_000)


class UnknownModelPrice(KeyError):
    pass


def call_cost(model: str, input_tokens: int, output_tokens: int,
              prices: Mapping[str, tuple[Decimal, Decimal]]) -> Decimal:
    if model not in prices:
        raise UnknownModelPrice(f"No price configured for model {model!r}")
    in_price, out_price = prices[model]
    return (Decimal(input_tokens) * in_price + Decimal(output_tokens) * out_price) / PER_TOKENS


def total_cost(step_costs: Iterable[Decimal | str]) -> Decimal:
    return sum((Decimal(c) for c in step_costs), Decimal("0"))
