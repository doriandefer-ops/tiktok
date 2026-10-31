"""Calcule les probabilités des matchs à venir et les écrit dans data/predictions.json."""
import json
import pathlib
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import apifootball
import availability
import backtest
import data
import model

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "predictions.json"


def run(download: bool = True) -> list:
    if download:
        data.download()
    results, fixtures = data.results(), data.fixtures()
    now = pd.Timestamp.now().normalize()
    fixtures = fixtures[fixtures["Date"] >= now]  # le fichier source garde parfois des matchs déjà joués
    preds = []
    for code, games in fixtures.groupby("Div"):
        fit = model.fit(results[results["Div"] == code], now)
        avail = {}
        if apifootball.key():
            keys = [(g["Date"].strftime("%Y-%m-%d"), g["HomeTeam"], g["AwayTeam"]) for _, g in games.iterrows()]
            try:
                avail = availability.for_league(code, keys, apifootball.season_year(now.date()))
            except Exception as e:  # quota, réseau, clé : on publie sans ajustement
                print(f"{code} : absences indisponibles ({e})")
        for _, g in games.iterrows():
            info = avail.get((g["Date"].strftime("%Y-%m-%d"), g["HomeTeam"], g["AwayTeam"]))
            mk = model.markets(fit.score_matrix(g["HomeTeam"], g["AwayTeam"],
                                                info["lam_mult"] if info else 1.0, info["mu_mult"] if info else 1.0))
            p_model = np.array([mk["home"], mk["draw"], mk["away"]])
            p_open = backtest.implied(g, ["AvgH", "AvgD", "AvgA"])
            p_pub = backtest.blend(p_model, p_open)
            value = []
            for k, (name, res) in enumerate(backtest.OUTCOMES):
                odd = g.get(f"Avg{res}")
                if odd and not np.isnan(odd):
                    ev = p_pub[k] * odd - 1
                    if ev >= backtest.EDGE:
                        value.append({"outcome": name, "odds": float(odd), "edge": round(float(ev), 3)})
            preds.append({
                "league": code, "league_name": data.LEAGUES[code],
                "date": g["Date"].strftime("%Y-%m-%d"), "time": g.get("Time", ""),
                "home": g["HomeTeam"], "away": g["AwayTeam"],
                "probs": {"home": float(p_pub[0]), "draw": float(p_pub[1]), "away": float(p_pub[2])},
                "fair_odds": {k: round(1 / float(v), 2) for k, v in zip(["home", "draw", "away"], p_pub)},
                "avg_odds": {k: float(g[f"Avg{r}"]) for k, r in [("home", "H"), ("draw", "D"), ("away", "A")]
                             if not np.isnan(g[f"Avg{r}"])},
                "margin": None if p_open is None else round(float(sum(1 / g[f"Avg{r}"] for r in "HDA") - 1), 4),
                "model": {k: mk[k] for k in ["home", "draw", "away"]},
                "market": None if p_open is None else dict(zip(["home", "draw", "away"], p_open.tolist())),
                "over25": mk["over25"], "btts": mk["btts"],
                "xg": [round(mk["xg_home"], 2), round(mk["xg_away"], 2)],
                "scores": mk["scores"], "value": value,
                "availability": info,
            })
    preds.sort(key=lambda p: (p["date"], p["time"] or "", p["league"]))
    OUT.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                               "matches": preds}, indent=1))
    return preds


if __name__ == "__main__":
    print(f"{len(run())} matchs prédits")
