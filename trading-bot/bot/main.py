"""Boucle principale du bot.

Usage :
    python -m bot.main            # lance le bot (mode défini dans .env)
    python -m bot.main --once     # une seule itération (test de connexion)
    python -m bot.main --close    # vend toutes les positions et quitte
    python -m bot.main --status   # affiche le capital et l'historique des trades

Arrêt d'urgence : crée un fichier nommé STOP dans le dossier du bot.
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from .broker import LiveBroker, PaperBroker, make_exchange
from .config import load_config
from .strategy import add_indicators, min_candles

STATE_FILE = "state.json"
POLL_SECONDS = 60

log = logging.getLogger("bot")


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler("logs/bot.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, STATE_FILE)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Bot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = load_state()
        ex = make_exchange(cfg, authenticated=cfg.live)
        self.broker = LiveBroker(cfg, ex) if cfg.live else PaperBroker(cfg, ex, self.state)
        self._migrate()
        self.state.setdefault("positions", {})
        self.state.setdefault("last_candle", {})
        self.state.setdefault("trades", [])

    def _migrate(self):
        """Convertit l'ancien format (une seule crypto) vers le format multi-cryptos."""
        if "position" in self.state:
            old = self.state.pop("position")
            symbol = self.cfg.symbols[0]
            if old:
                self.state.setdefault("positions", {})[symbol] = old
                paper = self.state.get("paper")
                if paper is not None and not paper.get("base"):
                    paper["base"] = {self.broker.base(symbol): old["qty"]}
        if not isinstance(self.state.get("last_candle", {}), dict):
            self.state["last_candle"] = {}

    @property
    def positions(self) -> dict:
        return self.state["positions"]

    def equity(self, prices: dict | None = None) -> float:
        total = self.broker.quote_balance()
        for symbol, pos in self.positions.items():
            price = (prices or {}).get(symbol) or self.broker.price(symbol)
            total += pos["qty"] * price
        return total

    # ------------------------------------------------------------------
    def open_position(self, symbol: str):
        price = self.broker.price(symbol)
        share = self.cfg.position_pct / 100 / len(self.cfg.symbols)
        budget = min(self.equity({symbol: price}) * share, self.broker.quote_balance() * 0.99)
        qty = budget / price
        if not self.broker.tradable(symbol, qty, price):
            log.warning("%s : montant trop petit pour la plateforme (%.2f %s) — ajoute des fonds",
                        symbol, budget, self.broker.quote)
            return
        filled, avg = self.broker.buy(symbol, qty)
        self.positions[symbol] = {"qty": filled, "entry": avg, "opened_at": now()}
        log.info("ACHAT %s : %.8f à %.2f (≈ %.2f %s)", symbol, filled, avg, filled * avg, self.broker.quote)

    def close_position(self, symbol: str, reason: str):
        pos = self.positions.get(symbol)
        if not pos:
            return
        filled, avg = self.broker.sell(symbol, pos["qty"])
        pnl = (avg - pos["entry"]) * filled
        self.state["trades"].append({"symbol": symbol, **pos, "exit": avg, "pnl": round(pnl, 2),
                                     "reason": reason, "closed_at": now()})
        del self.positions[symbol]
        log.info("VENTE %s (%s) : %.8f à %.2f | résultat %+.2f %s",
                 symbol, reason, filled, avg, pnl, self.broker.quote)

    # ------------------------------------------------------------------
    def step_symbol(self, symbol: str):
        df = self.broker.candles(symbol)
        last_ts = str(df["ts"].iloc[-1])
        if self.state["last_candle"].get(symbol) == last_ts:
            return  # rien de nouveau : on attend la clôture de la prochaine bougie
        if len(df) < min_candles(self.cfg):
            log.warning("%s : historique insuffisant (%d/%d bougies) — réduis EMA_SLOW ou change TIMEFRAME",
                        symbol, len(df), min_candles(self.cfg))
            return
        row = add_indicators(df, self.cfg).iloc[-1]
        in_market = symbol in self.positions
        log.info("%s | bougie %s | prix %.2f | EMA %.2f / %.2f | tendance %s | %s",
                 symbol, last_ts[:16], row["close"], row["ema_fast"], row["ema_slow"],
                 "HAUSSIÈRE" if row["uptrend"] else "baissière",
                 "investi" if in_market else "en liquide")
        if row["uptrend"] and not in_market:
            self.open_position(symbol)
        elif not row["uptrend"] and in_market:
            self.close_position(symbol, "tendance baissière")
        # marqué comme traité seulement si tout a réussi (sinon nouvel essai)
        self.state["last_candle"][symbol] = last_ts
        return True

    def step(self):
        acted = False
        for symbol in self.cfg.symbols:
            acted |= bool(self.step_symbol(symbol))
        if acted:
            log.info("Capital total : %.2f %s", self.equity(), self.broker.quote)

    def run(self, once: bool = False):
        log.info("Démarrage — mode %s | %s | %s | bougies %s | %g %% du capital max investi",
                 self.cfg.mode.upper(), self.cfg.exchange, ", ".join(self.cfg.symbols),
                 self.cfg.timeframe, self.cfg.position_pct)
        while True:
            if os.path.exists("STOP"):
                log.warning("Fichier STOP détecté : arrêt du bot (les positions sont conservées)")
                break
            try:
                self.step()
                save_state(self.state)
            except Exception as e:  # réseau, API... on log et on réessaie
                log.error("Erreur : %s — nouvel essai dans %d s", e, POLL_SECONDS)
            if once:
                break
            time.sleep(POLL_SECONDS)

    def close_all(self):
        if not self.positions:
            log.info("Aucune position ouverte")
        for symbol in list(self.positions):
            self.close_position(symbol, "fermeture manuelle")

    def status(self):
        q = self.broker.quote
        prices = {s: self.broker.price(s) for s in self.cfg.symbols}
        print(f"Mode {self.cfg.mode} | " + " | ".join(f"{s} {p:.2f}" for s, p in prices.items()))
        print(f"Capital total : {self.equity(prices):.2f} {q} (dont {self.broker.quote_balance():.2f} {q} en liquide)")
        for symbol in self.cfg.symbols:
            pos = self.positions.get(symbol)
            if pos:
                pnl = (prices[symbol] - pos["entry"]) * pos["qty"]
                print(f"  {symbol} : {pos['qty']:.8f} achetés à {pos['entry']:.2f} ({pnl:+.2f} {q})")
            else:
                print(f"  {symbol} : en liquide")
        trades = self.state["trades"]
        print(f"Trades terminés : {len(trades)} | résultat cumulé {sum(t['pnl'] for t in trades):+.2f} {q}")
        for t in trades[-10:]:
            print(f"  {t['closed_at'][:16]}  {t.get('symbol', self.cfg.symbols[0]):8} "
                  f"{t['entry']:.2f} -> {t['exit']:.2f}  {t['pnl']:+.2f}")


def main():
    p = argparse.ArgumentParser(description="Bot de trading")
    p.add_argument("--once", action="store_true", help="une seule itération")
    p.add_argument("--close", action="store_true", help="vend toutes les positions et quitte")
    p.add_argument("--status", action="store_true", help="affiche le capital et les trades")
    args = p.parse_args()
    setup_logging()
    cfg = load_config()
    if cfg.live and not args.status:
        log.warning("MODE LIVE : des ordres RÉELS vont être passés sur %s", cfg.exchange)
    bot = Bot(cfg)
    if args.status:
        bot.status()
    elif args.close:
        bot.close_all()
        save_state(bot.state)
    else:
        bot.run(once=args.once)


if __name__ == "__main__":
    main()
