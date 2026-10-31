"""Connexion à la plateforme de trading via CCXT (100+ plateformes supportées).

- LiveBroker  : passe de vrais ordres sur ton compte.
- PaperBroker : utilise les vrais prix du marché mais simule les ordres.
"""
import logging

import ccxt
import pandas as pd

log = logging.getLogger("bot")

PAPER_FEE = 0.004  # frais simulés par ordre au marché (Kraken, petit compte : 0,4 %)


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
    for symbol in cfg.symbols:
        if symbol not in ex.markets:
            raise ValueError(f"{symbol} n'existe pas sur {cfg.exchange}")
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
        self.quote = cfg.quote

    @staticmethod
    def base(symbol: str) -> str:
        return symbol.split("/")[0]

    def price(self, symbol: str) -> float:
        return float(self.ex.fetch_ticker(symbol)["last"])

    def candles(self, symbol: str, limit: int = 720) -> pd.DataFrame:
        return fetch_candles(self.ex, symbol, self.cfg.timeframe, limit)

    def tradable(self, symbol: str, qty: float, price: float) -> bool:
        limits = self.ex.market(symbol).get("limits", {}) or {}
        min_amount = (limits.get("amount") or {}).get("min") or 0
        min_cost = (limits.get("cost") or {}).get("min") or 0
        return qty > 0 and qty >= min_amount and qty * price >= min_cost


class PaperBroker(BaseBroker):
    def __init__(self, cfg, ex, state: dict):
        super().__init__(cfg, ex)
        self.state = state
        paper = state.setdefault("paper", {"quote": cfg.paper_start_balance, "base": {}})
        if not isinstance(paper.get("base"), dict):  # ancien format (une seule crypto)
            paper["base"] = {}

    def quote_balance(self) -> float:
        return self.state["paper"]["quote"]

    def buy(self, symbol: str, qty: float) -> tuple[float, float]:
        p, paper = self.price(symbol), self.state["paper"]
        qty = min(qty, paper["quote"] / (p * (1 + PAPER_FEE)))
        paper["quote"] -= qty * p * (1 + PAPER_FEE)
        b = self.base(symbol)
        paper["base"][b] = paper["base"].get(b, 0.0) + qty
        log.info("[PAPER] ACHAT %.8f %s @ %.2f", qty, b, p)
        return qty, p

    def sell(self, symbol: str, qty: float) -> tuple[float, float]:
        p, paper, b = self.price(symbol), self.state["paper"], self.base(symbol)
        qty = min(qty, paper["base"].get(b, 0.0))
        paper["base"][b] = paper["base"].get(b, 0.0) - qty
        paper["quote"] += qty * p * (1 - PAPER_FEE)
        log.info("[PAPER] VENTE %.8f %s @ %.2f", qty, b, p)
        return qty, p


class LiveBroker(BaseBroker):
    def quote_balance(self) -> float:
        return float(self.ex.fetch_balance()["free"].get(self.quote, 0) or 0)

    def base_balance(self, symbol: str) -> float:
        return float(self.ex.fetch_balance()["free"].get(self.base(symbol), 0) or 0)

    def _market(self, symbol: str, side: str, qty: float) -> tuple[float, float]:
        amount = float(self.ex.amount_to_precision(symbol, qty))
        order = self.ex.create_order(symbol, "market", side, amount)
        try:
            order = self.ex.fetch_order(order["id"], symbol)
        except Exception:  # certaines plateformes ne le supportent pas
            pass
        filled = float(order.get("filled") or amount)
        avg = float(order.get("average") or order.get("price") or self.price(symbol))
        log.info("[LIVE] %s %.8f %s @ %.2f (ordre %s)", side.upper(), filled, self.base(symbol), avg, order.get("id"))
        return filled, avg

    def buy(self, symbol: str, qty: float) -> tuple[float, float]:
        return self._market(symbol, "buy", qty)

    def sell(self, symbol: str, qty: float) -> tuple[float, float]:
        # On ne vend jamais plus que ce que le bot a acheté ni que le solde dispo
        return self._market(symbol, "sell", min(qty, self.base_balance(symbol)))
