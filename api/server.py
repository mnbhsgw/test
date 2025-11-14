from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from alert_router.router import OpportunityAlert
from config.manager import ConfigManager
from spread_engine.calc import SpreadOpportunity


app = FastAPI(
    title="Bitcoin Arbitrage Monitor API",
    description="API for monitoring arbitrage opportunities across exchanges",
    version="0.1.0",
)

# Initialize config manager
config_manager = ConfigManager()


class SpreadOpportunityResponse(BaseModel):
    buy_exchange: str
    sell_exchange: str
    product: str
    best_buy_price: float
    best_sell_price: float
    gross_spread: float
    net_spread: float
    available_volume: float
    metadata: dict


class AlertResponse(BaseModel):
    buy_exchange: str
    sell_exchange: str
    product: str
    net_spread: float
    gross_spread: float
    available_volume: float
    recorded_at: str
    metadata: dict


def load_spread_opportunities(path: Path) -> List[SpreadOpportunityResponse]:
    """Load spread opportunities from JSONL file."""
    opportunities: List[SpreadOpportunityResponse] = []
    if not path.exists():
        return opportunities
    
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            payload = entry.get("payload", {})
            try:
                opp = SpreadOpportunityResponse(
                    buy_exchange=payload["buy_exchange"],
                    sell_exchange=payload["sell_exchange"],
                    product=payload["product"],
                    best_buy_price=float(payload["best_buy_price"]),
                    best_sell_price=float(payload["best_sell_price"]),
                    gross_spread=float(payload["gross_spread"]),
                    net_spread=float(payload["net_spread"]),
                    available_volume=float(payload["available_volume"]),
                    metadata=payload.get("metadata", {}),
                )
                opportunities.append(opp)
            except (KeyError, ValueError, TypeError):
                continue
    
    return opportunities


def load_alerts(path: Path) -> List[AlertResponse]:
    """Load alerts from JSONL file."""
    alerts: List[AlertResponse] = []
    if not path.exists():
        return alerts
    
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            payload = entry.get("payload", {})
            try:
                alert = AlertResponse(
                    buy_exchange=payload["buy_exchange"],
                    sell_exchange=payload["sell_exchange"],
                    product=payload["product"],
                    net_spread=float(payload["net_spread"]),
                    gross_spread=float(payload.get("gross_spread", 0)),
                    available_volume=float(payload.get("available_volume", 0)),
                    recorded_at=entry.get("recorded_at", ""),
                    metadata=payload.get("metadata", {}),
                )
                alerts.append(alert)
            except (KeyError, ValueError, TypeError):
                continue
    
    return alerts


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Bitcoin Arbitrage Monitor API",
        "version": "0.1.0",
        "endpoints": {
            "opportunities": "/api/v1/opportunities",
            "alerts": "/api/v1/alerts",
            "config": "/api/v1/config",
            "health": "/health",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/v1/opportunities", response_model=List[SpreadOpportunityResponse])
async def get_opportunities(
    min_net_spread: Optional[float] = None,
    min_volume: Optional[float] = None,
    buy_exchange: Optional[str] = None,
    sell_exchange: Optional[str] = None,
):
    """
    Get spread opportunities.
    
    - **min_net_spread**: Filter by minimum net spread
    - **min_volume**: Filter by minimum available volume
    - **buy_exchange**: Filter by buy exchange name
    - **sell_exchange**: Filter by sell exchange name
    """
    path = Path("storage_snapshots/snapshot-spread_opportunity.jsonl")
    opportunities = load_spread_opportunities(path)
    
    # Apply filters
    filtered = opportunities
    if min_net_spread is not None:
        filtered = [opp for opp in filtered if opp.net_spread >= min_net_spread]
    if min_volume is not None:
        filtered = [opp for opp in filtered if opp.available_volume >= min_volume]
    if buy_exchange:
        filtered = [opp for opp in filtered if opp.buy_exchange == buy_exchange]
    if sell_exchange:
        filtered = [opp for opp in filtered if opp.sell_exchange == sell_exchange]
    
    # Sort by net spread descending
    filtered.sort(key=lambda opp: opp.net_spread, reverse=True)
    
    return filtered


@app.get("/api/v1/alerts", response_model=List[AlertResponse])
async def get_alerts(
    min_net_spread: Optional[float] = None,
    buy_exchange: Optional[str] = None,
    sell_exchange: Optional[str] = None,
    limit: int = 100,
):
    """
    Get alert history.
    
    - **min_net_spread**: Filter by minimum net spread
    - **buy_exchange**: Filter by buy exchange name
    - **sell_exchange**: Filter by sell exchange name
    - **limit**: Maximum number of alerts to return
    """
    path = Path("storage_snapshots/snapshot-spread_opportunity.jsonl")
    alerts = load_alerts(path)
    
    # Apply filters
    filtered = alerts
    if min_net_spread is not None:
        filtered = [alert for alert in filtered if alert.net_spread >= min_net_spread]
    if buy_exchange:
        filtered = [alert for alert in filtered if alert.buy_exchange == buy_exchange]
    if sell_exchange:
        filtered = [alert for alert in filtered if alert.sell_exchange == sell_exchange]
    
    # Sort by recorded_at descending (most recent first)
    filtered.sort(key=lambda alert: alert.recorded_at, reverse=True)
    
    return filtered[:limit]


class AlertRuleUpdate(BaseModel):
    min_net_spread: Optional[float] = None
    min_volume: Optional[float] = None
    cooldown_seconds: Optional[int] = None


class FeeProfileUpdate(BaseModel):
    taker_percent: Optional[float] = None
    withdrawal_fee: Optional[float] = None
    metadata: Optional[Dict[str, str]] = None


@app.get("/api/v1/config")
async def get_config():
    """Get current configuration."""
    config = config_manager.get_config()
    return config.to_dict()


@app.put("/api/v1/config/alert-rule")
async def update_alert_rule(update: AlertRuleUpdate):
    """Update alert rule configuration."""
    try:
        config = config_manager.update_alert_rule(
            min_net_spread=update.min_net_spread,
            min_volume=update.min_volume,
            cooldown_seconds=update.cooldown_seconds,
        )
        return config.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/v1/config/fee-profile/{exchange}")
async def update_fee_profile(exchange: str, update: FeeProfileUpdate):
    """Update fee profile for an exchange."""
    try:
        config = config_manager.update_fee_profile(
            exchange=exchange,
            taker_percent=update.taker_percent,
            withdrawal_fee=update.withdrawal_fee,
            metadata=update.metadata,
        )
        return config.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

