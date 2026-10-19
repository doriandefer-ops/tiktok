"""Réglages du bot. Modifie ici, pas dans le code."""
import os

SYMBOLES = os.environ.get("SYMBOLES", "SPY,QQQ").split(",")  # ETF S&P 500 et Nasdaq 100
SMA_COURTE = 20                  # jours
SMA_LONGUE = 50                  # jours
PART_PAR_POSITION = 0.25         # 25 % du capital max par symbole
PERTE_MAX_JOUR = 0.03            # si le compte perd 3 % sur la journée : plus aucun achat
CAPITAL_MAX_USD = float(os.environ.get("CAPITAL_MAX_USD", "100000"))  # plafond total engagé
