from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from typing import Dict

from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server

REGISTRY = CollectorRegistry()

API_REQUEST_DURATION = Histogram(
    "btc_arb_api_request_duration_seconds",
    "Duration of exchange API requests.",
    ["exchange", "operation"],
    registry=REGISTRY,
)
API_REQUEST_STATUS = Counter(
    "btc_arb_api_request_total",
    "Status of exchange API requests.",
    ["exchange", "operation", "status"],
    registry=REGISTRY,
)
NORMALIZATION_COUNT = Counter(
    "btc_arb_normalization_total",
    "Number of payloads normalized by stage.",
    ["stage", "status"],
    registry=REGISTRY,
)
SPREAD_ATTEMPTS = Counter(
    "btc_arb_spread_attempts_total",
    "Count of spread evaluations grouped by status.",
    ["status"],
    registry=REGISTRY,
)
SPREAD_OPPORTUNITIES = Counter(
    "btc_arb_spread_opportunities_total",
    "Positive spread opportunities by pair.",
    ["buy_exchange", "sell_exchange"],
    registry=REGISTRY,
)
ALERTS_SENT = Counter(
    "btc_arb_alerts_sent_total",
    "Alerts pushed to notification channels.",
    ["channel"],
    registry=REGISTRY,
)


def start_metrics_server(port: int = 8000) -> None:
    """Expose the collected metrics over HTTP for Prometheus scraping."""
    start_http_server(port, registry=REGISTRY)


@contextmanager
def track_api_request(exchange: str, operation: str):
    timer = API_REQUEST_DURATION.labels(exchange, operation).time()
    timer.__enter__()
    try:
        yield
        API_REQUEST_STATUS.labels(exchange, operation, "success").inc()
    except Exception:
        API_REQUEST_STATUS.labels(exchange, operation, "error").inc()
        raise
    finally:
        timer.__exit__(None, None, None)


def record_normalization(stage: str, status: str = "success") -> None:
    NORMALIZATION_COUNT.labels(stage, status).inc()


def record_spread_attempt(status: str) -> None:
    SPREAD_ATTEMPTS.labels(status).inc()


def record_spread_opportunity(buy_exchange: str, sell_exchange: str) -> None:
    SPREAD_OPPORTUNITIES.labels(buy_exchange, sell_exchange).inc()


def record_alert(channel: str) -> None:
    ALERTS_SENT.labels(channel).inc()
