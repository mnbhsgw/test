from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional

from alert_router.router import AlertRule
from spread_engine.calc import FeeProfile


@dataclass
class AppConfig:
    """Application configuration including alert rules and fee profiles."""
    
    alert_rule: AlertRule = field(default_factory=lambda: AlertRule(
        min_net_spread=1000.0,
        min_volume=0.01,
        cooldown_seconds=180,
    ))
    fee_profiles: Dict[str, FeeProfile] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "alert_rule": {
                "min_net_spread": self.alert_rule.min_net_spread,
                "min_volume": self.alert_rule.min_volume,
                "cooldown_seconds": self.alert_rule.cooldown_seconds,
            },
            "fee_profiles": {
                exchange: {
                    "taker_percent": profile.taker_percent,
                    "withdrawal_fee": profile.withdrawal_fee,
                    "metadata": profile.metadata,
                }
                for exchange, profile in self.fee_profiles.items()
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        """Create config from dictionary."""
        alert_rule_data = data.get("alert_rule", {})
        alert_rule = AlertRule(
            min_net_spread=alert_rule_data.get("min_net_spread", 1000.0),
            min_volume=alert_rule_data.get("min_volume", 0.01),
            cooldown_seconds=alert_rule_data.get("cooldown_seconds", 180),
        )
        
        fee_profiles = {}
        for exchange, profile_data in data.get("fee_profiles", {}).items():
            fee_profiles[exchange] = FeeProfile(
                taker_percent=profile_data.get("taker_percent", 0.002),
                withdrawal_fee=profile_data.get("withdrawal_fee", 0.0),
                metadata=profile_data.get("metadata", {}),
            )
        
        return cls(alert_rule=alert_rule, fee_profiles=fee_profiles)


class ConfigManager:
    """Manages application configuration with file-based persistence."""
    
    def __init__(self, config_path: Path | str = "config.json") -> None:
        """
        Initialize config manager.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self._config: Optional[AppConfig] = None
    
    def load(self) -> AppConfig:
        """Load configuration from file."""
        if self._config is not None:
            return self._config
        
        if not self.config_path.exists():
            # Return default config if file doesn't exist
            self._config = AppConfig()
            return self._config
        
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._config = AppConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise RuntimeError(f"Failed to load config from {self.config_path}: {exc}") from exc
        
        return self._config
    
    def save(self, config: Optional[AppConfig] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Config to save (uses cached config if not provided)
        """
        if config is not None:
            self._config = config
        
        if self._config is None:
            self._config = AppConfig()
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
    
    def update_alert_rule(
        self,
        min_net_spread: Optional[float] = None,
        min_volume: Optional[float] = None,
        cooldown_seconds: Optional[int] = None,
    ) -> AppConfig:
        """
        Update alert rule configuration.
        
        Args:
            min_net_spread: Minimum net spread threshold
            min_volume: Minimum volume threshold
            cooldown_seconds: Cooldown period in seconds
        
        Returns:
            Updated configuration
        """
        config = self.load()
        
        if min_net_spread is not None:
            config.alert_rule.min_net_spread = min_net_spread
        if min_volume is not None:
            config.alert_rule.min_volume = min_volume
        if cooldown_seconds is not None:
            config.alert_rule.cooldown_seconds = cooldown_seconds
        
        self.save(config)
        return config
    
    def update_fee_profile(
        self,
        exchange: str,
        taker_percent: Optional[float] = None,
        withdrawal_fee: Optional[float] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> AppConfig:
        """
        Update fee profile for an exchange.
        
        Args:
            exchange: Exchange name
            taker_percent: Taker fee percentage
            withdrawal_fee: Withdrawal fee amount
            metadata: Optional metadata
        
        Returns:
            Updated configuration
        """
        config = self.load()
        
        if exchange not in config.fee_profiles:
            config.fee_profiles[exchange] = FeeProfile()
        
        profile = config.fee_profiles[exchange]
        if taker_percent is not None:
            profile.taker_percent = taker_percent
        if withdrawal_fee is not None:
            profile.withdrawal_fee = withdrawal_fee
        if metadata is not None:
            profile.metadata.update(metadata)
        
        self.save(config)
        return config
    
    def get_config(self) -> AppConfig:
        """Get current configuration."""
        return self.load()
    
    def reload(self) -> AppConfig:
        """Reload configuration from file."""
        self._config = None
        return self.load()

