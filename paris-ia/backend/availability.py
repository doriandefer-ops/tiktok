"""Absences (blessés, suspendus, compositions officielles) et leur effet sur les buts attendus.

Principe : chaque joueur a un poids offensif (part des buts + passes décisives de son équipe) et un
poids de temps de jeu (part des minutes). Les absences réduisent l'attaque de l'équipe et
affaiblissent sa défense, ce qui modifie les buts attendus des deux équipes avant le calcul des
probabilités. Les coefficients K_ATT et K_DEF se règlent avec calibrate.py."""
import difflib
import json
import pathlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import apifootball as api

K_ATT = 0.6     # part de la production offensive perdue réellement répercutée sur l'attaque
K_DEF = 0.5     # effet des titulaires défensifs absents sur les buts encaissés
MAX_ATT_LOSS = 0.35
MAX_DEF_LOSS = 0.25
DEF_WEIGHT = {"Goalkeeper": 1.0, "Defender": 1.0, "Midfielder": 0.5, "Attacker": 0.0}
STARTER = 0.5   # un joueur qui a disputé au moins 50 % des minutes est un titulaire habituel

# Réglage mesuré par calibrate.py, s'il a été lancé et s'il améliore réellement les prédictions.
_CAL = pathlib.Path(__file__).resolve().parent.parent / "data" / "calibration.json"
if _CAL.exists():
    _best = json.loads(_CAL.read_text())["best"]
    K_ATT, K_DEF = _best["k_att"], _best["k_def"]

# Noms football-data.co.uk qui ne ressemblent pas assez aux noms API-Football.
ALIASES = {
    "paris sg": "paris saint germain", "man united": "manchester united", "man city": "manchester city",
    "nott'm forest": "nottingham forest", "wolves": "wolverhampton wanderers", "spurs": "tottenham",
    "ath madrid": "atletico madrid", "ath bilbao": "athletic club", "sociedad": "real sociedad",
    "betis": "real betis", "vallecano": "rayo vallecano", "espanol": "espanyol", "milan": "ac milan",
    "inter": "inter", "m'gladbach": "borussia monchengladbach", "ein frankfurt": "eintracht frankfurt",
    "fc koln": "1. fc koln", "sp lisbon": "sporting cp", "sp braga": "sc braga", "for sittard": "fortuna sittard",
    "nijmegen": "nec nijmegen", "st gilloise": "union st. gilloise", "club brugge": "club brugge kv",
}
_STOP = {"fc", "cf", "ac", "afc", "sc", "club", "cd", "ud", "sv", "vfb", "vfl", "rc", "as", "ss", "us", "1"}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().strip()
    s = ALIASES.get(s, s)
    words = [w for w in re.split(r"[^a-z0-9']+", s) if w and w not in _STOP]
    return " ".join(words)


