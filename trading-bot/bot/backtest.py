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

COST = 0.0045  # 0,4 % de frais Kraken (ordre au marché) + 0,05 % de glissement
ARCHIVE = "https://data.binance.vision/data/spot/monthly/klines/{s}/{i}/{s}-{i}-{y}-{m:02d}.zip"


def download_history(symbol: str, since: int, interval: str = "1h", since_month: int = 1) -> pd.DataFrame:
    """Bougies depuis les archives publiques de Binance (mises en cache dans data/)."""
    pair = symbol.replace("/", "").upper()
    os.makedirs("data", exist_ok=True)
    frames, today = [], date.today()
    for y in range(since, today.year + 1):
        for m in range(1, 13):
            if (y, m) >= (today.year, today.month):
                break
            if (y, m) < (since, since_month):
                continue
            path = f"data/{pair}-{interval}-{y}-{m:02d}.csv"
            if not os.path.exists(path):
                try:
                    with urllib.request.urlopen(ARCHIVE.format(s=pair, i=interval, y=y, m=m), timeout=30) as r:
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


def run_backtest(data: dict, cfg, start_balance: float = 1000.0) -> dict:
    """Portefeuille multi-cryptos avec capital commun.
    data : {symbole: DataFrame}. Décision à la clôture d'une bougie, exécution à l'ouverture de la suivante."""
    if isinstance(data, pd.DataFrame):
        data = {"X": data}
    frames = {s: add_indicators(df, cfg).set_index("ts") for s, df in data.items()}
    common = sorted(set.intersection(*(set(f.index) for f in frames.values())))
    frames = {s: f.loc[common].reset_index() for s, f in frames.items()}
    n, warmup = len(frames), min_candles(cfg)
    if len(common) <= warmup + 1:
        raise SystemExit(f"Pas assez de bougies ({len(common)}) : il en faut plus de {warmup}")
    share = cfg.position_pct / 100 / n
    cash, curve = start_balance, []
    qty = {s: 0.0 for s in frames}
    entry = {s: 0.0 for s in frames}
    trades = {s: [] for s in frames}
    for i in range(warmup + 1, len(common)):
        opens = {s: float(f["open"].iloc[i]) for s, f in frames.items()}
        for s, f in frames.items():  # ventes d'abord, pour libérer du liquide
            if qty[s] > 0 and not f["uptrend"].iloc[i - 1]:
                cash += qty[s] * opens[s] * (1 - COST)
                trades[s].append(opens[s] * (1 - COST) ** 2 / entry[s] - 1)
                qty[s] = 0.0
        for s, f in frames.items():
            if qty[s] == 0 and f["uptrend"].iloc[i - 1]:
                equity = cash + sum(qty[k] * opens[k] for k in frames)
                spend = min(equity * share, cash)
                qty[s], entry[s] = spend * (1 - COST) / opens[s], opens[s]
                cash -= spend
        curve.append(cash + sum(qty[s] * float(f["close"].iloc[i]) for s, f in frames.items()))
    eq = pd.Series(curve)
    # Référence « achat simple » : capital réparti à parts égales, acheté au début et gardé
    bh = sum(f["close"].iloc[warmup + 1:].reset_index(drop=True) / float(f["open"].iloc[warmup + 1])
             for f in frames.values()) / n
    all_trades = [t for ts in trades.values() for t in ts]
    first = next(iter(frames.values()))
    res = {
        "periode": f"{str(first['ts'].iloc[warmup + 1])[:10]} -> {str(first['ts'].iloc[-1])[:10]}",
        "capital_final": round(float(eq.iloc[-1]), 2),
        "gain_bot_pct": round(float(eq.iloc[-1] / start_balance - 1) * 100, 1),
        "gain_achat_simple_pct": round(float(bh.iloc[-1] - 1) * 100, 1),
        "pire_chute_bot_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 1),
        "pire_chute_achat_simple_pct": round(float((bh / bh.cummax() - 1).min()) * 100, 1),
        "trades": len(all_trades),
        "trades_gagnants_pct": round(sum(t > 0 for t in all_trades) / len(all_trades) * 100, 1) if all_trades else 0.0,
    }
    if n > 1:
        for s in frames:
            res[f"trades_{s}"] = len(trades[s])
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", help="un seul fichier CSV (une seule crypto)")
    p.add_argument("--exchange", action="store_true", help="historique via ta plateforme")
    p.add_argument("--since", type=int, default=2021, help="année de début (archives)")
    args = p.parse_args()
    cfg = load_config()
    if args.csv:
        data = {cfg.symbols[0]: pd.read_csv(args.csv)}
    elif args.exchange:
        from .broker import fetch_candles, make_exchange
        ex = make_exchange(cfg, authenticated=False)
        data = {s: fetch_candles(ex, s, cfg.timeframe, 720) for s in cfg.symbols}
    else:
        data = {}
        for s in cfg.symbols:
            print(f"Chargement de l'historique {s} depuis {args.since}…")
            data[s] = resample(download_history(s, args.since), cfg.timeframe)
    print(f"\n{', '.join(data)} | bougies {cfg.timeframe} | EMA {cfg.ema_fast}/{cfg.ema_slow} | "
          f"jusqu'à {cfg.position_pct:g} % investi ({cfg.position_pct / len(data):g} % par crypto)")
    for k, v in run_backtest(data, cfg, cfg.paper_start_balance).items():
        print(f"  {k:28} {v}")


if __name__ == "__main__":
    main()
