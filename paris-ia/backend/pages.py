"""Pages générées côté serveur : une page par match (référencement), liste des matchs, pages légales,
sitemap et robots.txt. Tant que INDEXABLE n'est pas à 1, tout est exclu des moteurs de recherche."""
import html
import json
import os
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
PREDICTIONS = ROOT / "data" / "predictions.json"
LEGAL = ROOT / "frontend" / "legal"
INDEXABLE = os.environ.get("INDEXABLE") == "1"
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]
LEGAL_PAGES = {"mentions-legales": "Mentions légales",
               "cgv": "Conditions générales de vente",
               "confidentialite": "Politique de confidentialité"}

e = html.escape


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def match_slug(m: dict) -> str:
    return f"{m['date']}-{slugify(m['home'])}-{slugify(m['away'])}"


def fr_date(iso: str) -> str:
    y, mth, d = iso.split("-")
    return f"{int(d)} {MONTHS[int(mth) - 1]} {y}"


def num(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def pct(p: float) -> str:
    return f"{round(p * 100)} %"


def load() -> dict:
    if not PREDICTIONS.exists():
        return {"generated": None, "matches": []}
    return json.loads(PREDICTIONS.read_text())


def layout(title: str, description: str, body: str, path: str, extra_head: str = "") -> str:
    robots = "index, follow" if INDEXABLE else "noindex, nofollow"
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="{robots}">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE_URL}{path}">
<link rel="stylesheet" href="/static/style.css">
{extra_head}
</head>
<body>
<header class="top">
  <a class="brand" href="/">Paris<span>IA</span></a>
  <nav><a href="/matchs">Matchs</a><a href="/#bilan">Bilan</a><a href="/#offres">Offres</a></nav>
</header>
<main class="page">
{body}
</main>
{footer()}
</body>
</html>"""


def footer() -> str:
    links = " · ".join(f'<a href="/{k}">{v}</a>' for k, v in LEGAL_PAGES.items())
    return f"""<footer>
  <p><strong>Jouer comporte des risques : endettement, isolement, dépendance.</strong> Pour être aidé, appelez le 09 74 75 13 13 (appel non surtaxé). Interdit aux moins de 18 ans.</p>
  <p>Les probabilités affichées sont des estimations statistiques, pas des conseils de paris. Elles n'augmentent pas vos chances de gagner et ne garantissent aucun gain. Paris IA n'est pas un opérateur de paris.</p>
  <p>{links}</p>
</footer>"""


def de(name: str) -> str:
    return ("d'" if name[:1].lower() in "aeiouyéèêàâî" else "de ") + name


def outcome_sentence(m: dict) -> str:
    p = m["probs"]
    fav = max(p, key=p.get)
    who = {"home": f"une victoire {de(m['home'])}", "draw": "un match nul", "away": f"une victoire {de(m['away'])}"}
    others = [k for k in ("home", "draw", "away") if k != fav]
    return (f"Le modèle estime à {pct(p[fav])} les chances d'{who[fav]}, contre {pct(p[others[0]])} "
            f"pour {who[others[0]]} et {pct(p[others[1]])} pour {who[others[1]]}.")


def match_page(slug: str) -> str | None:
    data = load()
    m = next((m for m in data["matches"] if match_slug(m) == slug), None)
    if not m:
        return None
    p, day = m["probs"], fr_date(m["date"])
    title = f"{m['home']} – {m['away']} : probabilités du match ({day})"
    desc = f"{m['league_name']}, {day}. " + outcome_sentence(m)
    fair = m.get("fair_odds") or {}
    margin = m.get("margin")
    rows = "".join(
        f"<tr><td>{e(label)}</td><td>{pct(p[k])}</td><td>{num(fair[k]) if k in fair else '–'}</td></tr>"
        for k, label in (("home", f"Victoire {m['home']}"), ("draw", "Match nul"), ("away", f"Victoire {m['away']}")))
    av = m.get("availability")
    absences = ""
    if av:
        def names(lst):
            return ", ".join(e(a["name"]) for a in lst) or "aucun absent connu"
        absences = (f"<h2>Absents</h2><p>{e(m['home'])} : {names(av['absent_home'])}.<br>"
                    f"{e(m['away'])} : {names(av['absent_away'])}.</p>")
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "SportsEvent", "name": f"{m['home']} – {m['away']}",
        "startDate": f"{m['date']}T{m.get('time') or '00:00'}", "sport": "Football",
        "homeTeam": {"@type": "SportsTeam", "name": m["home"]},
        "awayTeam": {"@type": "SportsTeam", "name": m["away"]},
        "location": {"@type": "Place", "name": f"Stade de {m['home']}"},
    }, ensure_ascii=False)
    body = f"""<p class="muted"><a href="/matchs">Tous les matchs</a> · {e(m['league_name'])}</p>
