from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from alert_router.router import NotificationChannel, OpportunityAlert
from observability.metrics import record_alert


class WebhookChannel(NotificationChannel):
    """Webhook notification channel that sends alerts via HTTP POST."""

    def __init__(
        self,
        url: str,
        timeout: int = 10,
        headers: Optional[dict] = None,
    ) -> None:
        """
        Initialize webhook channel.
        
        Args:
            url: Webhook URL to POST alerts to
            timeout: Request timeout in seconds
            headers: Optional custom headers (Content-Type will be set to application/json)
        """
        self.url = url
        self.timeout = timeout
        self.headers = headers or {}
        self.headers.setdefault("Content-Type", "application/json")

    def send(self, alert: OpportunityAlert) -> None:
        """Send alert to webhook URL via HTTP POST."""
        payload = {
            "event_type": "arbitrage_opportunity",
            "buy_exchange": alert.buy_exchange,
            "sell_exchange": alert.sell_exchange,
            "product": alert.product,
            "net_spread": alert.net_spread,
            "gross_spread": alert.gross_spread,
            "available_volume": alert.available_volume,
            "recorded_at": alert.recorded_at,
            "metadata": alert.metadata,
        }
        
        json_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=json_data,
            headers=self.headers,
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.getcode()
                if 200 <= status < 300:
                    record_alert("WebhookChannel")
                else:
                    raise RuntimeError(f"Webhook returned status {status}")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Webhook HTTP error: {exc}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Webhook network error: {exc}") from exc

