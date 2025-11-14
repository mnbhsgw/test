from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from alert_router.router import AlertRouter, AlertRule, ConsoleChannel, OpportunityAlert
from alert_router.webhook import WebhookChannel
from config.manager import ConfigManager
from data_collector.clients import BitbankClient, BitflyerClient, CoincheckClient, ExchangeClient
from data_collector.normalizer import normalize_order_book, normalize_ticker
from data_collector.storage import FileStorageAdapter
from spread_engine.calc import DEFAULT_FEES, FeeProfile, SpreadCalculator, SpreadOpportunity


def _utcnow_iso() -> str:
    """Get current UTC time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


class MonitoringPipeline:
    """Continuous monitoring pipeline that collects data, calculates spreads, and sends alerts."""

    def __init__(
        self,
        interval_seconds: float = 5.0,
        alert_rule: Optional[AlertRule] = None,
        webhook_url: Optional[str] = None,
        webhook_headers: Optional[dict] = None,
        config_path: Optional[str] = None,
    ) -> None:
        """
        Initialize monitoring pipeline.
        
        Args:
            interval_seconds: Interval between data collection cycles
            alert_rule: Alert rule configuration (defaults to reasonable values or from config)
            webhook_url: Optional webhook URL for notifications
            webhook_headers: Optional headers for webhook requests
            config_path: Optional path to configuration file
        """
        self.interval_seconds = interval_seconds
        self.clients: List[ExchangeClient] = [
            BitflyerClient(),
            CoincheckClient(),
            BitbankClient(),
        ]
        self.storage = FileStorageAdapter("storage_snapshots")
        
        # Load configuration
        self.config_manager = ConfigManager(config_path or "config.json")
        config = self.config_manager.load()
        
        # Setup calculator with fee profiles from config
        fees = DEFAULT_FEES.copy()
        fees.update(config.fee_profiles)
        self.calculator = SpreadCalculator(fees=fees)
        
        # Setup alert router
        rule = alert_rule or config.alert_rule
        from alert_router.router import NotificationChannel
        channels: List[NotificationChannel] = [ConsoleChannel()]
        if webhook_url:
            channels.append(WebhookChannel(webhook_url, headers=webhook_headers))
        self.router = AlertRouter(rule=rule, channels=channels)
        
        self.running = False

    def _collect_data(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Collect and normalize data from all exchanges."""
        from data_collector.normalizer import NormalizedOrderBook, NormalizedTicker
        
        tickers: Dict[str, NormalizedTicker] = {}
        order_books: Dict[str, NormalizedOrderBook] = {}
        
        for client in self.clients:
            try:
                raw_ticker = client.fetch_ticker()
                raw_order_book = client.fetch_order_book()
                
                normalized_ticker = normalize_ticker(
                    raw_ticker, client.exchange_name, client.product
                )
                normalized_order_book = normalize_order_book(
                    raw_order_book, client.exchange_name, client.product
                )
                
                if normalized_ticker:
                    tickers[client.exchange_name] = normalized_ticker
                    self.storage.persist_snapshot(
                        exchange=client.exchange_name,
                        product=client.product,
                        kind="ticker",
                        payload={
                            "exchange": normalized_ticker.exchange,
                            "product": normalized_ticker.product,
                            "timestamp": normalized_ticker.timestamp,
                            "bid": normalized_ticker.bid,
                            "ask": normalized_ticker.ask,
                            "bid_size": normalized_ticker.bid_size,
                            "ask_size": normalized_ticker.ask_size,
                            "volume": normalized_ticker.volume,
                        },
                    )
                
                if normalized_order_book:
                    order_books[client.exchange_name] = normalized_order_book
                    self.storage.persist_snapshot(
                        exchange=client.exchange_name,
                        product=client.product,
                        kind="order_book",
                        payload={
                            "exchange": normalized_order_book.exchange,
                            "product": normalized_order_book.product,
                            "timestamp": normalized_order_book.timestamp,
                            "bids": [
                                {"price": level.price, "size": level.size}
                                for level in normalized_order_book.bids
                            ],
                            "asks": [
                                {"price": level.price, "size": level.size}
                                for level in normalized_order_book.asks
                            ],
                        },
                    )
            except Exception as exc:
                print(f"Error collecting data from {client.exchange_name}: {exc}")
        
        return tickers, order_books

    def _calculate_spreads(
        self, tickers: Dict[str, Any], order_books: Dict[str, Any]
    ) -> List[SpreadOpportunity]:
        """Calculate spread opportunities from collected data."""
        opportunities: List[SpreadOpportunity] = []
        
        for buy_name, buy_ticker in tickers.items():
            for sell_name, sell_ticker in tickers.items():
                if buy_name == sell_name:
                    continue
                
                buy_book = order_books.get(buy_name)
                sell_book = order_books.get(sell_name)
                
                if not buy_book or not sell_book:
                    continue
                
                result = self.calculator.evaluate(
                    buy_ticker, buy_book, sell_ticker, sell_book
                )
                
                if result:
                    opportunities.append(result)
        
        opportunities.sort(key=lambda opp: opp.net_spread, reverse=True)
        return opportunities

    def _save_opportunities(self, opportunities: List[SpreadOpportunity]) -> None:
        """Save spread opportunities to storage."""
        for opp in opportunities:
            payload = {
                "buy_exchange": opp.buy_exchange,
                "sell_exchange": opp.sell_exchange,
                "product": opp.product,
                "best_buy_price": opp.best_buy_price,
                "best_sell_price": opp.best_sell_price,
                "gross_spread": opp.gross_spread,
                "net_spread": opp.net_spread,
                "available_volume": opp.available_volume,
                "metadata": opp.metadata,
            }
            self.storage.persist_snapshot(
                exchange=f"{opp.buy_exchange}->{opp.sell_exchange}",
                product=opp.product,
                kind="spread_opportunity",
                payload=payload,
            )

    def _send_alerts(self, opportunities: List[SpreadOpportunity]) -> None:
        """Send alerts for opportunities that meet the criteria."""
        for opp in opportunities:
            alert = OpportunityAlert(
                buy_exchange=opp.buy_exchange,
                sell_exchange=opp.sell_exchange,
                product=opp.product,
                net_spread=opp.net_spread,
                gross_spread=opp.gross_spread,
                available_volume=opp.available_volume,
                recorded_at=_utcnow_iso(),
                metadata=opp.metadata,
            )
            self.router.handle(alert)

    def reload_config(self) -> None:
        """Reload configuration from file."""
        config = self.config_manager.reload()
        
        # Update calculator fees
        fees = DEFAULT_FEES.copy()
        fees.update(config.fee_profiles)
        self.calculator = SpreadCalculator(fees=fees)
        
        # Update alert router rule
        self.router.rule = config.alert_rule
    
    def run_cycle(self) -> None:
        """Run a single monitoring cycle."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting monitoring cycle...")
        
        # Reload config to pick up any changes
        self.reload_config()
        
        # Collect data
        tickers, order_books = self._collect_data()
        print(f"Collected data from {len(tickers)} exchanges")
        
        # Calculate spreads
        opportunities = self._calculate_spreads(tickers, order_books)
        print(f"Found {len(opportunities)} spread opportunities")
        
        # Save opportunities
        if opportunities:
            self._save_opportunities(opportunities)
        
        # Send alerts
        self._send_alerts(opportunities)
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Cycle complete")

    def run_continuous(self) -> None:
        """Run monitoring pipeline continuously."""
        self.running = True
        print(f"Starting continuous monitoring (interval: {self.interval_seconds}s)")
        
        try:
            while self.running:
                self.run_cycle()
                time.sleep(self.interval_seconds)
        except KeyboardInterrupt:
            print("\nStopping monitoring pipeline...")
            self.running = False

    def stop(self) -> None:
        """Stop the monitoring pipeline."""
        self.running = False


def main() -> None:
    """Main entry point for monitoring pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bitcoin arbitrage monitoring pipeline")
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Interval between monitoring cycles in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--min-net-spread",
        type=float,
        default=1000.0,
        help="Minimum net spread for alerts (default: 1000.0)",
    )
    parser.add_argument(
        "--min-volume",
        type=float,
        default=0.01,
        help="Minimum volume for alerts (default: 0.01)",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=180,
        help="Cooldown period between alerts in seconds (default: 180)",
    )
    parser.add_argument(
        "--webhook-url",
        type=str,
        help="Optional webhook URL for notifications",
    )
    
    args = parser.parse_args()
    
    rule = AlertRule(
        min_net_spread=args.min_net_spread,
        min_volume=args.min_volume,
        cooldown_seconds=args.cooldown,
    )
    
    pipeline = MonitoringPipeline(
        interval_seconds=args.interval,
        alert_rule=rule,
        webhook_url=args.webhook_url,
    )
    
    pipeline.run_continuous()


if __name__ == "__main__":
    main()

