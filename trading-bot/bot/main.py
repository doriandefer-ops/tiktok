"""Boucle principale du bot.

Usage :
    python -m bot.main            # lance le bot (mode défini dans .env)
    python -m bot.main --once     # une seule itération (test de connexion)
    python -m bot.main --close    # vend la position ouverte et quitte
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
        self.state.setdefault("position", None)
        self.state.setdefault("trades", [])

    def equity(self, price: float) -> float:
        pos = self.state["position"]
        return self.broker.quote_balance() + (pos["qty"] * price if pos else 0.0)

    # ------------------------------------------------------------------
    def open_position(self):
        price = self.broker.price()
        equity = self.equity(price)
        budget = min(equity * self.cfg.position_pct / 100, self.broker.quote_balance() * 0.99)
        qty = budget / price
        if not self.broker.tradable(qty, price):
            log.warning("Montant trop petit pour la plateforme (%.2f %s) — ajoute des fonds",
                        budget, self.broker.quote)
            return
        filled, avg = self.broker.buy(qty)
        self.state["position"] = {"qty": filled, "entry": avg, "opened_at": now()}
        log.info("ACHAT : %.8f %s à %.2f (≈ %.2f %s)", filled, self.broker.base, avg,
                 filled * avg, self.broker.quote)

    def close_position(self, reason: str):
        pos = self.state["position"]
        if not pos:
            log.info("Aucune position ouverte")
            return
        filled, avg = self.broker.sell(pos["qty"])
        pnl = (avg - pos["entry"]) * filled
        self.state["trades"].append({**pos, "exit": avg, "pnl": round(pnl, 2),
                                     "reason": reason, "closed_at": now()})
        self.state["position"] = None
        log.info("VENTE (%s) : %.8f %s à %.2f | résultat %+.2f %s",
                 reason, filled, self.broker.base, avg, pnl, self.broker.quote)

    # ------------------------------------------------------------------
    def step(self):
        df = self.broker.candles()
        last_ts = str(df["ts"].iloc[-1])
        if self.state.get("last_candle") == last_ts:
            return  # rien de nouveau : on attend la clôture de la prochaine bougie
        if len(df) < min_candles(self.cfg):
            log.warning("Historique insuffisant (%d/%d bougies) — réduis EMA_SLOW ou change TIMEFRAME",
                        len(df), min_candles(self.cfg))
            return
        row = add_indicators(df, self.cfg).iloc[-1]
        in_market = self.state["position"] is not None
        price = float(row["close"])
        log.info("Bougie %s | prix %.2f | EMA %.2f / %.2f | tendance %s | %s | capital %.2f %s",
                 last_ts, price, row["ema_fast"], row["ema_slow"],
                 "HAUSSIÈRE" if row["uptrend"] else "baissière",
                 "investi" if in_market else "en liquide",
                 self.equity(price), self.broker.quote)
        if row["uptrend"] and not in_market:
            self.open_position()
        elif not row["uptrend"] and in_market:
            self.close_position("tendance baissière")
        # marqué comme traité seulement si tout a réussi (sinon nouvel essai)
        self.state["last_candle"] = last_ts

    def run(self, once: bool = False):
        log.info("Démarrage — mode %s | %s | %s | bougies %s | %g %% du capital investi en tendance haussière",
                 self.cfg.mode.upper(), self.cfg.exchange, self.cfg.symbol,
                 self.cfg.timeframe, self.cfg.position_pct)
        while True:
            if os.path.exists("STOP"):
                log.warning("Fichier STOP détecté : arrêt du bot (la position éventuelle est conservée)")
                break
            try:
                self.step()
                save_state(self.state)
            except Exception as e:  # réseau, API... on log et on réessaie
                log.error("Erreur : %s — nouvel essai dans %d s", e, POLL_SECONDS)
            if once:
                break
            time.sleep(POLL_SECONDS)

    def status(self):
        price = self.broker.price()
        pos = self.state["position"]
        print(f"Mode {self.cfg.mode} | prix {self.cfg.symbol} : {price:.2f}")
        print(f"Capital : {self.equity(price):.2f} {self.broker.quote}")
        if pos:
            pnl = (price - pos["entry"]) * pos["qty"]
            print(f"Position : {pos['qty']:.8f} achetés à {pos['entry']:.2f} ({pnl:+.2f} {self.broker.quote})")
        else:
            print("Position : aucune (en liquide)")
        trades = self.state["trades"]
        total = sum(t["pnl"] for t in trades)
        print(f"Trades terminés : {len(trades)} | résultat cumulé {total:+.2f} {self.broker.quote}")
        for t in trades[-10:]:
            print(f"  {t['closed_at'][:16]}  {t['entry']:.2f} -> {t['exit']:.2f}  {t['pnl']:+.2f}")


def main():
    p = argparse.ArgumentParser(description="Bot de trading")
    p.add_argument("--once", action="store_true", help="une seule itération")
    p.add_argument("--close", action="store_true", help="vend la position et quitte")
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
        bot.close_position("fermeture manuelle")
        save_state(bot.state)
    else:
        bot.run(once=args.once)


if __name__ == "__main__":
    main()
