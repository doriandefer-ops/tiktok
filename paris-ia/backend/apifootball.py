"""Client API-Football v3 (api-sports.io) : calendrier, blessés, compositions, statistiques joueurs.

Clé : variable d'environnement API_FOOTBALL_KEY (https://dashboard.api-football.com).
Chaque réponse est mise en cache sur disque, et un budget quotidien évite de dépasser le quota
(100 requêtes par jour sur l'offre gratuite)."""
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request
from datetime import date

BASE = "https://v3.football.api-sports.io"
CACHE = pathlib.Path(__file__).resolve().parent.parent / "data" / "api"
DAILY_BUDGET = int(os.environ.get("API_FOOTBALL_DAILY_BUDGET", "90"))

# Identifiants API-Football des 10 championnats (codes football-data.co.uk -> id de ligue).
LEAGUE_IDS = {"E0": 39, "SP1": 140, "I1": 135, "D1": 78, "F1": 61,
              "N1": 88, "P1": 94, "B1": 144, "T1": 203, "SC0": 179}


class BudgetExceeded(RuntimeError):
    pass


def key() -> str | None:
    return os.environ.get("API_FOOTBALL_KEY") or None


def season_year(d: date) -> int:
    """API-Football désigne une saison par son année de début (2026 pour 2026-27)."""
    return d.year if d.month >= 7 else d.year - 1


def _budget_file() -> pathlib.Path:
    return CACHE / "budget.json"


def used_today() -> int:
    f = _budget_file()
    if not f.exists():
        return 0
    b = json.loads(f.read_text())
    return b["count"] if b["day"] == date.today().isoformat() else 0


def _spend() -> None:
    n = used_today()
    if n >= DAILY_BUDGET:
        raise BudgetExceeded(f"Budget quotidien atteint ({DAILY_BUDGET} requêtes)")
    _budget_file().write_text(json.dumps({"day": date.today().isoformat(), "count": n + 1}))


def call(endpoint: str, params: dict, ttl: float) -> dict:
    """Appelle l'API (ou relit le cache s'il a moins de `ttl` secondes) et renvoie la réponse complète."""
    CACHE.mkdir(parents=True, exist_ok=True)
    query = urllib.parse.urlencode(sorted(params.items()))
    path = CACHE / (endpoint.strip("/").replace("/", "_") + "__" + query.replace("&", "_").replace("=", "-") + ".json")
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        return json.loads(path.read_text())
    if not key():
        raise RuntimeError("API_FOOTBALL_KEY manquante")
    _spend()
    req = urllib.request.Request(f"{BASE}/{endpoint.strip('/')}?{query}",
                                 headers={"x-apisports-key": key()})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    if body.get("errors"):
        raise RuntimeError(f"API-Football : {body['errors']}")
    path.write_text(json.dumps(body))
    return body


def get(endpoint: str, params: dict, ttl: float) -> list:
    return call(endpoint, params, ttl).get("response", [])


def fixtures(league: int, season: int, start: str, end: str) -> list:
    return get("fixtures", {"league": league, "season": season, "from": start, "to": end}, ttl=6 * 3600)


def season_fixtures(league: int, season: int) -> list:
    return get("fixtures", {"league": league, "season": season}, ttl=7 * 86400)


def injuries(league: int, season: int) -> list:
    """Toutes les absences de la saison (une requête par championnat), avec l'id du match concerné."""
    return get("injuries", {"league": league, "season": season}, ttl=6 * 3600)


def lineups(fixture: int) -> list:
    """Compositions officielles, publiées en général 20 à 40 minutes avant le coup d'envoi."""
    return get("fixtures/lineups", {"fixture": fixture}, ttl=15 * 60)


def players(league: int, season: int, ttl: float = 7 * 86400) -> list:
    """Statistiques de tous les joueurs du championnat (réponse paginée, environ 30 pages)."""
    out, page, total = [], 1, 1
    while page <= total:
        body = call("players", {"league": league, "season": season, "page": page}, ttl=ttl)
        out.extend(body.get("response", []))
        total = body.get("paging", {}).get("total", 1)
        page += 1
    return out
