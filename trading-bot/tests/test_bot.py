import numpy as np
import pandas as pd

from bot.backtest import resample, run_backtest
from bot.config import Config
from bot.strategy import add_indicators, min_candles, target_in_market

cfg = Config(ema_fast=12, ema_slow=26)


def synthetic(n=1500, seed=1, drift=0.0002):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0, 0.005, n)) * close
    ts = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({"ts": ts, "open": open_, "close": close,
                         "high": np.maximum(open_, close) + spread,
                         "low": np.minimum(open_, close) - spread, "volume": 1.0})


def test_trend_detection():
    up = synthetic(drift=0.01)
    down = synthetic(drift=-0.01)
    assert target_in_market(up, cfg) is True
    assert target_in_market(down, cfg) is False
    assert target_in_market(up.iloc[: min_candles(cfg) - 1], cfg) is None


def test_no_lookahead():
    """Le signal d'une bougie ne doit pas dépendre des bougies suivantes."""
    df = synthetic()
    full = add_indicators(df, cfg)["uptrend"]
    part = add_indicators(df.iloc[:800], cfg)["uptrend"]
    assert (full.iloc[:800] == part).all()


def test_backtest_runs():
    res = run_backtest(synthetic(), cfg)
    assert res["trades"] > 0
    assert res["capital_final"] > 0
    assert res["pire_chute_bot_pct"] <= 0


def test_position_pct_limits_exposure():
    crash = synthetic(drift=0.002).copy()
    crash.loc[1200:, ["open", "high", "low", "close"]] *= 0.5  # krach soudain de -50 %
    half = run_backtest(crash, Config(ema_fast=12, ema_slow=26, position_pct=50))
    full = run_backtest(crash, Config(ema_fast=12, ema_slow=26, position_pct=100))
    assert half["pire_chute_bot_pct"] > full["pire_chute_bot_pct"]


def test_resample():
    df = synthetic(48)
    df["ts"] = (df["ts"] - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)
    assert len(resample(df, "1d")) == 8


class FakeExchange:
    """Imite une plateforme CCXT : rejoue des bougies synthétiques."""
    def __init__(self, df):
        self.df, self.i = df, 200

    def market(self, symbol):
        return {"base": "BTC", "quote": "EUR", "limits": {"amount": {"min": 0}, "cost": {"min": 1}}}

    def fetch_ticker(self, symbol):
        return {"last": float(self.df["close"].iloc[self.i - 1])}

    def fetch_ohlcv(self, symbol, tf, limit=720):
        d = self.df.iloc[max(0, self.i - limit):self.i]
        return [[int(r.ts.timestamp() * 1000), r.open, r.high, r.low, r.close, r.volume] for r in d.itertuples()]


def test_paper_bot_loop(tmp_path, monkeypatch):
    import bot.main as m
    monkeypatch.chdir(tmp_path)
    fake = FakeExchange(synthetic())
    monkeypatch.setattr(m, "make_exchange", lambda cfg, authenticated: fake)
    b = m.Bot(cfg)
    for _ in range(1200):
        fake.i += 1
        b.step()
        b.step()  # même bougie : ne doit rien refaire
        m.save_state(b.state)
    assert b.state["trades"], "le bot aurait dû trader"
    p = b.state["paper"]
    assert p["quote"] >= 0 and p["base"] >= 0
    if b.state["position"]:
        assert abs(b.state["position"]["qty"] - p["base"]) < 1e-9
    else:
        assert p["base"] < 1e-9
