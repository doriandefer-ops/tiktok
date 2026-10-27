"""Téléchargement des résultats et cotes (football-data.co.uk) pour les 10 championnats."""
import io
import pathlib
import urllib.request

import pandas as pd

LEAGUES = {
    "E0": "Premier League",
    "SP1": "La Liga",
    "I1": "Serie A",
    "D1": "Bundesliga",
    "F1": "Ligue 1",
    "N1": "Eredivisie",
    "P1": "Liga Portugal",
    "B1": "Pro League (Belgique)",
    "T1": "Süper Lig",
    "SC0": "Premiership (Écosse)",
}
SEASONS = ["2324", "2425", "2526", "2627"]
BASE = "https://www.football-data.co.uk"
RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

# Colonnes utiles : cotes d'ouverture (moyenne, max, Pinnacle) et de clôture.
ODDS = ["AvgH", "AvgD", "AvgA", "MaxH", "MaxD", "MaxA", "PSH", "PSD", "PSA",
        "AvgCH", "AvgCD", "AvgCA", "PSCH", "PSCD", "PSCA",
        "Avg>2.5", "Avg<2.5", "Max>2.5", "Max<2.5", "AvgC>2.5", "AvgC<2.5"]


def _get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def _parse(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), on_bad_lines="skip")
    df = df.dropna(subset=["HomeTeam", "AwayTeam"])
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    return df.reindex(columns=list(dict.fromkeys([*df.columns, *ODDS]))).copy()


def download(refresh_current: bool = True) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for season in SEASONS:
        for code in LEAGUES:
            path = RAW / f"{season}_{code}.csv"
            if path.exists() and not (refresh_current and season == SEASONS[-1]):
                continue
            path.write_text(_get(f"{BASE}/mmz4281/{season}/{code}.csv"), encoding="utf-8")
    (RAW / "fixtures.csv").write_text(_get(f"{BASE}/fixtures.csv"), encoding="utf-8")


def results() -> pd.DataFrame:
    frames = []
    for season in SEASONS:
        for code in LEAGUES:
            path = RAW / f"{season}_{code}.csv"
            if not path.exists():
                continue
            df = _parse(path.read_text(encoding="utf-8"))
            frames.append(df.assign(Season=season))
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["Date", "FTHG", "FTAG"])
    df["FTHG"] = df["FTHG"].astype(int)
    df["FTAG"] = df["FTAG"].astype(int)
    keep = ["Div", "Season", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"] + ODDS
    return df[keep].sort_values("Date").reset_index(drop=True)


def fixtures() -> pd.DataFrame:
    path = RAW / "fixtures.csv"
    if not path.exists():
        return pd.DataFrame()
    df = _parse(path.read_text(encoding="utf-8"))
    df = df[df["Div"].isin(LEAGUES)]
    keep = ["Div", "Date", "Time", "HomeTeam", "AwayTeam"] + ODDS
    return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


if __name__ == "__main__":
    download()
    r = results()
    print(f"{len(r)} matchs joués, {len(fixtures())} matchs à venir")
