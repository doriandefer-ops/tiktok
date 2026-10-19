"""Stratégie : croisement de moyennes mobiles (tendance) sur bougies journalières.

On est acheté quand la moyenne courte est au-dessus de la longue, sinon on est à plat.
Pas de vente à découvert, pas d'effet de levier.
"""
import pandas as pd


def signal(closes: pd.Series, court: int, long: int) -> bool:
    """True = on doit être acheté, False = on doit être à plat."""
    if len(closes) < long:
        return False
    return closes.rolling(court).mean().iloc[-1] > closes.rolling(long).mean().iloc[-1]


def positions_historiques(closes: pd.Series, court: int, long: int) -> pd.Series:
    """Position (1 ou 0) à la clôture de chaque jour, utilisée par le backtest."""
    sma_c = closes.rolling(court).mean()
    sma_l = closes.rolling(long).mean()
    return (sma_c > sma_l).astype(int).where(sma_l.notna(), 0)


def backtest(closes: pd.Series, court: int, long: int, frais: float = 0.0005) -> dict:
    """Simule la stratégie : le signal de la veille décide de la position du jour."""
    rendements = closes.pct_change().fillna(0)
    pos = positions_historiques(closes, court, long).shift(1).fillna(0)
    changements = pos.diff().abs().fillna(pos.iloc[0])
    strat = pos * rendements - changements * frais
    courbe = (1 + strat).cumprod()
    buy_hold = (1 + rendements).cumprod()
    return {
        "rendement_strategie": courbe.iloc[-1] - 1,
        "rendement_buy_hold": buy_hold.iloc[-1] - 1,
        "pire_baisse_strategie": (courbe / courbe.cummax() - 1).min(),
        "pire_baisse_buy_hold": (buy_hold / buy_hold.cummax() - 1).min(),
        "nb_trades": int(changements.astype(bool).sum()),
        "temps_investi": pos.mean(),
    }
