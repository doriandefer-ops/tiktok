"""Gestion du risque : taille de position, stop-loss, take-profit."""


def position_size(equity: float, entry: float, stop: float, cfg) -> float:
    """Quantité à acheter pour ne perdre que RISK_PER_TRADE_PCT si le stop est touché,
    plafonnée à MAX_POSITION_PCT du capital."""
    risk_per_unit = entry - stop
    if risk_per_unit <= 0 or entry <= 0:
        return 0.0
    qty_risk = equity * cfg.risk_per_trade_pct / 100 / risk_per_unit
    qty_cap = equity * cfg.max_position_pct / 100 / entry
    return max(0.0, min(qty_risk, qty_cap))


def stop_and_target(entry: float, atr_value: float, cfg) -> tuple[float, float]:
    stop = entry - cfg.stop_atr_mult * atr_value
    target = entry + cfg.take_profit_atr_mult * atr_value
    return stop, target


def daily_loss_exceeded(day_start_equity: float, equity: float, cfg) -> bool:
    if day_start_equity <= 0:
        return False
    loss_pct = (day_start_equity - equity) / day_start_equity * 100
    return loss_pct >= cfg.max_daily_loss_pct
