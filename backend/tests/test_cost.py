"""Cost is calculated in code from tokens x configured prices."""
from decimal import Decimal

import pytest

from app.cost import UnknownModelPrice, call_cost, total_cost

PRICES = {"m": (Decimal("10"), Decimal("50"))}


def test_call_cost_exact():
    # 1,000 in * $10/1M + 200 out * $50/1M = 0.01 + 0.01
    assert call_cost("m", 1000, 200, PRICES) == Decimal("0.02")
    assert call_cost("m", 1, 1, PRICES) == Decimal("0.00006")
    assert call_cost("m", 0, 0, PRICES) == 0


def test_unknown_model_raises():
    with pytest.raises(UnknownModelPrice):
        call_cost("nope", 1, 1, PRICES)


def test_total_is_sum_of_steps():
    assert total_cost(["0.01", "0.02", Decimal("0.00006")]) == Decimal("0.03006")
