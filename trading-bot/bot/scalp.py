"""Version SCALPING — SIMULATION UNIQUEMENT (aucun ordre réel possible).

Stratégie classique de scalping « retour à la moyenne » sur bougies d'1 minute :
- Achat quand le prix casse sous la bande de Bollinger basse ET que le RSI(7) est très bas
  (le prix a chuté trop vite, on parie sur un rebond).
- Vente au premier de ces événements : objectif +0,3 %, stop -0,3 %,
  retour à la moyenne, ou au bout de 30 minutes.

Usage :
    python -m bot.scalp --backtest      # teste sur les 3 derniers mois (bougies 1 min)
    python -m bot.scalp                 # simulation en direct avec les vrais prix Kraken
    python -m bot.scalp --status        # résultat de la simulation

Indépendant du vrai bot : capital fictif et suivi séparés (scalp_state.json, logs/scalp.log).
Réglages optionnels dans .env : SCALP_SYMBOL, SCALP_FEE_PCT, SCALP_START_BALANCE.
"""
import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from dotenv import load_dotenv

STATE_FILE = "scalp_state.json"
log = logging.getLogger("scalp")


@dataclass
class ScalpConfig:
    symbol: str = "BTC/EUR"
    exchange: str = "kraken"
    fee_pct: float = 0.4          # frais par ordre (Kraken petit compte, ordre au marché)
    start_balance: float = 1000.0
    bb_period: int = 20
    bb_k: float = 2.0
    rsi_period: int = 7
    rsi_max: float = 25.0
    take_profit_pct: float = 0.3
    stop_loss_pct: float = 0.3
    max_minutes: int = 30


def load_scalp_config() -> ScalpConfig:
    load_dotenv(".env")
    return ScalpConfig(
        symbol=os.getenv("SCALP_SYMBOL", "BTC/EUR").strip(),
        exchange=os.getenv("EXCHANGE", "kraken").strip().lower(),
        fee_pct=float(os.getenv("SCALP_FEE_PCT", 0.4)),
        start_balance=float(os.getenv("SCALP_START_BALANCE", 1000)),
    )


def indicators(df: pd.DataFrame, c: ScalpConfig) -> pd.DataFrame:
    df = df.copy()
    mid = df["close"].rolling(c.bb_period).mean()
    std = df["close"].rolling(c.bb_period).std()
    df["mid"], df["lower"] = mid, mid - c.bb_k * std
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / c.rsi_period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / c.rsi_period, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, 1e-12))
    df["entry"] = (df["close"] < df["lower"]) & (df["rsi"] < c.rsi_max)
    return df


# ----------------------------------------------------------------------------- backtest
def backtest(df: pd.DataFrame, c: ScalpConfig) -> dict:
    df = indicators(df, c).reset_index(drop=True)
    o, h, l, cl = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    mid, entry_sig = df["mid"].to_numpy(float), df["entry"].to_numpy(bool)
    fee = c.fee_pct / 100
    eq, trades, i, n = 1.0, [], c.bb_period, len(df)
    while i < n - 1:
        if not entry_sig[i]:
            i += 1
            continue
        ep = o[i + 1]  # achat à l'ouverture de la bougie suivante
        tp, sl = ep * (1 + c.take_profit_pct / 100), ep * (1 - c.stop_loss_pct / 100)
        j, xp = i + 1, None
        while j < n:
            if l[j] <= sl:                     # stop prioritaire (hypothèse prudente)
                xp = min(sl, o[j]); break
            if h[j] >= tp:
                xp = max(tp, o[j]); break
            if cl[j] >= mid[j] or j - i >= c.max_minutes:
                xp = cl[j]; break
            j += 1
        if xp is None:
            break
        r = xp / ep * (1 - fee) / (1 + fee)
        trades.append(r - 1)
        eq *= r
        i = j + 1
    t = np.array(trades) if trades else np.zeros(1)
    days = max((len(df) / 1440), 1e-9)
    return {
        "trades": len(trades),
        "trades_par_jour": round(len(trades) / days, 1),
        "trades_gagnants_pct": round(float((t > 0).mean() * 100), 1) if trades else 0.0,
        "gain_moyen_par_trade_avant_frais_pct": round(float(np.mean([(1 + x) * (1 + fee) / (1 - fee) - 1 for x in trades]) * 100), 3) if trades else 0.0,
        "frais_par_aller_retour_pct": round(2 * c.fee_pct, 2),
        "capital_final": round(c.start_balance * eq, 2),
        "gain_pct": round((eq - 1) * 100, 1),
    }


def run_backtest(months: int):
    from .backtest import download_history
    c = load_scalp_config()
    today = date.today()
    y, m = today.year, today.month - months
    while m < 1:
        y, m = y - 1, m + 12
    print(f"Chargement des bougies 1 minute {c.symbol} ({months} derniers mois complets)…")
    df = download_history(c.symbol, y, interval="1m", since_month=m)
    df = df.sort_values("ts").reset_index(drop=True)
    start, end = pd.to_datetime(df["ts"].iloc[[0, -1]], unit="ms")
    print(f"\nSCALPING {c.symbol} | {start:%Y-%m-%d} -> {end:%Y-%m-%d} | {len(df)} bougies 1 min")
    for label, fee in (("SANS frais (impossible en vrai)", 0.0),
                       ("frais 0,25 % (ordres limites, si exécutés)", 0.25),
                       (f"frais {c.fee_pct:g} % (Kraken, ordres au marché)", c.fee_pct)):
        c.fee_pct = fee
        print(f"\n  -- {label}")
        for k, v in backtest(df, c).items():
            print(f"     {k:38} {v}")


