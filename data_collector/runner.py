from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Iterable

from .clients import BitbankClient, BitflyerClient, CoincheckClient, ExchangeClient
from .normalizer import normalize_order_book, normalize_ticker
from .storage import FileStorageAdapter


def log_fetch(client: ExchangeClient, storage: FileStorageAdapter) -> None:
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

    normalized_ticker = normalize_ticker(ticker, client.exchange_name, client.product)
    normalized_order_book = normalize_order_book(order_book, client.exchange_name, client.product)

    print(f"{client.exchange_name} normalized:")
    normalized_payload = {
        "ticker": asdict(normalized_ticker) if normalized_ticker else None,
        "order_book": asdict(normalized_order_book) if normalized_order_book else None,
    }
    print(json.dumps(normalized_payload, indent=2, ensure_ascii=False))
    if normalized_ticker:
        storage.persist_snapshot(
            exchange=client.exchange_name,
            product=client.product,
            kind="ticker",
            payload=asdict(normalized_ticker),
        )
    if normalized_order_book:
        storage.persist_snapshot(
            exchange=client.exchange_name,
            product=client.product,
            kind="order_book",
            payload=asdict(normalized_order_book),
        )


def main() -> None:
    clients: Iterable[ExchangeClient] = [
        BitflyerClient(),
        CoincheckClient(),
        BitbankClient(),
    ]
    storage = FileStorageAdapter("storage_snapshots")

    for client in clients:
        log_fetch(client, storage)


if __name__ == "__main__":
    main()
