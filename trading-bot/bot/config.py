"""Chargement de la configuration depuis le fichier .env."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass
class Config:
    mode: str
    exchange: str
    api_key: str
    api_secret: str
    api_password: str
    sandbox: bool
    symbol: str
    timeframe: str
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_max_entry: float
    atr_period: int
    stop_atr_mult: float
    take_profit_atr_mult: float
    risk_per_trade_pct: float
    max_position_pct: float
    max_daily_loss_pct: float
    paper_start_balance: float

    @property
    def live(self) -> bool:
        return self.mode == "live"


def load_config(env_file: str = ".env") -> Config:
    load_dotenv(env_file)
    cfg = Config(
        mode=os.getenv("MODE", "paper").strip().lower(),
        exchange=os.getenv("EXCHANGE", "binance").strip().lower(),
        api_key=os.getenv("API_KEY", ""),
        api_secret=os.getenv("API_SECRET", ""),
        api_password=os.getenv("API_PASSWORD", ""),
        sandbox=os.getenv("SANDBOX", "false").lower() == "true",
        symbol=os.getenv("SYMBOL", "BTC/USDT"),
        timeframe=os.getenv("TIMEFRAME", "1h"),
        ema_fast=_i("EMA_FAST", 12),
        ema_slow=_i("EMA_SLOW", 26),
        rsi_period=_i("RSI_PERIOD", 14),
        rsi_max_entry=_f("RSI_MAX_ENTRY", 70),
        atr_period=_i("ATR_PERIOD", 14),
        stop_atr_mult=_f("STOP_ATR_MULT", 2.0),
        take_profit_atr_mult=_f("TAKE_PROFIT_ATR_MULT", 3.0),
        risk_per_trade_pct=_f("RISK_PER_TRADE_PCT", 1.0),
        max_position_pct=_f("MAX_POSITION_PCT", 25),
        max_daily_loss_pct=_f("MAX_DAILY_LOSS_PCT", 3.0),
        paper_start_balance=_f("PAPER_START_BALANCE", 1000),
    )
    if cfg.mode not in ("paper", "live"):
        raise ValueError("MODE doit valoir 'paper' ou 'live'")
    if cfg.ema_fast >= cfg.ema_slow:
        raise ValueError("EMA_FAST doit être plus petit que EMA_SLOW")
    if cfg.live and not (cfg.api_key and cfg.api_secret):
        raise ValueError("MODE=live nécessite API_KEY et API_SECRET dans .env")
    return cfg
