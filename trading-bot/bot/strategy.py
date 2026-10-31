"""Stratégie : croisement de moyennes mobiles exponentielles + filtre RSI.

- Entrée (achat) : l'EMA rapide croise au-dessus de l'EMA lente,
  le prix est au-dessus de l'EMA lente et le RSI n'est pas en surachat.
- Sortie : stop-loss / take-profit basés sur l'ATR (gérés par le bot),
  ou croisement baissier des EMA.

Les signaux sont calculés uniquement sur des bougies CLÔTURÉES.
"""
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-12)
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def add_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = ema(df["close"], cfg.ema_fast)
    df["ema_slow"] = ema(df["close"], cfg.ema_slow)
    df["rsi"] = rsi(df["close"], cfg.rsi_period)
    df["atr"] = atr(df, cfg.atr_period)
    above = df["ema_fast"] > df["ema_slow"]
    df["cross_up"] = above & ~above.shift(1, fill_value=False)
    df["cross_down"] = ~above & above.shift(1, fill_value=False)
    return df


def signal(df: pd.DataFrame, cfg) -> str:
    """Renvoie 'buy', 'sell' ou 'hold' pour la dernière bougie de df."""
    min_len = max(cfg.ema_slow, cfg.rsi_period, cfg.atr_period) * 3
    if len(df) < min_len:
        return "hold"
    row = add_indicators(df, cfg).iloc[-1]
    return row_signal(row, cfg)


def row_signal(row, cfg) -> str:
    if row["cross_up"] and row["close"] > row["ema_slow"] and row["rsi"] < cfg.rsi_max_entry:
        return "buy"
    if row["cross_down"]:
        return "sell"
    return "hold"
