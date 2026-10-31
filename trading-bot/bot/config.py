"""Chargement de la configuration depuis le fichier .env."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    mode: str = "paper"
    exchange: str = "kraken"
    api_key: str = ""
    api_secret: str = ""
    api_password: str = ""
    sandbox: bool = False
    symbols: tuple = ("BTC/EUR", "ETH/EUR")
    timeframe: str = "4h"
    ema_fast: int = 72
    ema_slow: int = 156
    position_pct: float = 50.0
    paper_start_balance: float = 1000.0

    @property
    def quote(self) -> str:
        return self.symbols[0].split("/")[1]

    @property
    def live(self) -> bool:
        return self.mode == "live"


def load_config(env_file: str = ".env") -> Config:
    load_dotenv(env_file)
    g = os.getenv
    cfg = Config(
        mode=g("MODE", "paper").strip().lower(),
        exchange=g("EXCHANGE", "kraken").strip().lower(),
        api_key=g("API_KEY", "").strip(),
        api_secret=g("API_SECRET", "").strip(),
        api_password=g("API_PASSWORD", "").strip(),
        sandbox=g("SANDBOX", "false").strip().lower() == "true",
        symbols=tuple(x.strip() for x in (g("SYMBOLS") or g("SYMBOL") or "BTC/EUR,ETH/EUR").split(",") if x.strip()),
        timeframe=g("TIMEFRAME", "4h").strip(),
        ema_fast=int(g("EMA_FAST", 72)),
        ema_slow=int(g("EMA_SLOW", 156)),
        position_pct=float(g("POSITION_PCT", 50)),
        paper_start_balance=float(g("PAPER_START_BALANCE", 1000)),
    )
    if cfg.mode not in ("paper", "live"):
        raise ValueError("MODE doit valoir 'paper' ou 'live'")
    if not cfg.symbols or len({x.split("/")[1] for x in cfg.symbols}) != 1:
        raise ValueError("SYMBOLS doit lister des paires de même devise, ex : BTC/EUR,ETH/EUR")
    if cfg.ema_fast >= cfg.ema_slow:
        raise ValueError("EMA_FAST doit être plus petit que EMA_SLOW")
    if not 0 < cfg.position_pct <= 100:
        raise ValueError("POSITION_PCT doit être entre 1 et 100")
    if cfg.live and not (cfg.api_key and cfg.api_secret):
        raise ValueError("MODE=live nécessite API_KEY et API_SECRET dans .env")
    return cfg
