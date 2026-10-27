"""Calcule les probabilités des matchs à venir et les écrit dans data/predictions.json."""
import json
import pathlib
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import backtest
import data
import model

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "predictions.json"


def run(download: bool = True) -> list:
    if download:
        data.download()
    results, fixtures = data.results(), data.fixtures()
    now = pd.Timestamp.now().normalize()
    preds = []
    for code, games in fixtures.groupby("Div"):
        fit = model.fit(results[results["Div"] == code], now)
        for _, g in games.iterrows():
            mk = model.markets(fit.score_matrix(g["HomeTeam"], g["AwayTeam"]))
            p_model = np.array([mk["home"], mk["draw"], mk["away"]])
            p_open = backtest.implied(g, ["AvgH", "AvgD", "AvgA"])
            p_pub = backtest.blend(p_model, p_open)
            value = []
            for k, (name, res) in enumerate(backtest.OUTCOMES):
                odd = g.get(f"Max{res}")
                if odd and not np.isnan(odd):
                    ev = p_pub[k] * odd - 1
                    if ev >= backtest.EDGE:
                        value.append({"outcome": name, "odds": float(odd), "edge": round(float(ev), 3)})
            preds.append({
                "league": code, "league_name": data.LEAGUES[code],
                "date": g["Date"].strftime("%Y-%m-%d"), "time": g.get("Time", ""),
                "home": g["HomeTeam"], "away": g["AwayTeam"],
                "probs": {"home": float(p_pub[0]), "draw": float(p_pub[1]), "away": float(p_pub[2])},
                "model": {k: mk[k] for k in ["home", "draw", "away"]},
                "market": None if p_open is None else dict(zip(["home", "draw", "away"], p_open.tolist())),
                "over25": mk["over25"], "btts": mk["btts"],
                "xg": [round(mk["xg_home"], 2), round(mk["xg_away"], 2)],
                "scores": mk["scores"], "value": value,
            })
    preds.sort(key=lambda p: (p["date"], p["time"] or "", p["league"]))
    OUT.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                               "matches": preds}, indent=1))
    return preds


if __name__ == "__main__":
    print(f"{len(run())} matchs prédits")
