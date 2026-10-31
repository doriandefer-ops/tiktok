"""Mesure l'apport des absences sur une saison passée et règle K_ATT / K_DEF.

Pour chaque match de la saison 2025-26, le modèle est ajusté sur le passé (comme backtest.py),
puis corrigé selon les absents connus de l'API (blessés et suspendus, sans les compositions qui
coûteraient une requête par match). L'importance des joueurs vient de la saison précédente pour ne
jamais utiliser d'information future. Résultat : data/calibration.json, lu par availability.py.

Coût : environ 2 + 2 x 35 requêtes par championnat (calendrier, blessés, joueurs de 2 saisons),
soit ~700 requêtes pour les 10 : prévoir une offre payante, ou lancer un championnat par jour
(python3 calibrate.py E0) sur l'offre gratuite, le cache gardant les réponses déjà obtenues."""
import itertools
import json
import pathlib
import sys

import numpy as np
import pandas as pd

import apifootball as api
import availability
import backtest
import data
import model

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "calibration.json"
SEASON = 2025                      # saison API-Football 2025-26 = saison football-data "2526"
GRID_ATT = (0.0, 0.3, 0.6, 1.0)
GRID_DEF = (0.0, 0.3, 0.6, 1.0)


def league_rows(code: str, results: pd.DataFrame) -> list:
    league = api.LEAGUE_IDS[code]
    fx = api.season_fixtures(league, SEASON)
    inj = api.injuries(league, SEASON)
    stats = api.players(league, SEASON - 1)
    df = results[results["Div"] == code]
    test = df[(df["Season"] == "2526")]
    rows = []
    for week, games in test.groupby(test["Date"].dt.to_period("W-MON")):
        fit = model.fit(df, week.start_time)
        for _, g in games.iterrows():
            f = availability.match_fixture(fx, g["Date"].strftime("%Y-%m-%d"), g["HomeTeam"], g["AwayTeam"])
            if not f:
                continue
            fid, hid, aid = f["fixture"]["id"], f["teams"]["home"]["id"], f["teams"]["away"]["id"]
            ab_h, _ = availability.absences(fid, hid, inj, [], availability.importance(stats, hid))
            ab_a, _ = availability.absences(fid, aid, inj, [], availability.importance(stats, aid))
            rows.append({"g": g, "fit": fit, "ab_h": ab_h, "ab_a": ab_a})
    return rows


def evaluate(rows: list, k_att: float, k_def: float) -> dict:
    ll, ll_mkt, pl, n_abs = [], [], [], 0
    for r in rows:
        g = r["g"]
        lm, mm = availability.multipliers(r["ab_h"], r["ab_a"], k_att, k_def)
        n_abs += (lm != 1.0 or mm != 1.0)
        mk = model.markets(r["fit"].score_matrix(g["HomeTeam"], g["AwayTeam"], lm, mm))
        p = np.array([mk["home"], mk["draw"], mk["away"]])
        res = "HDA".index(g["FTR"])
        ll.append(-np.log(p[res]))
        m = backtest.implied(g, ["AvgCH", "AvgCD", "AvgCA"])
        if m is not None:
            ll_mkt.append(-np.log(m[res]))
        o = backtest.implied(g, ["AvgH", "AvgD", "AvgA"])
        if o is not None:
            q = backtest.blend(p, o)
            for k, r_ in enumerate("HDA"):
                odd = g[f"Avg{r_}"]
                if q[k] * odd - 1 >= backtest.EDGE:
                    pl.append(odd - 1 if g["FTR"] == r_ else -1)
    return {"k_att": k_att, "k_def": k_def, "matches": len(rows), "adjusted": n_abs,
            "logloss": float(np.mean(ll)), "logloss_market_close": float(np.mean(ll_mkt)),
            "bets": len(pl), "roi": float(np.mean(pl)) if pl else None}


def main(codes) -> None:
    results = data.results()
    rows = []
    for code in codes:
        try:
            rows += league_rows(code, results)
            print(f"{code} : ok ({len(rows)} matchs cumulés)")
        except api.BudgetExceeded as e:
            print(f"{code} : {e}. Relancer demain, le cache garde les réponses déjà obtenues.")
            break
    if not rows:
        return
    grid = [evaluate(rows, a, d) for a, d in itertools.product(GRID_ATT, GRID_DEF)]
    base = next(r for r in grid if r["k_att"] == 0 and r["k_def"] == 0)
    best = min(grid, key=lambda r: r["logloss"])
    print(pd.DataFrame(grid).round(4).to_string(index=False))
    print(f"\nSans absences : {base['logloss']:.4f} · meilleur réglage : {best['logloss']:.4f} "
          f"(K_ATT={best['k_att']}, K_DEF={best['k_def']}) · marché à la clôture : {base['logloss_market_close']:.4f}")
    OUT.write_text(json.dumps({"leagues": list(codes), "best": best, "baseline": base, "grid": grid}, indent=1))
    print("Note : avec 4 x 4 réglages testés, un gain inférieur à ~0,002 n'est pas significatif.")


if __name__ == "__main__":
    main(sys.argv[1:] or list(data.LEAGUES))
