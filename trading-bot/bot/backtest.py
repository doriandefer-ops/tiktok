"""Backtest : teste la stratégie sur l'historique AVANT de risquer de l'argent.

Usage :
    python -m bot.backtest                 # télécharge ~1000 bougies via la plateforme
    python -m bot.backtest --candles 3000
    python -m bot.backtest --csv data.csv  # colonnes : ts,open,high,low,close,volume
"""
import argparse

import pandas as pd

from .config import load_config
from .risk import position_size, stop_and_target
from .strategy import add_indicators

FEE = 0.001


def run_backtest(df: pd.DataFrame, cfg, start_balance: float = 1000.0) -> dict:
    df = add_indicators(df, cfg).reset_index(drop=True)
    warmup = max(cfg.ema_slow, cfg.rsi_period, cfg.atr_period) * 3
    cash, pos, trades, curve = start_balance, None, [], []

    for i in range(warmup, len(df)):
        r = df.iloc[i]
        if pos:  # stop / objectif touché pendant la bougie (stop prioritaire, prudent)
            exit_price = reason = None
            if r["low"] <= pos["stop"]:
                exit_price, reason = min(pos["stop"], r["open"]), "stop"
            elif r["high"] >= pos["target"]:
                exit_price, reason = max(pos["target"], r["open"]), "target"
            elif r["cross_down"]:
                exit_price, reason = r["close"], "cross"
            if exit_price is not None:
                cash += pos["qty"] * exit_price * (1 - FEE)
                trades.append((exit_price - pos["entry"]) * pos["qty"] - pos["qty"] * (exit_price + pos["entry"]) * FEE)
                pos = None
        elif r["cross_up"] and r["close"] > r["ema_slow"] and r["rsi"] < cfg.rsi_max_entry:
            entry = r["close"]
            stop, target = stop_and_target(entry, r["atr"], cfg)
            qty = min(position_size(cash, entry, stop, cfg), cash / (entry * (1 + FEE)))
            if qty > 0:
                cash -= qty * entry * (1 + FEE)
                pos = {"qty": qty, "entry": entry, "stop": stop, "target": target}
        curve.append(cash + (pos["qty"] * r["close"] if pos else 0))

    equity = pd.Series(curve) if curve else pd.Series([start_balance])
    drawdown = ((equity - equity.cummax()) / equity.cummax()).min() * 100
    wins = [t for t in trades if t > 0]
    first, last = df["close"].iloc[warmup] if len(df) > warmup else 0, df["close"].iloc[-1]
    return {
        "final_equity": round(float(equity.iloc[-1]), 2),
        "return_pct": round((equity.iloc[-1] / start_balance - 1) * 100, 2),
        "buy_and_hold_pct": round((last / first - 1) * 100, 2) if first else 0.0,
        "trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
        "max_drawdown_pct": round(float(drawdown), 2),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv")
    p.add_argument("--candles", type=int, default=1000)
    args = p.parse_args()
    cfg = load_config()
    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        from .broker import make_exchange
        ex = make_exchange(cfg, authenticated=False)
        tf_ms = ex.parse_timeframe(cfg.timeframe) * 1000
        since = ex.milliseconds() - args.candles * tf_ms
        rows = []
        while since < ex.milliseconds() - tf_ms:
            batch = ex.fetch_ohlcv(cfg.symbol, cfg.timeframe, since=since, limit=1000)
            if not batch:
                break
            rows += batch
            since = batch[-1][0] + tf_ms
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]).drop_duplicates("ts")
    print(f"{cfg.symbol} {cfg.timeframe} — {len(df)} bougies")
    for k, v in run_backtest(df, cfg, cfg.paper_start_balance).items():
        print(f"  {k:18} {v}")


if __name__ == "__main__":
    main()
