"""API + site : comptes, abonnements Stripe et accès aux pronostics selon l'offre."""
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import sqlite3
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "app.sqlite"
SECRET = os.environ.get("APP_SECRET", "dev-secret-a-changer").encode()
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")
STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
PRICES = {"premium": os.environ.get("STRIPE_PRICE_PREMIUM"), "pro": os.environ.get("STRIPE_PRICE_PRO")}
PLANS = {"free": 0, "premium": 1, "pro": 2}

app = FastAPI(title="Paris IA")


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""create table if not exists users (
        id integer primary key, email text unique not null, salt text not null, pw text not null,
        plan text not null default 'free', stripe_customer text, created integer not null)""")
    return con


def hash_pw(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()


def sign(uid: int) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"uid": uid, "t": int(time.time())}).encode()).decode()
    return body + "." + hmac.new(SECRET, body.encode(), "sha256").hexdigest()


def current_user(request: Request):
    token = request.cookies.get("session", "")
    body, _, sig = token.partition(".")
    if not body or not hmac.compare_digest(sig, hmac.new(SECRET, body.encode(), "sha256").hexdigest()):
        return None
    uid = json.loads(base64.urlsafe_b64decode(body))["uid"]
    with db() as con:
        return con.execute("select * from users where id = ?", (uid,)).fetchone()


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
        with db() as con:
            uid = con.execute("insert into users (email, salt, pw, created) values (?, ?, ?, ?)",
                              (c.email.lower(), salt, hash_pw(c.password, salt), int(time.time()))).lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Un compte existe déjà avec cet email.")
    response.set_cookie("session", sign(uid), httponly=True, samesite="lax", max_age=30 * 86400)
    return {"ok": True}


@app.post("/api/login")
def login(c: Credentials, response: Response):
    with db() as con:
        u = con.execute("select * from users where email = ?", (c.email.lower(),)).fetchone()
    if not u or not hmac.compare_digest(u["pw"], hash_pw(c.password, u["salt"])):
        raise HTTPException(401, "Identifiants incorrects.")
    response.set_cookie("session", sign(u["id"]), httponly=True, samesite="lax", max_age=30 * 86400)
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    u = current_user(request)
    return {"email": u["email"] if u else None, "plan": u["plan"] if u else "free",
            "stripe": bool(STRIPE_KEY)}


@app.get("/api/matches")
def matches(request: Request):
    """Gratuit : probabilités 1X2. Premium/Pro : tous les marchés et les value bets."""
    path = DATA / "predictions.json"
    if not path.exists():
        return {"generated": None, "matches": [], "plan": plan_of(request)}
    payload = json.loads(path.read_text())
    plan = plan_of(request)
    if PLANS[plan] < PLANS["premium"]:
        keep = {"league", "league_name", "date", "time", "home", "away", "probs"}
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


@app.post("/api/checkout/{plan}")
def checkout(plan: str, request: Request):
    u = current_user(request)
    if not u:
        raise HTTPException(401, "Connecte-toi d'abord.")
    if plan not in ("premium", "pro"):
        raise HTTPException(404)
    if not STRIPE_KEY or not PRICES[plan]:
        # Mode démo : pas de clés Stripe, l'offre est activée directement.
        with db() as con:
            con.execute("update users set plan = ? where id = ?", (plan, u["id"]))
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
    with db() as con:
        if event["type"] == "checkout.session.completed":
            con.execute("update users set plan = ?, stripe_customer = ? where id = ?",
                        (obj["metadata"]["plan"], obj["customer"], int(obj["client_reference_id"])))
        elif event["type"] == "customer.subscription.deleted":
            con.execute("update users set plan = 'free' where stripe_customer = ?", (obj["customer"],))
    return {"ok": True}


app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")
