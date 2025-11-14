from __future__ import annotations

import json
import sys
from typing import Iterable

from .clients import BitbankClient, BitflyerClient, CoincheckClient, ExchangeClient


def log_fetch(client: ExchangeClient) -> None:
    """Fetch ticker and order book data from a client and print JSON."""

    def fetch_or_none(func_name: str):
        func = getattr(client, func_name)
        try:
            return func()
        except Exception as exc:
            print(f"{client.exchange_name} {func_name} error: {exc}", file=sys.stderr)
            return None

    ticker = fetch_or_none("fetch_ticker")
    order_book = fetch_or_none("fetch_order_book")

    payload = {"ticker": ticker, "order_book": order_book}
    print(f"{client.exchange_name} snapshot:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    clients: Iterable[ExchangeClient] = [
        BitflyerClient(),
        CoincheckClient(),
        BitbankClient(),
    ]

    for client in clients:
        log_fetch(client)


if __name__ == "__main__":
    main()
