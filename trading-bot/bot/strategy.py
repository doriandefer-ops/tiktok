"""Stratégie : suivi de tendance par moyennes mobiles exponentielles.

- Tendance haussière (EMA rapide > EMA lente) : on est investi.
- Tendance baissière (EMA rapide < EMA lente) : on est en liquide.

Pas de take-profit : on laisse courir les gains tant que la tendance dure.
Le but n'est pas de gagner chaque trade (beaucoup de petites pertes),
mais de capter les grosses hausses et d'éviter une partie des grosses baisses.
Les signaux sont calculés uniquement sur des bougies CLÔTURÉES.
"""
import pandas as pd


def add_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=cfg.ema_fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=cfg.ema_slow, adjust=False).mean()
    df["uptrend"] = df["ema_fast"] > df["ema_slow"]
    return df


def min_candles(cfg) -> int:
    """Nombre de bougies nécessaires pour des moyennes fiables."""
    return cfg.ema_slow * 3


def target_in_market(df: pd.DataFrame, cfg) -> bool | None:
    """True = être investi, False = être en liquide, None = pas assez d'historique."""
    if len(df) < min_candles(cfg):
        return None
    return bool(add_indicators(df, cfg)["uptrend"].iloc[-1])