def similarity(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if a == b or (a and b and (a in b or b in a)):
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_fixture(api_fixtures: list, day: str, home: str, away: str):
    """Retrouve le match API correspondant à un match football-data (même jour à ±1, noms proches)."""
    d = datetime.fromisoformat(day).date()
    best, best_score = None, 1.3
    for f in api_fixtures:
        fd = datetime.fromisoformat(f["fixture"]["date"].replace("Z", "+00:00")).date()
        if abs((fd - d).days) > 1:
            continue
        score = similarity(home, f["teams"]["home"]["name"]) + similarity(away, f["teams"]["away"]["name"])
        if score > best_score:
            best, best_score = f, score
    return best


def importance(players_resp: list, team_id: int) -> dict:
    """Poids de chaque joueur de l'équipe : part des minutes et part de la production offensive."""
    rows = []
    for p in players_resp:
        for st in p.get("statistics", []):
            if st.get("team", {}).get("id") != team_id:
                continue
            games, goals = st.get("games", {}), st.get("goals", {})
            rows.append({"id": p["player"]["id"], "name": p["player"]["name"],
                         "pos": games.get("position") or "",
                         "minutes": games.get("minutes") or 0,
                         "att": (goals.get("total") or 0) + 0.7 * (goals.get("assists") or 0)})
    max_min = max((r["minutes"] for r in rows), default=0) or 1
    total_att = sum(r["att"] for r in rows) or 1
    return {r["id"]: {"name": r["name"], "pos": r["pos"], "min_share": r["minutes"] / max_min,
                      "att_share": r["att"] / total_att} for r in rows}


def absences(fixture_id: int, team_id: int, injuries_resp: list, lineup_resp: list, weights: dict) -> tuple:
    """Liste des absents d'une équipe pour un match, et si la composition officielle est connue."""
    lineup = next((l for l in lineup_resp if l.get("team", {}).get("id") == team_id), None)
    out = {}
    for inj in injuries_resp:
        if inj.get("fixture", {}).get("id") != fixture_id or inj.get("team", {}).get("id") != team_id:
            continue
        pl = inj["player"]
        doubtful = (pl.get("type") or "").lower().startswith("questionable")
        out[pl["id"]] = {"name": pl.get("name"), "reason": pl.get("reason") or "", "weight": 0.5 if doubtful else 1.0}
    if lineup and lineup.get("startXI"):
        starting = {s["player"]["id"] for s in lineup["startXI"]}
        out = {pid: a | {"weight": 1.0} for pid, a in out.items() if pid not in starting}
        for pid, w in weights.items():
            if w["min_share"] >= STARTER and pid not in starting and pid not in out:
                out[pid] = {"name": w["name"], "reason": "Absent de la composition", "weight": 1.0}
    result = []
    for pid, a in out.items():
        w = weights.get(pid, {"pos": "", "min_share": 0.0, "att_share": 0.0})
        result.append(a | {"pos": w["pos"], "min_share": round(w["min_share"], 3), "att_share": round(w["att_share"], 3)})
    result.sort(key=lambda a: -(a["att_share"] + a["min_share"]) * a["weight"])
    return result, bool(lineup and lineup.get("startXI"))


def losses(absent: list, k_att: float = K_ATT, k_def: float = K_DEF) -> tuple:
    att = min(MAX_ATT_LOSS, k_att * sum(a["weight"] * a["att_share"] for a in absent))
    dfn = min(MAX_DEF_LOSS, k_def * sum(a["weight"] * a["min_share"] * DEF_WEIGHT.get(a["pos"], 0.5)
                                        for a in absent) / 5)
    return att, dfn


def multipliers(absent_home: list, absent_away: list, k_att: float = K_ATT, k_def: float = K_DEF) -> tuple:
    """Multiplicateurs des buts attendus (domicile, extérieur)."""
    att_h, def_h = losses(absent_home, k_att, k_def)
    att_a, def_a = losses(absent_away, k_att, k_def)
    return (1 - att_h) * (1 + def_a), (1 - att_a) * (1 + def_h)


def for_league(code: str, games: list, season: int) -> dict:
    """Absences et multiplicateurs pour les matchs à venir d'un championnat.

    `games` = liste de (date ISO, domicile, extérieur) au format football-data. Renvoie un dict
    {(date, domicile, extérieur): info}. Les erreurs d'API (quota, clé) laissent le match sans ajustement."""
    league = api.LEAGUE_IDS[code]
    days = sorted(g[0] for g in games)
    start = (datetime.fromisoformat(days[0]) - timedelta(days=1)).date().isoformat()
    end = (datetime.fromisoformat(days[-1]) + timedelta(days=1)).date().isoformat()
    fx = api.fixtures(league, season, start, end)
    inj = api.injuries(league, season)
    try:
        stats = api.players(league, season)
    except api.BudgetExceeded:
        stats = []  # absents affichés, mais sans poids : pas d'ajustement du modèle
    now = datetime.now(timezone.utc)
    out = {}
    for day, home, away in games:
        f = match_fixture(fx, day, home, away)
        if not f:
            continue
        fid = f["fixture"]["id"]
        kickoff = datetime.fromisoformat(f["fixture"]["date"].replace("Z", "+00:00"))
        lu = []
        if timedelta(0) <= kickoff - now <= timedelta(minutes=90):
            try:
                lu = api.lineups(fid)
            except api.BudgetExceeded:
                pass
        hid, aid = f["teams"]["home"]["id"], f["teams"]["away"]["id"]
        ab_h, lu_h = absences(fid, hid, inj, lu, importance(stats, hid))
        ab_a, lu_a = absences(fid, aid, inj, lu, importance(stats, aid))
        lam_m, mu_m = multipliers(ab_h, ab_a) if stats else (1.0, 1.0)
        out[(day, home, away)] = {"fixture": fid, "absent_home": ab_h, "absent_away": ab_a,
                                  "lineups": lu_h and lu_a, "weighted": bool(stats),
                                  "lam_mult": round(lam_m, 4), "mu_mult": round(mu_m, 4)}
    return out
