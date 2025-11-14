from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _timestamp_to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            numeric = float(value)
        except ValueError:
            return value
        else:
            value = numeric
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.utcfromtimestamp(ts).isoformat() + "Z"
    return None


def _normalize_levels(
    entries: Iterable[Any], limit: int
) -> List["NormalizedLevel"]:
    normalized: List[NormalizedLevel] = []
    for idx, entry in enumerate(entries):
        if idx >= limit:
            break
        price = None
        size = None
        if isinstance(entry, dict):
            price = _safe_float(entry.get("price"))
            size = _safe_float(entry.get("size"))
        elif isinstance(entry, Sequence) and len(entry) >= 2:
            price = _safe_float(entry[0])
            size = _safe_float(entry[1])
        else:
            continue
        if price is None or size is None:
            continue
        normalized.append(NormalizedLevel(price=price, size=size))
    return normalized


@dataclass
class NormalizedLevel:
    price: float
    size: float


@dataclass
class NormalizedTicker:
    exchange: str
    product: str
    timestamp: Optional[str]
    bid: Optional[float]
    ask: Optional[float]
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    volume: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedOrderBook:
    exchange: str
    product: str
    timestamp: Optional[str]
    bids: List[NormalizedLevel] = field(default_factory=list)
    asks: List[NormalizedLevel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_ticker(
    raw: Optional[Dict[str, Any]], exchange: str, product: str
) -> Optional[NormalizedTicker]:
    if raw is None:
        return None
    allowed = {"exchange", "timestamp", "bid", "ask", "bid_size", "ask_size", "volume"}
    metadata = {
        key: value for key, value in raw.items() if key not in allowed
    }
    return NormalizedTicker(
        exchange=exchange,
        product=product,
        timestamp=_timestamp_to_iso(raw.get("timestamp")),
        bid=_safe_float(raw.get("bid")),
        ask=_safe_float(raw.get("ask")),
        bid_size=_safe_float(raw.get("bid_size")),
        ask_size=_safe_float(raw.get("ask_size")),
        volume=_safe_float(raw.get("volume")),
        metadata=metadata,
    )


def normalize_order_book(
    raw: Optional[Dict[str, Any]], exchange: str, product: str, limit: int = 5
) -> Optional[NormalizedOrderBook]:
    if raw is None:
        return None
    metadata = {k: v for k, v in raw.items() if k not in {"exchange", "timestamp", "bids", "asks"}}

    return NormalizedOrderBook(
        exchange=exchange,
        product=product,
        timestamp=_timestamp_to_iso(raw.get("timestamp")),
        bids=_normalize_levels(raw.get("bids", []), limit),
        asks=_normalize_levels(raw.get("asks", []), limit),
        metadata=metadata,
    )
