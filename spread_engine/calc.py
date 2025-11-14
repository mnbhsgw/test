from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

from data_collector.normalizer import NormalizedLevel, NormalizedOrderBook, NormalizedTicker
from observability.metrics import record_spread_attempt, record_spread_opportunity


@dataclass
class FeeProfile:
    taker_percent: float = 0.002
    withdrawal_fee: float = 0.0
    metadata: Dict[str, str] = field(default_factory=dict)


DEFAULT_FEE_PROFILE = FeeProfile()


DEFAULT_FEES: Dict[str, FeeProfile] = {
    "bitFlyer": FeeProfile(taker_percent=0.0003, withdrawal_fee=100.0, metadata={"notes": "bitFlyer taker fee"}),
    "Coincheck": FeeProfile(taker_percent=0.001, withdrawal_fee=250.0),
    "bitbank": FeeProfile(taker_percent=0.002, withdrawal_fee=120.0),
}


@dataclass
class SpreadOpportunity:
    buy_exchange: str
    sell_exchange: str
    product: str
    best_buy_price: float
    best_sell_price: float
    gross_spread: float
    net_spread: float
    available_volume: float
    metadata: Dict[str, float] = field(default_factory=dict)


class SpreadCalculator:
    def __init__(self, fees: Optional[Dict[str, FeeProfile]] = None) -> None:
        self.fees = fees or DEFAULT_FEES

    def _top_level(self, order_book: NormalizedOrderBook, side: str) -> Optional[NormalizedLevel]:
        levels = order_book.bids if side == "bid" else order_book.asks
        return levels[0] if levels else None

    def _fee_profile(self, exchange: str) -> FeeProfile:
        return self.fees.get(exchange, DEFAULT_FEE_PROFILE)

    def evaluate(
        self,
        buy_ticker: NormalizedTicker,
        buy_order_book: NormalizedOrderBook,
        sell_ticker: NormalizedTicker,
        sell_order_book: NormalizedOrderBook,
    ) -> Optional[SpreadOpportunity]:
        if buy_ticker.product != sell_ticker.product:
            record_spread_attempt("skip_product")
            return None

        buy_level = self._top_level(buy_order_book, "ask")
        sell_level = self._top_level(sell_order_book, "bid")
        if not buy_level or not sell_level:
            record_spread_attempt("skip_levels")
            return None

        buy_price = buy_level.price
        sell_price = sell_level.price
        volume = min(buy_level.size, sell_level.size)
        if volume <= 0 or sell_price <= buy_price:
            record_spread_attempt("skip_volume_price")
            return None

        buy_fee = self._fee_profile(buy_ticker.exchange)
        sell_fee = self._fee_profile(sell_ticker.exchange)

        gross = sell_price - buy_price
        buy_cost = buy_price * buy_fee.taker_percent
        sell_gain = sell_price * (1 - sell_fee.taker_percent)
        net = sell_gain - (buy_price + buy_cost) - buy_fee.withdrawal_fee - sell_fee.withdrawal_fee

        if net <= 0:
            record_spread_attempt("skip_no_profit")
            return None

        metadata = {
            "buy_fee_percent": buy_fee.taker_percent,
            "sell_fee_percent": sell_fee.taker_percent,
            "buy_withdrawal_fee": buy_fee.withdrawal_fee,
            "sell_withdrawal_fee": sell_fee.withdrawal_fee,
        }

        record_spread_attempt("positive")
        record_spread_opportunity(buy_ticker.exchange, sell_ticker.exchange)

        return SpreadOpportunity(
            buy_exchange=buy_ticker.exchange,
            sell_exchange=sell_ticker.exchange,
            product=buy_ticker.product,
            best_buy_price=buy_price,
            best_sell_price=sell_price,
            gross_spread=gross,
            net_spread=net,
            available_volume=volume,
            metadata=metadata,
        )
