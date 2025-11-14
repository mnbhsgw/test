import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Sequence, Tuple


JSONType = Dict[str, Any]


class ExchangeClient:
    """Base helper for fetching JSON from public exchange endpoints."""

    exchange_name = "generic"
    user_agent = "btc-arb-monitor/0.1"

    def fetch_json(self, url: str, timeout: int = 10) -> JSONType:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{self.exchange_name} HTTP error: {exc}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self.exchange_name} network error: {exc}") from exc

    @staticmethod
    def _format_iso(timestamp: float) -> str:
        return datetime.utcfromtimestamp(timestamp).isoformat() + "Z"

    @staticmethod
    def _normalize_entries(entries: Sequence[Sequence[float]], limit: int) -> List[Dict[str, float]]:
        normalized: List[Dict[str, float]] = []
        for price, size in entries[:limit]:
            normalized.append({"price": price, "size": size})
        return normalized


class BitflyerClient(ExchangeClient):
    exchange_name = "bitFlyer"
    product = "BTC_JPY"

    def fetch_ticker(self) -> JSONType:
        url = f"https://api.bitflyer.com/v1/ticker?product_code={self.product}"
        data = self.fetch_json(url)
        return {
            "exchange": self.exchange_name,
            "timestamp": data.get("timestamp"),
            "bid": data.get("best_bid"),
            "ask": data.get("best_ask"),
            "bid_size": data.get("best_bid_size"),
            "ask_size": data.get("best_ask_size"),
        }

    def fetch_order_book(self, limit: int = 5) -> JSONType:
        url = f"https://api.bitflyer.com/v1/board?product_code={self.product}"
        data = self.fetch_json(url)
        return {
            "exchange": self.exchange_name,
            "timestamp": data.get("timestamp"),
            "bids": self._normalize_entries(
                [(entry["price"], entry["size"]) for entry in data.get("bids", [])], limit
            ),
            "asks": self._normalize_entries(
                [(entry["price"], entry["size"]) for entry in data.get("asks", [])], limit
            ),
        }


class CoincheckClient(ExchangeClient):
    exchange_name = "Coincheck"
    ticker_url = "https://coincheck.com/api/ticker"
    orderbook_url = "https://coincheck.com/api/order_books"

    def fetch_ticker(self) -> JSONType:
        data = self.fetch_json(self.ticker_url)
        timestamp = data.get("timestamp")
        iso_ts = self._format_iso(float(timestamp)) if timestamp else None
        return {
            "exchange": self.exchange_name,
            "timestamp": iso_ts,
            "bid": data.get("bid"),
            "ask": data.get("ask"),
            "volume": data.get("volume"),
        }

    def fetch_order_book(self, limit: int = 5) -> JSONType:
        data = self.fetch_json(self.orderbook_url)
        timestamp = data.get("timestamp")
        iso_ts = self._format_iso(float(timestamp)) if timestamp else None
        bids = [(float(price), float(amount)) for price, amount in data.get("bids", [])]
        asks = [(float(price), float(amount)) for price, amount in data.get("asks", [])]
        return {
            "exchange": self.exchange_name,
            "timestamp": iso_ts,
            "bids": self._normalize_entries(bids, limit),
            "asks": self._normalize_entries(asks, limit),
        }


class BitbankClient(ExchangeClient):
    exchange_name = "bitbank"
    base_url = "https://public.bitbank.cc/btc_jpy"

    def fetch_ticker(self) -> JSONType:
        data = self.fetch_json(f"{self.base_url}/ticker")
        payload = data.get("data", {})
        timestamp = payload.get("timestamp")
        iso_ts = (
            self._format_iso(float(timestamp) / 1000.0) if timestamp else None
        )
        return {
            "exchange": self.exchange_name,
            "timestamp": iso_ts,
            "bid": float(payload.get("buy")) if payload.get("buy") else None,
            "ask": float(payload.get("sell")) if payload.get("sell") else None,
        }

    def fetch_order_book(self, limit: int = 5) -> JSONType:
        data = self.fetch_json(f"{self.base_url}/depth")
        payload = data.get("data", {})
        timestamp = payload.get("timestamp")
        iso_ts = (
            self._format_iso(float(timestamp) / 1000.0) if timestamp else None
        )
        bids = [(float(entry[0]), float(entry[1])) for entry in payload.get("bids", [])]
        asks = [(float(entry[0]), float(entry[1])) for entry in payload.get("asks", [])]
        return {
            "exchange": self.exchange_name,
            "timestamp": iso_ts,
            "bids": self._normalize_entries(bids, limit),
            "asks": self._normalize_entries(asks, limit),
        }
