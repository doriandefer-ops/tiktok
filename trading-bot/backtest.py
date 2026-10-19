"""Teste la stratégie sur l'historique avant de la laisser trader.

    python backtest.py            # 5 ans sur les symboles de config.py
    python backtest.py --ans 10
"""
import argparse

import config
from alpaca import Alpaca
from strategy import backtest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ans", type=int, default=5)
    args = parser.parse_args()
    api = Alpaca()
    for symbole in config.SYMBOLES:
        closes = api.clotures(symbole, jours=args.ans * 365)
        r = backtest(closes, config.SMA_COURTE, config.SMA_LONGUE)
        print(f"\n{symbole} ({closes.index[0]} → {closes.index[-1]})")
        print(f"  Stratégie   : {r['rendement_strategie']:+.1%}  (pire baisse {r['pire_baisse_strategie']:.1%})")
        print(f"  Buy & hold  : {r['rendement_buy_hold']:+.1%}  (pire baisse {r['pire_baisse_buy_hold']:.1%})")
        print(f"  {r['nb_trades']} trades, investi {r['temps_investi']:.0%} du temps")


if __name__ == "__main__":
    main()
