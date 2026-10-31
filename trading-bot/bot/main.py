"""Boucle principale du bot.

Usage :
    python -m bot.main            # lance le bot (mode défini dans .env)
    python -m bot.main --once     # une seule itération (test)
    python -m bot.main --close    # ferme la position ouverte et quitte

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
from .risk import daily_loss_exceeded, position_size, stop_and_target
from .strategy import add_indicators, row_signal

STATE_FILE = "state.json"
POLL_SECONDS = 30

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


class Bot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = load_state()
        ex = make_exchange(cfg, authenticated=cfg.live)
        self.broker = LiveBroker(cfg, ex) if cfg.live else PaperBroker(cfg, ex, self.state)
        self.state.setdefault("position", None)
        self.state.setdefault("trades", [])

    # ------------------------------------------------------------------
    def equity(self, price: float) -> float:
        pos = self.state["position"]
        return self.broker.quote_balance() + (pos["qty"] * price if pos else 0.0)

    def _roll_day(self, equity: float):
        today = datetime.now(timezone.utc).date().isoformat()
        if self.state.get("day") != today:
            self.state["day"] = today
            self.state["day_start_equity"] = equity

    # ------------------------------------------------------------------
    def open_position(self, row):
        price = self.broker.price()
        stop, target = stop_and_target(price, float(row["atr"]), self.cfg)
        equity = self.equity(price)
        qty = position_size(equity, price, stop, self.cfg)
        qty = min(qty, self.broker.quote_balance() * 0.995 / price)
        if not self.broker.tradable(qty, price):
            log.warning("Taille de position trop petite (%.8f) — capital insuffisant ?", qty)
            return
        filled, avg = self.broker.buy(qty)
        stop, target = stop_and_target(avg, float(row["atr"]), self.cfg)
        self.state["position"] = {
            "qty": filled, "entry": avg, "stop": stop, "target": target,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }
        log.info("Position ouverte : entrée %.4f | stop %.4f | objectif %.4f", avg, stop, target)

    def close_position(self, reason: str):
        pos = self.state["position"]
        if not pos:
            return
        filled, avg = self.broker.sell(pos["qty"])
        pnl = (avg - pos["entry"]) * filled
        self.state["trades"].append({**pos, "exit": avg, "pnl": pnl, "reason": reason,
                                     "closed_at": datetime.now(timezone.utc).isoformat()})
        self.state["position"] = None
        log.info("Position fermée (%s) : sortie %.4f | P&L %+.2f %s", reason, avg, pnl, self.broker.quote)

    # ------------------------------------------------------------------
    def step(self):
        price = self.broker.price()
        equity = self.equity(price)
        self._roll_day(equity)
        pos = self.state["position"]

        # 1) Surveillance stop-loss / take-profit à chaque passage
        if pos:
            if price <= pos["stop"]:
                self.close_position("stop-loss")
            elif price >= pos["target"]:
                self.close_position("take-profit")

        # 2) Signal de stratégie, une seule fois par bougie clôturée
        df = self.broker.candles()
        last_ts = str(df["ts"].iloc[-1])
        if self.state.get("last_candle") == last_ts:
            return
        self.state["last_candle"] = last_ts
        row = add_indicators(df, self.cfg).iloc[-1]
        sig = row_signal(row, self.cfg)
        log.info("Bougie %s | close %.4f | EMA %.4f/%.4f | RSI %.1f | signal %s | capital %.2f %s",
                 last_ts, row["close"], row["ema_fast"], row["ema_slow"], row["rsi"], sig,
                 equity, self.broker.quote)

        if sig == "sell" and self.state["position"]:
            self.close_position("croisement baissier")
        elif sig == "buy" and not self.state["position"]:
            if daily_loss_exceeded(self.state["day_start_equity"], equity, self.cfg):
                log.warning("Perte journalière max atteinte : pas de nouveau trade aujourd'hui")
            else:
                self.open_position(row)

    def run(self, once: bool = False):
        log.info("Démarrage — mode %s | %s | %s | %s",
                 self.cfg.mode.upper(), self.cfg.exchange, self.cfg.symbol, self.cfg.timeframe)
        while True:
            if os.path.exists("STOP"):
                log.warning("Fichier STOP détecté : arrêt du bot (position conservée)")
                break
            try:
                self.step()
                save_state(self.state)
            except Exception as e:  # réseau, API... on log et on réessaie
                log.exception("Erreur : %s", e)
            if once:
                break
            time.sleep(POLL_SECONDS)


def main():
    p = argparse.ArgumentParser(description="Bot de trading")
    p.add_argument("--once", action="store_true", help="une seule itération")
    p.add_argument("--close", action="store_true", help="ferme la position et quitte")
    args = p.parse_args()
    setup_logging()
    cfg = load_config()
    if cfg.live:
        log.warning("MODE LIVE : des ordres RÉELS vont être passés sur %s", cfg.exchange)
    bot = Bot(cfg)
    if args.close:
        bot.close_position("fermeture manuelle")
        save_state(bot.state)
        return
    bot.run(once=args.once)


if __name__ == "__main__":
    main()
