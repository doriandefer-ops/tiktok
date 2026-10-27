"""Backtest walk-forward : chaque semaine, le modèle est réajusté sur le passé puis prédit les matchs
de la semaine, sans jamais voir le futur. Compare au marché (cotes d'ouverture et de clôture)."""
import json
import pathlib
import sys

import numpy as np
import pandas as pd

import data
import model

OUT = pathlib.Path(__file__).resolve().parent.parent / "data"
START = pd.Timestamp("2025-08-01")
EDGE = 0.05          # value minimale exigée : p_modèle × cote − 1
BLEND = 0.35         # poids du modèle dans la probabilité publiée (le reste = marché)
OUTCOMES = [("home", "H"), ("draw", "D"), ("away", "A")]


def implied(row, cols):
    odds = np.array([row[c] for c in cols], float)
    if np.isnan(odds).any() or (odds <= 1).any():
        return None
    inv = 1 / odds
    return inv / inv.sum()  # retire la marge du bookmaker


def blend(p_model: np.ndarray, p_market) -> np.ndarray:
    if p_market is None:
        return p_model
    return BLEND * p_model + (1 - BLEND) * p_market


def predict_league(df: pd.DataFrame) -> list:
    rows = []
    test = df[df["Date"] >= START]
    for week, games in test.groupby(test["Date"].dt.to_period("W-MON")):
        fit = model.fit(df, week.start_time)
        for _, g in games.iterrows():
            mk = model.markets(fit.score_matrix(g["HomeTeam"], g["AwayTeam"]))
            rows.append({"g": g, "mk": mk})
    return rows


def run(leagues=None) -> dict:
    df = data.results()
    records = []
    for code in leagues or data.LEAGUES:
        league = df[df["Div"] == code]
        for r in predict_league(league):
            g, mk = r["g"], r["mk"]
            p_model = np.array([mk["home"], mk["draw"], mk["away"]])
            p_open = implied(g, ["AvgH", "AvgD", "AvgA"])
            p_close = implied(g, ["PSCH", "PSCD", "PSCA"])
            if p_close is None:
                p_close = implied(g, ["AvgCH", "AvgCD", "AvgCA"])
            p_pub = blend(p_model, p_open)
            pick = None
            for k, (name, res) in enumerate(OUTCOMES):
                odd = g[f"Avg{res}"]
                if p_open is not None and p_pub[k] * odd - 1 >= EDGE:
                    if pick is None or p_pub[k] * odd > pick["ev"]:
                        pick = {"outcome": name, "odds": float(odd), "p": float(p_pub[k]),
                                "ev": float(p_pub[k] * odd), "won": g["FTR"] == res,
                                "close": float(g[f"PSC{res}"]) if not np.isnan(g[f"PSC{res}"]) else None}
            records.append({
                "league": code, "date": g["Date"].strftime("%Y-%m-%d"),
                "home": g["HomeTeam"], "away": g["AwayTeam"],
                "score": f"{g['FTHG']}-{g['FTAG']}", "result": g["FTR"],
                "p_model": p_model.round(4).tolist(),
                "p_pub": p_pub.round(4).tolist(),
                "p_open": None if p_open is None else p_open.round(4).tolist(),
                "p_close": None if p_close is None else p_close.round(4).tolist(),
                "pick": pick,
            })
    return summarize(records)


def logloss(records, key):
    idx = {"H": 0, "D": 1, "A": 2}
    vals = [-np.log(r[key][idx[r["result"]]]) for r in records if r[key] is not None and r["p_close"] is not None]
    return float(np.mean(vals)), len(vals)


def summarize(records) -> dict:
    picks = [r for r in records if r["pick"]]
    profit = sum(p["pick"]["odds"] - 1 if p["pick"]["won"] else -1 for p in picks)
    clv = [p["pick"]["odds"] / p["pick"]["close"] - 1 for p in picks if p["pick"]["close"]]
    by_month = {}
    for p in sorted(picks, key=lambda r: r["date"]):
        m = p["date"][:7]
        by_month.setdefault(m, {"bets": 0, "profit": 0.0})
        by_month[m]["bets"] += 1
        by_month[m]["profit"] += p["pick"]["odds"] - 1 if p["pick"]["won"] else -1
    summary = {
        "matches": len(records),
        "logloss": {k: logloss(records, k)[0] for k in ["p_model", "p_pub", "p_open", "p_close"]},
        "bets": len(picks),
        "hit_rate": float(np.mean([p["pick"]["won"] for p in picks])) if picks else None,
        "roi": profit / len(picks) if picks else None,
        "profit_units": profit,
        "clv": float(np.mean(clv)) if clv else None,
        "by_month": by_month,
        "params": {"edge": EDGE, "blend": BLEND, "start": str(START.date())},
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "backtest.json").write_text(json.dumps(summary, indent=1))
    (OUT / "history.json").write_text(json.dumps(records, default=bool))
    return summary


if __name__ == "__main__":
    s = run(sys.argv[1:] or None)
    print(json.dumps({k: v for k, v in s.items() if k != "by_month"}, indent=1))