<h1>{e(m['home'])} – {e(m['away'])}</h1>
<p class="muted">{e(m['league_name'])}, {day}{(' à ' + e(m['time'])) if m.get('time') else ''}</p>
<p class="lead">{e(outcome_sentence(m))}</p>
<div class="table-wrap"><table>
<thead><tr><th>Issue</th><th>Probabilité</th><th>Cote juste (sans marge)</th></tr></thead>
<tbody>{rows}</tbody></table></div>
{f'<p class="muted">Les bookmakers prélèvent en moyenne une marge de {num(margin * 100, 1)} % sur ce match : leurs cotes sont plus basses que les cotes justes.</p>' if margin else ''}
{absences}
<h2>Comment ces probabilités sont calculées</h2>
<p>Un modèle statistique estime la force offensive et défensive de chaque équipe à partir des buts et des tirs cadrés des trois dernières saisons, puis combine son estimation (30 %) avec les probabilités du marché sans marge (70 %). Le <a href="/#bilan">bilan public</a> compare chaque estimation au résultat réel.</p>
<div class="cta"><p>Probabilités de buts, scores les plus probables et buts attendus avec l'offre Premium.</p><a class="button" href="/#offres">Voir les offres</a></div>"""
    return layout(title, desc, body, f"/match/{slug}",
                  f'<script type="application/ld+json">{jsonld}</script>')


def matches_page() -> str:
    data = load()
    by_league: dict = {}
    for m in data["matches"]:
        by_league.setdefault(m["league_name"], []).append(m)
    sections = "".join(
        f"<h2>{e(lg)}</h2><ul class='match-list'>" + "".join(
            f"<li><a href='/match/{match_slug(m)}'>{e(m['home'])} – {e(m['away'])}</a>"
            f" <span class='muted'>{fr_date(m['date'])} · {pct(max(m['probs'].values()))} pour l'issue la plus probable</span></li>"
            for m in ms) + "</ul>"
        for lg, ms in sorted(by_league.items()))
    body = f"<h1>Probabilités des prochains matchs</h1><p class='muted'>10 championnats européens, mis à jour plusieurs fois par jour.</p>{sections or '<p>Aucun match programmé.</p>'}"
    return layout("Probabilités des prochains matchs de football", "Probabilités de victoire, de nul et cotes justes pour les prochains matchs de 10 championnats européens.", body, "/matchs")


def legal_page(name: str) -> str | None:
    if name not in LEGAL_PAGES:
        return None
    body = (LEGAL / f"{name}.html").read_text()
    return layout(f"{LEGAL_PAGES[name]} – Paris IA", LEGAL_PAGES[name], body, f"/{name}")


def sitemap() -> str:
    urls = ["/", "/matchs"] + [f"/match/{match_slug(m)}" for m in load()["matches"]] + [f"/{k}" for k in LEGAL_PAGES]
    items = "".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'


def robots() -> str:
    if not INDEXABLE:
        return "User-agent: *\nDisallow: /\n"
    return f"User-agent: *\nDisallow: /api/\nSitemap: {SITE_URL}/sitemap.xml\n"
