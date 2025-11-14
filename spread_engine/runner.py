from __future__ import annotations

import json
import sys
from typing import Dict, Iterable, List, Optional, Tuple

from data_collector.clients import BitbankClient, BitflyerClient, CoincheckClient, ExchangeClient
from data_collector.normalizer import (
    NormalizedOrderBook,
    NormalizedTicker,
    normalize_order_book,
    normalize_ticker,
)
from spread_engine.calc import SpreadCalculator, SpreadOpportunity


def _fetch_and_normalize(
    client: ExchangeClient,
) -> Tuple[str, Optional[NormalizedTicker], Optional[NormalizedOrderBook]]:
    ticker = None
    order_book = None
    try:
        ticker = client.fetch_ticker()
        order_book = client.fetch_order_book()
    except Exception as exc:  # pragma: no cover - network operations
        print(f"{client.exchange_name} fetch error: {exc}", file=sys.stderr)

    normalized_ticker = normalize_ticker(ticker, client.exchange_name, client.product)
    normalized_order_book = normalize_order_book(order_book, client.exchange_name, client.product)
    return client.exchange_name, normalized_ticker, normalized_order_book


def main() -> None:
    clients: Iterable[ExchangeClient] = [
        BitflyerClient(),
        CoincheckClient(),
        BitbankClient(),
    ]
    snapshots: Dict[str, NormalizedTicker] = {}
    order_books: Dict[str, NormalizedOrderBook] = {}
    for client in clients:
        name, ticker, order_book = _fetch_and_normalize(client)
        if ticker:
            snapshots[name] = ticker
        if order_book:
            order_books[name] = order_book

    calculator = SpreadCalculator()
    opportunities: List[SpreadOpportunity] = []
    for buy_name, buy_ticker in snapshots.items():
        for sell_name, sell_ticker in snapshots.items():
            if buy_name == sell_name:
                continue
            buy_book = order_books.get(buy_name)
            sell_book = order_books.get(sell_name)
            if not buy_book or not sell_book:
                continue
            result = calculator.evaluate(buy_ticker, buy_book, sell_ticker, sell_book)
            if result:
                opportunities.append(result)

    opportunities.sort(key=lambda opp: opp.net_spread, reverse=True)
    print(">>>> Spread opportunities <<<<")
    for opp in opportunities:
        print(json.dumps(opp.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
