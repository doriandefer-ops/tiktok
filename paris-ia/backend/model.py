"""Modèle Dixon-Coles (Poisson bivarié corrigé, pondéré dans le temps) par championnat."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson

XI = 0.0019     # décroissance temporelle par jour (demi-vie ~ 1 an)
SHOTS = 0.7     # part des tirs cadrés dans la cible (réglée par backtest, voir README)
L2 = 0.05       # régularisation : stabilise les promus et les équipes peu vues
MAX_GOALS = 10


@dataclass
class Fit:
    teams: list
    attack: np.ndarray
    defence: np.ndarray
    home: float
    rho: float

    def rates(self, home_team: str, away_team: str):
        idx = {t: i for i, t in enumerate(self.teams)}
        # Équipe inconnue (promue sans historique) : niveau légèrement sous la moyenne.
        ah, dh = (self.attack[idx[home_team]], self.defence[idx[home_team]]) if home_team in idx else (-0.15, 0.15)
        aa, da = (self.attack[idx[away_team]], self.defence[idx[away_team]]) if away_team in idx else (-0.15, 0.15)
        return np.exp(self.home + ah + da), np.exp(aa + dh)

    def score_matrix(self, home_team: str, away_team: str) -> np.ndarray:
        lam, mu = self.rates(home_team, away_team)
        g = np.arange(MAX_GOALS + 1)
        m = np.outer(poisson.pmf(g, lam), poisson.pmf(g, mu))
        r = self.rho
        m[0, 0] *= 1 - lam * mu * r
        m[0, 1] *= 1 + lam * r
        m[1, 0] *= 1 + mu * r
        m[1, 1] *= 1 - r
        return m / m.sum()


def fit(matches: pd.DataFrame, as_of: pd.Timestamp, shots: float = SHOTS, xi: float = XI) -> Fit:
    """Ajuste le modèle sur les matchs joués avant `as_of`.

    `shots` = part de la cible venant des tirs cadrés (buts attendus approchés) plutôt que des buts :
    les tirs cadrés mesurent mieux le niveau réel, les buts dépendent beaucoup du hasard."""
    df = matches[matches["Date"] < as_of]
    teams = sorted(set(df["HomeTeam"]) | set(df["AwayTeam"]))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    h = df["HomeTeam"].map(idx).to_numpy()
    a = df["AwayTeam"].map(idx).to_numpy()
    gx = df["FTHG"].to_numpy(float)
    gy = df["FTAG"].to_numpy(float)
    w = np.exp(-xi * (as_of - df["Date"]).dt.days.to_numpy(float))
    sx = df["HST"].to_numpy(float) if "HST" in df else np.full_like(gx, np.nan)
    sy = df["AST"].to_numpy(float) if "AST" in df else np.full_like(gy, np.nan)
    ok = ~(np.isnan(sx) | np.isnan(sy))
    conv = (gx[ok].sum() + gy[ok].sum()) / max(sx[ok].sum() + sy[ok].sum(), 1)
    x = np.where(ok, (1 - shots) * gx + shots * conv * np.nan_to_num(sx), gx)
    y = np.where(ok, (1 - shots) * gy + shots * conv * np.nan_to_num(sy), gy)

    def nll(p):
        att, dfn, home = p[:n], p[n:2 * n], p[2 * n]
        ll_h = home + att[h] + dfn[a]
        ll_a = att[a] + dfn[h]
        lam, mu = np.exp(ll_h), np.exp(ll_a)
        f = -np.sum(w * (x * ll_h - lam + y * ll_a - mu)) + L2 * (att @ att + dfn @ dfn)
        rh, ra = w * (x - lam), w * (y - mu)
        g_att = -(np.bincount(h, rh, n) + np.bincount(a, ra, n)) + 2 * L2 * att
        g_def = -(np.bincount(a, rh, n) + np.bincount(h, ra, n)) + 2 * L2 * dfn
        return f, np.concatenate([g_att, g_def, [-rh.sum()]])

    res = minimize(nll, np.zeros(2 * n + 1), jac=True, method="L-BFGS-B")
    att, dfn, home = res.x[:n], res.x[n:2 * n], res.x[2 * n]
    att = att - att.mean()
    dfn = dfn + (res.x[:n].mean())  # conserve les taux attendus après recentrage

    lam = np.exp(home + att[h] + dfn[a])
    mu = np.exp(att[a] + dfn[h])
    x, y = gx, gy  # la corrélation des petits scores s'estime sur les vrais scores

    def rho_nll(r):
        tau = np.ones_like(lam)
        m00, m01, m10, m11 = (x == 0) & (y == 0), (x == 0) & (y == 1), (x == 1) & (y == 0), (x == 1) & (y == 1)
        tau[m00] = 1 - lam[m00] * mu[m00] * r
        tau[m01] = 1 + lam[m01] * r
        tau[m10] = 1 + mu[m10] * r
        tau[m11] = 1 - r
        return -np.sum(w * np.log(np.clip(tau, 1e-10, None)))

    rho = minimize_scalar(rho_nll, bounds=(-0.2, 0.2), method="bounded").x
    return Fit(teams, att, dfn, home, rho)


def markets(m: np.ndarray) -> dict:
    """Probabilités des principaux marchés à partir de la matrice des scores."""
    g = np.arange(m.shape[0])
    total = g[:, None] + g[None, :]
    top = np.dstack(np.unravel_index(np.argsort(m, axis=None)[::-1][:3], m.shape))[0]
    return {
        "home": float(np.tril(m, -1).sum()),
        "draw": float(np.trace(m)),
        "away": float(np.triu(m, 1).sum()),
        "over25": float(m[total > 2.5].sum()),
        "btts": float(m[1:, 1:].sum()),
        "xg_home": float((m.sum(1) * g).sum()),
        "xg_away": float((m.sum(0) * g).sum()),
        "scores": [{"score": f"{i}-{j}", "p": float(m[i, j])} for i, j in top],
    }