# ----------------------------------------------------------------------------- simulation en direct
def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ScalpSim:
    def __init__(self, c: ScalpConfig):
        import ccxt  # import ici : le backtest n'en a pas besoin
        self.c = c
        self.ex = getattr(ccxt, c.exchange)({"enableRateLimit": True})  # SANS clé API : aucun ordre possible
        self.state = {"cash": c.start_balance, "position": None, "trades": [], "last_candle": None}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, encoding="utf-8") as f:
                self.state.update(json.load(f))

    def save(self):
        with open(STATE_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
        os.replace(STATE_FILE + ".tmp", STATE_FILE)

    def price(self) -> float:
        return float(self.ex.fetch_ticker(self.c.symbol)["last"])

    def close(self, price: float, reason: str):
        pos, fee = self.state["position"], self.c.fee_pct / 100
        value = pos["qty"] * price * (1 - fee)
        pnl = value - pos["cost"]
        self.state["cash"] += value
        self.state["trades"].append({"entry": pos["entry"], "exit": price, "pnl": round(pnl, 4),
                                     "reason": reason, "closed_at": now()})
        self.state["position"] = None
        log.info("[SIMULATION] VENTE à %.2f (%s) | %+.2f EUR | capital %.2f EUR",
                 price, reason, pnl, self.state["cash"])

    def step(self):
        pos = self.state["position"]
        if pos:  # surveillance objectif / stop toutes les quelques secondes
            p = self.price()
            if p >= pos["tp"]:
                return self.close(p, "objectif")
            if p <= pos["sl"]:
                return self.close(p, "stop")
        raw = self.ex.fetch_ohlcv(self.c.symbol, "1m", limit=100)
        df = indicators(pd.DataFrame(raw[:-1], columns=["ts", "open", "high", "low", "close", "volume"]), self.c)
        last = df.iloc[-1]
        if self.state["last_candle"] == int(last["ts"]):
            return
        self.state["last_candle"] = int(last["ts"])
        if pos:
            minutes = (last["ts"] - pos["ts"]) / 60000
            if last["close"] >= last["mid"] or minutes >= self.c.max_minutes:
                self.close(self.price(), "moyenne" if last["close"] >= last["mid"] else "temps écoulé")
        elif last["entry"]:
            p, fee = self.price(), self.c.fee_pct / 100
            cash = self.state["cash"]
            qty = cash / (p * (1 + fee))
            self.state["cash"] = 0.0
            self.state["position"] = {"qty": qty, "entry": p, "cost": cash, "ts": int(last["ts"]),
                                      "tp": p * (1 + self.c.take_profit_pct / 100),
                                      "sl": p * (1 - self.c.stop_loss_pct / 100)}
            log.info("[SIMULATION] ACHAT à %.2f (RSI %.1f, sous la bande basse)", p, last["rsi"])

    def run(self):
        log.info("SCALPING EN SIMULATION — %s | frais simulés %g %% par ordre | capital fictif %.2f EUR",
                 self.c.symbol, self.c.fee_pct, self.state["cash"])
        while not os.path.exists("STOP"):
            try:
                self.step()
                self.save()
            except Exception as e:
                log.error("Erreur : %s — nouvel essai", e)
            time.sleep(5)

    def status(self):
        p = self.price()
        pos, t = self.state["position"], self.state["trades"]
        capital = self.state["cash"] + (pos["qty"] * p if pos else 0)
        print(f"SCALPING (simulation) {self.c.symbol} | prix {p:.2f}")
        print(f"Capital fictif : {capital:.2f} EUR (départ {self.c.start_balance:.2f}) "
              f"→ {(capital / self.c.start_balance - 1) * 100:+.2f} %")
        if t:
            wins = sum(x["pnl"] > 0 for x in t)
            print(f"Trades : {len(t)} | gagnants {wins} ({wins / len(t) * 100:.0f} %) | "
                  f"total {sum(x['pnl'] for x in t):+.2f} EUR")
        print("Position : " + (f"achetée à {pos['entry']:.2f}" if pos else "aucune"))


def main():
    p = argparse.ArgumentParser(description="Scalping — simulation uniquement")
    p.add_argument("--backtest", action="store_true")
    p.add_argument("--months", type=int, default=3)
    p.add_argument("--status", action="store_true")
    args = p.parse_args()
    if args.backtest:
        return run_backtest(args.months)
    os.makedirs("logs", exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler("logs/scalp.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    sim = ScalpSim(load_scalp_config())
    sim.status() if args.status else sim.run()


if __name__ == "__main__":
    main()
