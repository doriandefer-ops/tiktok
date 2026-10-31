import numpy as np
import pandas as pd

from bot.backtest import run_backtest
from bot.config import load_config
from bot.risk import daily_loss_exceeded, position_size, stop_and_target
from bot.strategy import add_indicators, rsi


def synthetic(n=1500, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n)))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0, 0.005, n)) * close
    return pd.DataFrame({"ts": range(n), "open": open_, "close": close,
                         "high": np.maximum(open_, close) + spread,
                         "low": np.minimum(open_, close) - spread, "volume": 1.0})


cfg = load_config("/nonexistent")


def test_position_size_respects_risk_and_cap():
    qty = position_size(1000, 100, 98, cfg)        # risque 1 % = 10 ; 10/2 = 5 unités = 500 > cap 25 %
    assert qty == 2.5                               # plafonné à 25 % du capital
    assert position_size(1000, 100, 100, cfg) == 0


def test_stop_target():
    stop, target = stop_and_target(100, 1, cfg)
    assert stop == 98 and target == 103


def test_daily_loss():
    assert daily_loss_exceeded(1000, 969, cfg)
    assert not daily_loss_exceeded(1000, 990, cfg)


def test_rsi_bounds():
    r = rsi(synthetic()["close"], 14).dropna()
    assert r.between(0, 100).all()


def test_crosses_alternate():
    df = add_indicators(synthetic(), cfg)
    events = df.loc[df.cross_up | df.cross_down, "cross_up"].tolist()
    assert all(a != b for a, b in zip(events, events[1:]))


def test_backtest_runs():
    res = run_backtest(synthetic(), cfg)
    assert res["trades"] > 0
    assert res["final_equity"] > 0
    assert res["max_drawdown_pct"] <= 0


class FakeExchange:
    """Imite une plateforme CCXT : rejoue des bougies synthétiques."""
    def __init__(self, df):
        self.df, self.i = df, 200

    def market(self, symbol):
        return {"base": "BTC", "quote": "USDT", "limits": {"amount": {"min": 0}, "cost": {"min": 1}}}

    def fetch_ticker(self, symbol):
        return {"last": float(self.df["close"].iloc[self.i - 1])}

    def fetch_ohlcv(self, symbol, tf, limit=300):
        d = self.df.iloc[max(0, self.i - limit):self.i]
        return [[int(r.ts) * 3_600_000, r.open, r.high, r.low, r.close, r.volume] for r in d.itertuples()]


def test_paper_bot_loop(tmp_path, monkeypatch):
    import bot.main as m
    monkeypatch.chdir(tmp_path)
    fake = FakeExchange(synthetic())
    monkeypatch.setattr(m, "make_exchange", lambda cfg, authenticated: fake)
    b = m.Bot(cfg)
    for _ in range(1000):
        fake.i += 1
        b.step()
        m.save_state(b.state)
    assert b.state["trades"], "le bot aurait dû trader"
    p = b.state["paper"]
    assert p["quote"] >= 0 and p["base"] >= -1e-12
    assert (tmp_path / "state.json").exists()
