# Bot de trading — suivi de tendance

Bot automatique en Python qui se connecte à ton compte via **CCXT**
(Kraken, Binance, Coinbase, Bitstamp, Bybit, OKX… plus de 100 plateformes crypto).
Configuré par défaut pour **Kraken, BTC/EUR + ETH/EUR, bougies de 4h**.

> ⚠️ Le trading comporte un risque de perte en capital. Les résultats passés ne garantissent
> pas les résultats futurs. Le bot démarre en **mode simulation** (`MODE=paper`).

## La stratégie

Pour chaque crypto (BTC et ETH par défaut), indépendamment :
- Tendance haussière (moyenne 12 jours > moyenne 26 jours) → le bot y investit sa part du capital
  (`POSITION_PCT` divisé par le nombre de cryptos : 50 % → 25 % par crypto).
- Tendance baissière → le bot revend cette crypto et garde des euros.
- Pas d'objectif de gain : on laisse courir les hausses. Beaucoup de petites pertes,
  quelques gros gains. Environ 1 trade par mois et par crypto.

Le but : capter une bonne partie des hausses et **éviter une grande partie des krachs**.

### Backtest (mars 2021 → sept. 2026, frais Kraken de 0,4 % + glissement inclus)

| Cryptos | Capital max investi | Gain bot | Gain achat simple | Pire chute bot | Pire chute achat simple |
|---|---|---|---|---|---|
| BTC | 50 % | +61 % | +50 % | −31 % | −74 % |
| **BTC + ETH (défaut)** | **50 %** | **+93 %** | +52 % | **−34 %** | −77 % |
| BTC + ETH | 100 % | +201 % | +52 % | −57 % | −77 % |

Limites connues : lors d'une forte hausse continue (ex. 2023-2024), le bot gagne **moins** que
l'achat simple, car il n'investit qu'une partie du capital et entre en retard.
BTC et ETH montent et baissent souvent ensemble : la diversification reste limitée.
Environ 1 trade sur 3 est gagnant : c'est normal pour ce type de stratégie.

## Installation (Windows)

1. Ouvre le dossier `trading-bot`, tape `cmd` dans la barre d'adresse, puis Entrée.
2. Dans le terminal :
   ```
   py -V:3.13 -m venv .venv
   .venv\Scripts\activate
   python -m pip install -r requirements.txt
   copy .env.example .env
   ```
Ensuite, double-clique sur **`lancer-bot.bat`** pour démarrer le bot.
Pour les autres commandes : ouvre le terminal dans le dossier et tape d'abord `.venv\Scripts\activate`.

## Utilisation

| Commande | Effet |
|---|---|
| `python -m bot.backtest` | Teste la stratégie sur ~5 ans d'historique |
| `python -m bot.main` | Lance le bot (Ctrl+C pour l'arrêter) |
| `python -m bot.main --once` | Une seule vérification (test de connexion) |
| `python -m bot.main --status` | Capital, positions, historique des trades |
| `python -m bot.main --close` | Vend toutes les positions maintenant |

Créer un fichier nommé `STOP` dans le dossier arrête aussi le bot.

## Version scalping (simulation uniquement)

Une version « scalping » (~20 trades par jour sur bougies d'1 minute) est fournie **pour
expérimenter uniquement** : elle ne peut pas passer d'ordre réel (aucune clé API utilisée).
Capital fictif et suivi séparés du vrai bot.

| Commande | Effet |
|---|---|
| `python -m bot.scalp --backtest` | Teste sur les 3 derniers mois (bougies 1 min) |
| double-clic sur `lancer-scalping.bat` | Simulation en direct avec les vrais prix |
| `python -m bot.scalp --status` | Résultat de la simulation |

Backtest BTC/EUR, juillet → septembre 2026 (1 807 trades, ~20 par jour) :

| Frais par ordre | Résultat |
|---|---|
| 0 % (impossible en vrai) | +10 % |
| 0,25 % | **−100 %** |
| 0,4 % (Kraken, ordres au marché) | **−100 %** |

Le gain moyen par trade avant frais (~0,006 %) est 100 fois plus petit que les frais d'un aller-retour.

## Passer en réel

1. Kraken → **Paramètres → API → Créer une clé**, avec uniquement : Query Funds,
   Query Open Orders & Trades, Query Closed Orders & Trades, Create & Modify Orders,
   Cancel/Close Orders. **Jamais « Withdraw Funds ».**
2. Dans `.env` : `API_KEY=`, `API_SECRET=`, puis `MODE=live`.
3. Avoir des euros sur le compte Kraken. Le bot ne vend que ce qu'il a lui-même acheté.

Le bot décide toutes les 4h, à la clôture des bougies. S'il est éteint, il ne pourra pas vendre
si la tendance se retourne : garde-le allumé, ou utilise `--close` avant une longue absence.
Ne partage jamais ton fichier `.env`.
