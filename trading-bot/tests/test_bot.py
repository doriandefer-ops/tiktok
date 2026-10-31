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
    half = run_backtest(crash, Config(ema_fast=12, ema_slow=26, position_pct=50, symbols=("X/EUR",)))
    full = run_backtest(crash, Config(ema_fast=12, ema_slow=26, position_pct=100, symbols=("X/EUR",)))
    assert half["pire_chute_bot_pct"] > full["pire_chute_bot_pct"]


def test_portfolio_backtest():
    data = {"BTC/EUR": synthetic(seed=1), "ETH/EUR": synthetic(seed=2)}
    res = run_backtest(data, cfg)
    assert res["trades"] == res["trades_BTC/EUR"] + res["trades_ETH/EUR"] > 0


def test_resample():
    df = synthetic(48)
    df["ts"] = (df["ts"] - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)
    assert len(resample(df, "1d")) == 8


class FakeExchange:
    """Imite une plateforme CCXT : rejoue des bougies synthétiques (une série par crypto)."""
    def __init__(self, data):
        self.data, self.i = data, 200

    def market(self, symbol):
        return {"limits": {"amount": {"min": 0}, "cost": {"min": 1}}}

    def fetch_ticker(self, symbol):
        return {"last": float(self.data[symbol]["close"].iloc[self.i - 1])}

    def fetch_ohlcv(self, symbol, tf, limit=720):
        d = self.data[symbol].iloc[max(0, self.i - limit):self.i]
        return [[int(r.ts.timestamp() * 1000), r.open, r.high, r.low, r.close, r.volume] for r in d.itertuples()]


def make_bot(tmp_path, monkeypatch, data, state=None):
    import json
    import bot.main as m
    monkeypatch.chdir(tmp_path)
    if state is not None:
        (tmp_path / "state.json").write_text(json.dumps(state))
    fake = FakeExchange(data)
    monkeypatch.setattr(m, "make_exchange", lambda cfg, authenticated: fake)
    return m, fake, m.Bot(cfg)


def test_paper_bot_loop(tmp_path, monkeypatch):
    data = {"BTC/EUR": synthetic(seed=1), "ETH/EUR": synthetic(seed=2)}
    m, fake, b = make_bot(tmp_path, monkeypatch, data)
    max_invested = 0
    for _ in range(1200):
        fake.i += 1
        b.step()
        b.step()  # même bougie : ne doit rien refaire
        m.save_state(b.state)
        eq = b.equity()
        max_invested = max(max_invested, (eq - b.broker.quote_balance()) / eq)
    symbols = {t["symbol"] for t in b.state["trades"]}
    assert symbols == {"BTC/EUR", "ETH/EUR"}
    assert max_invested <= 0.6  # ~50 % à l'achat, puis varie avec les prix
    p = b.state["paper"]
    assert p["quote"] >= 0
    for s in ("BTC", "ETH"):
        held = b.positions.get(f"{s}/EUR", {}).get("qty", 0.0)
        assert abs(p["base"].get(s, 0.0) - held) < 1e-9


def test_migration_from_single_crypto_state(tmp_path, monkeypatch):
    old = {"paper": {"quote": 500.0, "base": 0.01}, "trades": [],
           "position": {"qty": 0.01, "entry": 50000, "opened_at": "x"},
           "last_candle": "2026-10-31 08:00:00+00:00"}
    data = {"BTC/EUR": synthetic(seed=1), "ETH/EUR": synthetic(seed=2)}
    m, fake, b = make_bot(tmp_path, monkeypatch, data, state=old)
    assert b.positions == {"BTC/EUR": old["position"]}
    assert b.state["paper"]["base"] == {"BTC": 0.01}
    assert b.state["last_candle"] == {}
    b.step()


def test_scalp_backtest_fees_matter():
    from bot.scalp import ScalpConfig, backtest
    df = synthetic(20000, seed=3, drift=0.0)
    free = backtest(df, ScalpConfig(fee_pct=0.0))
    paid = backtest(df, ScalpConfig(fee_pct=0.4))
    assert free["trades"] == paid["trades"] > 0
    assert paid["capital_final"] < free["capital_final"]


def test_scalp_never_uses_api_keys():
    """La version scalping ne doit jamais pouvoir passer d'ordre réel."""
    src = open("bot/scalp.py", encoding="utf-8").read()
    assert "apiKey" not in src and "create_order" not in src and "API_KEY" not in src
