import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bot  # noqa: E402
from strategy import backtest, signal  # noqa: E402


def serie(valeurs):
    debut = date.today() - timedelta(days=len(valeurs) + 1)
    return pd.Series(valeurs, index=[debut + timedelta(days=i) for i in range(len(valeurs))], dtype=float)


HAUSSE = serie(np.linspace(100, 200, 120))
BAISSE = serie(np.linspace(200, 100, 120))


class FausseApi:
    live = False

    def __init__(self, closes, positions=None, equity=10000, last_equity=10000, cash=10000):
        self.closes, self.positions = closes, positions or {}
        self.cpt = {"equity": str(equity), "last_equity": str(last_equity), "cash": str(cash)}
        self.ordres = []

    def compte(self): return self.cpt
    def marche_ouvert(self): return True
    def position(self, s): return self.positions.get(s)
    def clotures(self, s, jours): return self.closes[s]
    def acheter(self, s, montant): self.ordres.append(("achat", s, round(montant, 2)))
    def fermer(self, s): self.ordres.append(("vente", s))


def test_signal():
    assert signal(HAUSSE, 20, 50)
    assert not signal(BAISSE, 20, 50)
    assert not signal(HAUSSE[:30], 20, 50)  # pas assez d'historique


def test_achete_en_tendance_haussiere_et_respecte_la_taille():
    api = FausseApi({"SPY": HAUSSE, "QQQ": BAISSE})
    bot.executer(api)
    assert api.ordres == [("achat", "SPY", 2500.0)]


def test_vend_quand_la_tendance_se_retourne():
    api = FausseApi({"SPY": BAISSE, "QQQ": BAISSE}, positions={"SPY": {"market_value": "3000"}})
    bot.executer(api)
    assert api.ordres == [("vente", "SPY")]


def test_bloque_les_achats_apres_grosse_perte():
    api = FausseApi({"SPY": HAUSSE, "QQQ": HAUSSE}, equity=9500, last_equity=10000)
    bot.executer(api)
    assert api.ordres == []


def test_limite_au_cash_disponible():
    api = FausseApi({"SPY": HAUSSE, "QQQ": HAUSSE}, cash=3000)
    bot.executer(api)
    assert api.ordres == [("achat", "SPY", 2500.0), ("achat", "QQQ", 500.0)]


def test_simulation_n_envoie_rien():
    api = FausseApi({"SPY": HAUSSE, "QQQ": HAUSSE})
    bot.executer(api, simul=True)
    assert api.ordres == []


def test_backtest():
    r = backtest(HAUSSE, 20, 50)
    assert r["nb_trades"] == 1 and r["rendement_strategie"] > 0
