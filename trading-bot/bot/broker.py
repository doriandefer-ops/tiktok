"""Connexion à la plateforme de trading via CCXT (100+ plateformes supportées).

- LiveBroker  : passe de vrais ordres sur ton compte.
- PaperBroker : utilise les vrais prix du marché mais simule les ordres.
"""
import logging

import ccxt
import pandas as pd

log = logging.getLogger("bot")

PAPER_FEE = 0.001  # 0,1 % de frais simulés par ordre


def make_exchange(cfg, authenticated: bool) -> ccxt.Exchange:
    if not hasattr(ccxt, cfg.exchange):
        raise ValueError(f"Plateforme inconnue pour CCXT : {cfg.exchange}")
    params = {"enableRateLimit": True}
    if authenticated:
        params.update(apiKey=cfg.api_key, secret=cfg.api_secret)
        if cfg.api_password:
            params["password"] = cfg.api_password
    ex = getattr(ccxt, cfg.exchange)(params)
    if cfg.sandbox:
        ex.set_sandbox_mode(True)
    ex.load_markets()
    if cfg.symbol not in ex.markets:
        raise ValueError(f"{cfg.symbol} n'existe pas sur {cfg.exchange}")
    return ex


def fetch_candles(ex: ccxt.Exchange, symbol: str, timeframe: str, limit: int = 720) -> pd.DataFrame:
    """Bougies OHLCV ; la dernière bougie (pas encore clôturée) est retirée."""
    raw = ex.fetch_ohlcv(symbol, timeframe, limit=limit + 1)
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.iloc[:-1].reset_index(drop=True)


class BaseBroker:
    def __init__(self, cfg, ex: ccxt.Exchange):
        self.cfg = cfg
        self.ex = ex
        market = ex.market(cfg.symbol)
        self.base, self.quote = market["base"], market["quote"]
        self.min_amount = (market.get("limits", {}).get("amount", {}) or {}).get("min") or 0
        self.min_cost = (market.get("limits", {}).get("cost", {}) or {}).get("min") or 0

    def price(self) -> float:
        return float(self.ex.fetch_ticker(self.cfg.symbol)["last"])

    def candles(self, limit: int = 720) -> pd.DataFrame:
        return fetch_candles(self.ex, self.cfg.symbol, self.cfg.timeframe, limit)

    def tradable(self, qty: float, price: float) -> bool:
        return qty > 0 and qty >= self.min_amount and qty * price >= self.min_cost


class PaperBroker(BaseBroker):
    def __init__(self, cfg, ex, state: dict):
        super().__init__(cfg, ex)
        self.state = state
        state.setdefault("paper", {"quote": cfg.paper_start_balance, "base": 0.0})

    def quote_balance(self) -> float:
        return self.state["paper"]["quote"]

    def buy(self, qty: float) -> tuple[float, float]:
        p = self.price()
        cost = qty * p * (1 + PAPER_FEE)
        if cost > self.state["paper"]["quote"]:
            qty = self.state["paper"]["quote"] / (p * (1 + PAPER_FEE))
            cost = self.state["paper"]["quote"]
        self.state["paper"]["quote"] -= cost
        self.state["paper"]["base"] += qty
        log.info("[PAPER] ACHAT %.8f %s @ %.4f", qty, self.base, p)
        return qty, p

    def sell(self, qty: float) -> tuple[float, float]:
        p = self.price()
        qty = min(qty, self.state["paper"]["base"])
        self.state["paper"]["base"] -= qty
        self.state["paper"]["quote"] += qty * p * (1 - PAPER_FEE)
        log.info("[PAPER] VENTE %.8f %s @ %.4f", qty, self.base, p)
        return qty, p


class LiveBroker(BaseBroker):
    def quote_balance(self) -> float:
        return float(self.ex.fetch_balance()["free"].get(self.quote, 0) or 0)

    def base_balance(self) -> float:
        return float(self.ex.fetch_balance()["free"].get(self.base, 0) or 0)

    def _market(self, side: str, qty: float) -> tuple[float, float]:
        amount = float(self.ex.amount_to_precision(self.cfg.symbol, qty))
        order = self.ex.create_order(self.cfg.symbol, "market", side, amount)
        try:
            order = self.ex.fetch_order(order["id"], self.cfg.symbol)
        except Exception:  # certaines plateformes ne le supportent pas
            pass
        filled = float(order.get("filled") or amount)
        avg = float(order.get("average") or order.get("price") or self.price())
        log.info("[LIVE] %s %.8f %s @ %.4f (ordre %s)", side.upper(), filled, self.base, avg, order.get("id"))
        return filled, avg

    def buy(self, qty: float) -> tuple[float, float]:
        return self._market("buy", qty)

    def sell(self, qty: float) -> tuple[float, float]:
        # On ne vend jamais plus que ce que le bot a acheté ni que le solde dispo
        return self._market("sell", min(qty, self.base_balance()))
