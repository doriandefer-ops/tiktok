"""Bot de trading : à lancer une fois par jour pendant les heures de marché US.

    python bot.py            # passe les ordres (compte paper par défaut)
    python bot.py --simul    # affiche ce qu'il ferait, sans rien envoyer
"""
import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from alpaca import Alpaca
from strategy import signal

log = logging.getLogger("bot")


def executer(api, simul=False):
    mode = "RÉEL" if api.live else "PAPER"
    compte = api.compte()
    if compte.get("trading_blocked") or compte.get("account_blocked"):
        log.error("Compte bloqué par Alpaca, arrêt.")
        return
    capital = float(compte["equity"])
    veille = float(compte["last_equity"])
    cash = float(compte["cash"])
    variation = capital / veille - 1 if veille else 0.0
    log.info("Compte %s : capital %.2f $, cash %.2f $, variation du jour %+.2f %%", mode, capital, cash, variation * 100)

    if not simul and not api.marche_ouvert():
        log.info("Marché fermé, rien à faire.")
        return
    achats_bloques = variation <= -config.PERTE_MAX_JOUR
    if achats_bloques:
        log.warning("Perte du jour > %.0f %% : aucun nouvel achat aujourd'hui.", config.PERTE_MAX_JOUR * 100)

    aujourd_hui = datetime.now(ZoneInfo("America/New_York")).date()
    engage = sum(float(p["market_value"]) for p in filter(None, (api.position(s) for s in config.SYMBOLES)))

    for symbole in config.SYMBOLES:
        closes = api.clotures(symbole, jours=config.SMA_LONGUE * 3)
        closes = closes[closes.index < aujourd_hui]  # seulement des journées terminées
        acheter = signal(closes, config.SMA_COURTE, config.SMA_LONGUE)
        pos = api.position(symbole)
        log.info("%s : dernière clôture %.2f, signal %s, position %s", symbole,
                 closes.iloc[-1] if len(closes) else float("nan"),
                 "ACHAT" if acheter else "À PLAT", f"{float(pos['market_value']):.2f} $" if pos else "aucune")

        if pos and not acheter:
            log.info("→ Vente de toute la position %s", symbole)
            if not simul:
                api.fermer(symbole)
            engage -= float(pos["market_value"])
        elif acheter and not pos and not achats_bloques:
            montant = min(capital * config.PART_PAR_POSITION, cash, config.CAPITAL_MAX_USD - engage)
            if montant < 1:
                log.info("→ Signal d'achat %s mais pas assez de budget disponible", symbole)
                continue
            log.info("→ Achat %s pour %.2f $", symbole, montant)
            if not simul:
                api.acheter(symbole, montant)
            cash -= montant
            engage += montant


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--simul", action="store_true", help="n'envoie aucun ordre")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executer(Alpaca(), simul=args.simul)


if __name__ == "__main__":
    main()
