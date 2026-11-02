"""Mesure l'apport des absences sur une saison passée et règle K_ATT / K_DEF.

Pour chaque match de la saison étudiée, le modèle est ajusté sur le passé (comme backtest.py), puis
corrigé selon les absents connus (blessés et suspendus, sans les compositions, qui coûteraient une
requête par match). L'importance des joueurs vient des meilleurs buteurs et passeurs de la saison
précédente : aucune information future n'est utilisée. Résultat : data/calibration.json, lu par
availability.py.

Données API-Football, deux façons de les obtenir (40 requêtes, compatibles avec l'offre gratuite
pour les saisons 2022 à 2024) :
  - en direct avec API_FOOTBALL_KEY : python3 calibrate.py
  - depuis le site en ligne, qui garde la clé : récupérer /api/admin/apidump?season=2024 (en-tête
    x-admin-token = APP_SECRET) dans un fichier, puis python3 calibrate.py --dump fichier.json"""
import argparse
import itertools
import json
import pathlib

import numpy as np
import pandas as pd

import apifootball as api
import availability
import backtest
import data
import model

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "calibration.json"
GRID_ATT = (0.0, 0.3, 0.6, 1.0, 1.5)
GRID_DEF = (0.0, 0.3, 0.6, 1.0)


def fd_season(season: int) -> str:
    """Saison API-Football (année de début) -> code football-data ("2425" pour 2024)."""
    return f"{season % 100:02d}{(season + 1) % 100:02d}"


def fetch(season: int) -> dict:
    out = {"season": season, "leagues": {}}
    for code, league in api.LEAGUE_IDS.items():
        out["leagues"][code] = {"fixtures": api.season_fixtures(league, season),
                                "injuries": api.injuries(league, season),
                                "key_players": api.key_players(league, season - 1)}
    return out


def league_rows(code: str, dump: dict, results: pd.DataFrame, season: int) -> tuple:
    d = dump["leagues"].get(code, {})
    if "error" in d or not d.get("fixtures"):
        return [], 0
    df = results[results["Div"] == code]
    prev = data.team_totals(df[df["Season"] == fd_season(season - 1)])
    test = df[df["Season"] == fd_season(season)]
    rows, unmatched = [], 0
    for week, games in test.groupby(test["Date"].dt.to_period("W-MON")):
        fit = model.fit(df, week.start_time)
        for _, g in games.iterrows():
            f = availability.match_fixture(d["fixtures"], g["Date"].strftime("%Y-%m-%d"), g["HomeTeam"], g["AwayTeam"])
            if not f:
                unmatched += 1
                continue
            fid, hid, aid = f["fixture"]["id"], f["teams"]["home"]["id"], f["teams"]["away"]["id"]
            w_h = availability.importance(d["key_players"], hid, *prev.get(g["HomeTeam"], (None, None)))
            w_a = availability.importance(d["key_players"], aid, *prev.get(g["AwayTeam"], (None, None)))
            ab_h, _ = availability.absences(fid, hid, d["injuries"], [], w_h)
            ab_a, _ = availability.absences(fid, aid, d["injuries"], [], w_a)
            rows.append({"g": g, "fit": fit, "ab_h": ab_h, "ab_a": ab_a})
    return rows, unmatched


def evaluate(rows: list, k_att: float, k_def: float) -> dict:
    ll, ll_mkt, ll_pub, adjusted = [], [], [], 0
    for r in rows:
        g = r["g"]
        lm, mm = availability.multipliers(r["ab_h"], r["ab_a"], k_att, k_def)
        adjusted += (lm != 1.0 or mm != 1.0)
        mk = model.markets(r["fit"].score_matrix(g["HomeTeam"], g["AwayTeam"], lm, mm))
        p = np.array([mk["home"], mk["draw"], mk["away"]])
        res = "HDA".index(g["FTR"])
        m_close = backtest.implied(g, ["AvgCH", "AvgCD", "AvgCA"])
        m_open = backtest.implied(g, ["AvgH", "AvgD", "AvgA"])
        if m_close is None or m_open is None:
            continue
        ll.append(-np.log(p[res]))
        ll_pub.append(-np.log(backtest.blend(p, m_open)[res]))
        ll_mkt.append(-np.log(m_close[res]))
    return {"k_att": k_att, "k_def": k_def, "matches": len(ll), "adjusted": adjusted,
            "logloss_model": float(np.mean(ll)), "logloss_published": float(np.mean(ll_pub)),
            "logloss_market_close": float(np.mean(ll_mkt))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", help="fichier JSON issu de /api/admin/apidump")
    ap.add_argument("--season", type=int, default=2024)
    args = ap.parse_args()
    dump = json.loads(pathlib.Path(args.dump).read_text()) if args.dump else fetch(args.season)
    season = dump["season"]
    results = data.results()
    rows = []
    for code in data.LEAGUES:
        r, unmatched = league_rows(code, dump, results, season)
        n_abs = sum(1 for x in r if x["ab_h"] or x["ab_a"])
        print(f"{code} : {len(r)} matchs associés, {unmatched} non associés, {n_abs} avec au moins un absent")
        rows += r
    if not rows:
        print("Aucun match exploitable.")
        return
    grid = [evaluate(rows, a, d) for a, d in itertools.product(GRID_ATT, GRID_DEF)]
    base = next(r for r in grid if r["k_att"] == 0 and r["k_def"] == 0)
    best = min(grid, key=lambda r: r["logloss_model"])
    print(pd.DataFrame(grid).round(4).to_string(index=False))
    print(f"\nModèle sans absences : {base['logloss_model']:.4f} · avec absences (K_ATT={best['k_att']}, "
          f"K_DEF={best['k_def']}) : {best['logloss_model']:.4f} · marché à la clôture : {base['logloss_market_close']:.4f}")
    OUT.write_text(json.dumps({"season": season, "best": best, "baseline": base, "grid": grid}, indent=1))


if __name__ == "__main__":
    main()
