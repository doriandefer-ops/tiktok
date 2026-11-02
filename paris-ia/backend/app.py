"""API + site : comptes, abonnements Stripe et accès aux pronostics selon l'offre."""
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import threading
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, Response as RawResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import pages

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SECRET = os.environ.get("APP_SECRET", "dev-secret-a-changer").encode()
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")
STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
PRICES = {"premium": os.environ.get("STRIPE_PRICE_PREMIUM"), "pro": os.environ.get("STRIPE_PRICE_PRO")}
PLANS = {"free": 0, "premium": 1, "pro": 2}
REFRESH_HOURS = float(os.environ.get("REFRESH_HOURS", "0"))
SECURE_COOKIE = SITE_URL.startswith("https://")

app = FastAPI(title="Paris IA")


def refresh_loop():
    """Retélécharge résultats et cotes puis recalcule les probabilités toutes les REFRESH_HOURS heures."""
    import predict
    while True:
        try:
            predict.run()
        except Exception as e:
            print(f"Mise à jour impossible : {e}", flush=True)
        time.sleep(REFRESH_HOURS * 3600)


@app.on_event("startup")
def start_refresh():
    db.init()
    if REFRESH_HOURS > 0:
        threading.Thread(target=refresh_loop, daemon=True).start()


def hash_pw(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()


def sign(uid: int) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"uid": uid, "t": int(time.time())}).encode()).decode()
    return body + "." + hmac.new(SECRET, body.encode(), "sha256").hexdigest()


def current_user(request: Request):
    token = request.cookies.get("session", "")
    body, _, sig = token.partition(".")
    if not body or not hmac.compare_digest(sig.encode(), hmac.new(SECRET, body.encode(), "sha256").hexdigest().encode()):
        return None
    uid = json.loads(base64.urlsafe_b64decode(body))["uid"]
    return db.one("select * from users where id = ?", (uid,))


def plan_of(request: Request) -> str:
    user = current_user(request)
    return user["plan"] if user else "free"


class Credentials(BaseModel):
    email: str
    password: str
    adult: bool = False


@app.post("/api/signup")
def signup(c: Credentials, response: Response):
    if not c.adult:
        raise HTTPException(400, "Le service est réservé aux personnes majeures.")
    if "@" not in c.email or len(c.password) < 8:
        raise HTTPException(400, "Email invalide ou mot de passe trop court (8 caractères minimum).")
    salt = secrets.token_hex(16)
    try:
        uid = db.insert("insert into users (email, salt, pw, created) values (?, ?, ?, ?)",
                        (c.email.lower(), salt, hash_pw(c.password, salt), int(time.time())))
    except db.Duplicate:
        raise HTTPException(400, "Un compte existe déjà avec cet email.")
    response.set_cookie("session", sign(uid), httponly=True, samesite="lax", secure=SECURE_COOKIE, max_age=30 * 86400)
    return {"ok": True}


@app.post("/api/login")
def login(c: Credentials, response: Response):
    u = db.one("select * from users where email = ?", (c.email.lower(),))
    if not u or not hmac.compare_digest(u["pw"], hash_pw(c.password, u["salt"])):
        raise HTTPException(401, "Identifiants incorrects.")
    response.set_cookie("session", sign(u["id"]), httponly=True, samesite="lax", secure=SECURE_COOKIE, max_age=30 * 86400)
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    u = current_user(request)
    return {"email": u["email"] if u else None, "plan": u["plan"] if u else "free",
            "stripe": bool(STRIPE_KEY and all(PRICES.values()))}


@app.get("/api/matches")
def matches(request: Request):
    """Gratuit : probabilités 1X2. Premium/Pro : tous les marchés et les value bets."""
    path = DATA / "predictions.json"
    if not path.exists():
        return {"generated": None, "matches": [], "plan": plan_of(request)}
    payload = json.loads(path.read_text())
    for m in payload["matches"]:
        m["slug"] = pages.match_slug(m)
    plan = plan_of(request)
    if PLANS[plan] < PLANS["premium"]:
        keep = {"league", "league_name", "date", "time", "home", "away", "probs", "slug"}
        payload["matches"] = [{k: v for k, v in m.items() if k in keep} | {"locked": True}
                              for m in payload["matches"]]
    payload["plan"] = plan
    return payload


@app.get("/api/track-record")
def track_record(request: Request):
    """Historique public : le bilan, gagnant ou perdant, est visible par tous."""
    summary = json.loads((DATA / "backtest.json").read_text()) if (DATA / "backtest.json").exists() else {}
    history = json.loads((DATA / "history.json").read_text()) if (DATA / "history.json").exists() else []
    picks = [h for h in history if h["pick"]]
    limit = None if PLANS[plan_of(request)] >= PLANS["pro"] else 30
    recent = sorted(picks, key=lambda h: h["date"], reverse=True)[:limit]
    return {"summary": summary, "picks": recent}


class Subscription(BaseModel):
    email: str
    consent: bool = False


@app.post("/api/newsletter")
def newsletter(s: Subscription):
    if not s.consent:
        raise HTTPException(400, "Coche la case pour accepter de recevoir la newsletter.")
    if "@" not in s.email or len(s.email) > 254:
        raise HTTPException(400, "Email invalide.")
    try:
        db.insert("insert into newsletter (email, created, source) values (?, ?, ?)",
                  (s.email.strip().lower(), int(time.time()), "site"))
    except db.Duplicate:
        pass  # déjà inscrit : même réponse, pour ne pas révéler qui est inscrit
    return {"ok": True}


@app.post("/api/checkout/{plan}")
def checkout(plan: str, request: Request):
    u = current_user(request)
    if not u:
        raise HTTPException(401, "Connecte-toi d'abord.")
    if plan not in ("premium", "pro"):
        raise HTTPException(404)
    if not STRIPE_KEY or not PRICES[plan]:
        # Mode démo : pas de clés Stripe, l'offre est activée directement.
        db.run("update users set plan = ? where id = ?", (plan, u["id"]))
        return {"url": "/?demo=1"}
    import stripe
    stripe.api_key = STRIPE_KEY
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": PRICES[plan], "quantity": 1}],
        customer_email=u["email"],
        client_reference_id=str(u["id"]),
        metadata={"plan": plan},
        success_url=f"{SITE_URL}/?paid=1",
        cancel_url=f"{SITE_URL}/#offres",
    )
    return {"url": session.url}


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    import stripe
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""),
                                               STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Signature invalide")
    obj = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        db.run("update users set plan = ?, stripe_customer = ? where id = ?",
               (obj["metadata"]["plan"], obj["customer"], int(obj["client_reference_id"])))
    elif event["type"] == "customer.subscription.deleted":
        db.run("update users set plan = 'free' where stripe_customer = ?", (obj["customer"],))
    return {"ok": True}


app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    page = (ROOT / "frontend" / "index.html").read_text()
    return page.replace("noindex, nofollow", "index, follow") if pages.INDEXABLE else page


@app.get("/matchs", response_class=HTMLResponse)
def matches_list():
    return pages.matches_page()


@app.get("/match/{slug}", response_class=HTMLResponse)
def match(slug: str):
    page = pages.match_page(slug)
    if page is None:
        raise HTTPException(404, "Match introuvable ou déjà joué.")
    return page


@app.get("/sitemap.xml")
def sitemap():
    return RawResponse(pages.sitemap(), media_type="application/xml")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return pages.robots()


@app.get("/{name}", response_class=HTMLResponse)
def legal(name: str):
    page = pages.legal_page(name)
    if page is None:
        raise HTTPException(404)
    return page
