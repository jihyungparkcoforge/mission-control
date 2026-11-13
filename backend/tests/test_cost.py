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


def test_large_token_counts_stay_exact():
    # 12,345,678 in * $10/1M + 3,210,987 out * $50/1M = 123.45678 + 160.54935
    assert call_cost("m", 12_345_678, 3_210_987, PRICES) == Decimal("284.00613")


def test_smallest_unit_is_not_rounded_away():
    assert call_cost("t", 1, 0, {"t": (Decimal("1.00"), Decimal("5.00"))}) == Decimal("0.000001")


def test_configured_prices_are_what_the_settings_use():
    from app.config import DEFAULT_PRICES, Settings
    s = Settings()
    assert s.prices["gpt-6.1-terra"] == DEFAULT_PRICES["gpt-6.1-terra"] == (Decimal("1.00"), Decimal("5.00"))
    # 1,000 in + 1,000 out at Terra prices = $0.001 + $0.005
    assert call_cost(s.openai_model, 1000, 1000, s.prices) == Decimal("0.006")
