"""Runtime settings. Model id and prices are configuration, not code."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal

# USD per 1M tokens: (input, output). Verify against https://openai.com/api/pricing before use.
DEFAULT_PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-6.1-terra": (Decimal("1.00"), Decimal("5.00")),
    "gpt-6-astra": (Decimal("10.00"), Decimal("50.00")),
    # The fake client spends no money; tokens are still counted and shown.
    "fake-model": (Decimal("0"), Decimal("0")),
}


@dataclass
class Settings:
    db_path: str = "data/mission_control.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-6.1-terra"
    fd_token: str = "flight-director"
    prices: dict[str, tuple[Decimal, Decimal]] = field(default_factory=lambda: dict(DEFAULT_PRICES))

    @property
    def demo_mode(self) -> bool:
        return not self.openai_api_key

    @classmethod
    def from_env(cls) -> "Settings":
        s = cls(
            db_path=os.getenv("DB_PATH", cls.db_path),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", cls.openai_model),
            fd_token=os.getenv("FD_TOKEN", cls.fd_token),
        )
        in_price, out_price = os.getenv("MODEL_PRICE_INPUT"), os.getenv("MODEL_PRICE_OUTPUT")
        if in_price and out_price:
            s.prices[s.openai_model] = (Decimal(in_price), Decimal(out_price))
        return s
