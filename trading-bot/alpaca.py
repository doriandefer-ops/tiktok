"""Petit client pour l'API REST d'Alpaca (compte, ordres, cours)."""
import os
from datetime import date, timedelta

import pandas as pd
import requests

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"


class Alpaca:
    def __init__(self):
        key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise SystemExit("ALPACA_API_KEY et ALPACA_SECRET_KEY doivent être définies (voir .env.example).")
        # Argent réel uniquement si on le demande explicitement.
        self.live = os.environ.get("ALPACA_LIVE", "").lower() == "oui"
        self.base = LIVE_URL if self.live else PAPER_URL
        self.session = requests.Session()
        self.session.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})

    def _req(self, methode, url, **kw):
        r = self.session.request(methode, url, timeout=20, **kw)
        r.raise_for_status()
        return r.json() if r.content else None

    def compte(self):
        return self._req("GET", f"{self.base}/v2/account")

    def marche_ouvert(self) -> bool:
        return self._req("GET", f"{self.base}/v2/clock")["is_open"]

    def position(self, symbole):
        """Renvoie la position ouverte sur ce symbole, ou None."""
        try:
            return self._req("GET", f"{self.base}/v2/positions/{symbole}")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    def acheter(self, symbole, montant_usd):
        return self._req("POST", f"{self.base}/v2/orders", json={
            "symbol": symbole, "notional": f"{montant_usd:.2f}",
            "side": "buy", "type": "market", "time_in_force": "day",
        })

    def fermer(self, symbole):
        return self._req("DELETE", f"{self.base}/v2/positions/{symbole}")

    def clotures(self, symbole, jours) -> pd.Series:
        """Clôtures journalières (ajustées des dividendes/splits), du plus ancien au plus récent."""
        params = {
            "timeframe": "1Day", "adjustment": "all", "feed": "iex", "limit": 10000,
            "start": (date.today() - timedelta(days=jours)).isoformat(),
        }
        bougies = []
        while True:
            data = self._req("GET", f"{DATA_URL}/v2/stocks/{symbole}/bars", params=params)
            bougies += data.get("bars") or []
            if not data.get("next_page_token"):
                break
            params["page_token"] = data["next_page_token"]
        if not bougies:
            return pd.Series(dtype=float)
        s = pd.Series({pd.Timestamp(b["t"]).date(): b["c"] for b in bougies}, dtype=float)
        return s.sort_index()
