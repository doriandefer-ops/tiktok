"""Backtest : teste la stratégie sur l'historique AVANT de risquer de l'argent.

Usage :
    python -m bot.backtest                  # ~5 ans d'historique (archives publiques Binance)
    python -m bot.backtest --since 2023     # depuis 2023
    python -m bot.backtest --exchange       # historique récent via ta plateforme (Kraken : 720 bougies max)
    python -m bot.backtest --csv data.csv   # colonnes : ts,open,high,low,close,volume

Les données téléchargées sont gardées dans le dossier data/ (téléchargées une seule fois).
"""
import argparse
import io
import os
import urllib.error
import urllib.request
import zipfile
from datetime import date

import pandas as pd

from .config import load_config
from .strategy import add_indicators, min_candles

COST = 0.0015  # 0,1 % de frais + 0,05 % de glissement par ordre (prudent)
ARCHIVE = "https://data.binance.vision/data/spot/monthly/klines/{s}/1h/{s}-1h-{y}-{m:02d}.zip"


def download_history(symbol: str, since: int) -> pd.DataFrame:
    """Bougies 1h depuis les archives publiques de Binance (mises en cache dans data/)."""
    pair = symbol.replace("/", "").upper()
    os.makedirs("data", exist_ok=True)
    frames, today = [], date.today()
    for y in range(since, today.year + 1):
        for m in range(1, 13):
            if (y, m) >= (today.year, today.month):
                break
            path = f"data/{pair}-1h-{y}-{m:02d}.csv"
            if not os.path.exists(path):
                try:
                    with urllib.request.urlopen(ARCHIVE.format(s=pair, y=y, m=m), timeout=30) as r:
                        z = zipfile.ZipFile(io.BytesIO(r.read()))
                        raw = z.read(z.namelist()[0])
                except urllib.error.HTTPError:
                    continue  # mois indisponible (paire pas encore cotée)
                with open(path, "wb") as f:
                    f.write(raw)
                print(f"  téléchargé {y}-{m:02d}")
            frames.append(pd.read_csv(path, header=None, usecols=range(6)))
    if not frames:
        raise SystemExit(f"Aucun historique trouvé pour {pair} — essaie --exchange")
    df = pd.concat(frames)
    df.columns = ["ts", "open", "high", "low", "close", "volume"]
    df = df[pd.to_numeric(df["ts"], errors="coerce").notna()].astype(float)
    df["ts"] = df["ts"].where(df["ts"] < 1e14, df["ts"] / 1000)  # µs -> ms (archives récentes)
    return df


def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    rule = timeframe.replace("m", "min").replace("d", "D").replace("w", "W")
    df = df.copy()
    df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
    out = df.resample(rule).agg({"open": "first", "high": "max", "low": "min",
                                 "close": "last", "volume": "sum"}).dropna()
    out["ts"] = out.index
    return out.reset_index(drop=True)


def run_backtest(df: pd.DataFrame, cfg, start_balance: float = 1000.0) -> dict:
    """Décision à la clôture d'une bougie, exécution à l'ouverture de la suivante."""
    df = add_indicators(df, cfg).reset_index(drop=True)
    warmup = min_candles(cfg)
    if len(df) <= warmup + 1:
        raise SystemExit(f"Pas assez de bougies ({len(df)}) : il en faut plus de {warmup}")
    cash, qty, entry, trades, curve = start_balance, 0.0, 0.0, [], []
    for i in range(warmup + 1, len(df)):
        want_in, px = bool(df["uptrend"].iloc[i - 1]), float(df["open"].iloc[i])
        if want_in and qty == 0:
            spend = (cash + qty * px) * cfg.position_pct / 100
            qty, entry = spend * (1 - COST) / px, px
            cash -= spend
        elif not want_in and qty > 0:
            cash += qty * px * (1 - COST)
            trades.append(px * (1 - COST) ** 2 / entry - 1)
            qty = 0.0
        curve.append(cash + qty * float(df["close"].iloc[i]))
    eq = pd.Series(curve)
    first, last = float(df["open"].iloc[warmup + 1]), float(df["close"].iloc[-1])
    bh = df["close"].iloc[warmup + 1:]
    return {
        "periode": f"{str(df['ts'].iloc[warmup + 1])[:10]} -> {str(df['ts'].iloc[-1])[:10]}",
        "capital_final": round(float(eq.iloc[-1]), 2),
        "gain_bot_pct": round(float(eq.iloc[-1] / start_balance - 1) * 100, 1),
        "gain_achat_simple_pct": round((last / first - 1) * 100, 1),
        "pire_chute_bot_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 1),
        "pire_chute_achat_simple_pct": round(float((bh / bh.cummax() - 1).min()) * 100, 1),
        "trades": len(trades),
        "trades_gagnants_pct": round(sum(t > 0 for t in trades) / len(trades) * 100, 1) if trades else 0.0,
        "temps_investi_pct": round(float(df["uptrend"].iloc[warmup:-1].mean()) * 100, 1),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv")
    p.add_argument("--exchange", action="store_true", help="historique via ta plateforme")
    p.add_argument("--since", type=int, default=2021, help="année de début (archives)")
    args = p.parse_args()
    cfg = load_config()
    if args.csv:
        df = pd.read_csv(args.csv)
    elif args.exchange:
        from .broker import fetch_candles, make_exchange
        df = fetch_candles(make_exchange(cfg, authenticated=False), cfg.symbol, cfg.timeframe, 720)
    else:
        print(f"Chargement de l'historique {cfg.symbol} depuis {args.since}…")
        df = resample(download_history(cfg.symbol, args.since), cfg.timeframe)
    print(f"\n{cfg.symbol} | bougies {cfg.timeframe} | EMA {cfg.ema_fast}/{cfg.ema_slow} | "
          f"{cfg.position_pct:g} % investi | {len(df)} bougies")
    for k, v in run_backtest(df, cfg, cfg.paper_start_balance).items():
        print(f"  {k:28} {v}")


if __name__ == "__main__":
    main()
