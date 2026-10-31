# Bot de trading — suivi de tendance

Bot automatique en Python qui se connecte à ton compte via **CCXT**
(Kraken, Binance, Coinbase, Bitstamp, Bybit, OKX… plus de 100 plateformes crypto).
Configuré par défaut pour **Kraken, BTC/EUR, bougies de 4h**.

> ⚠️ Le trading comporte un risque de perte en capital. Les résultats passés ne garantissent
> pas les résultats futurs. Le bot démarre en **mode simulation** (`MODE=paper`).

## La stratégie

- Tendance haussière (moyenne 12 jours > moyenne 26 jours) → le bot investit `POSITION_PCT` % du capital.
- Tendance baissière → le bot revend tout et reste en euros.
- Pas d'objectif de gain : on laisse courir les hausses. Beaucoup de petites pertes,
  quelques gros gains. Seulement ~1 trade par mois en moyenne.

Le but : capter une bonne partie des hausses et **éviter une grande partie des krachs**.

### Backtest BTC/EUR (mars 2021 → sept. 2026, frais inclus)

| Réglage | Gain bot | Gain achat simple | Pire chute bot | Pire chute achat simple |
|---|---|---|---|---|
| 50 % investi (défaut) | +77 % | +50 % | **−30 %** | −74 % |
| 100 % investi | +153 % | +50 % | −50 % | −74 % |

Limites connues : lors d'une forte hausse continue (ex. 2023-2024), le bot gagne **moins** que
l'achat simple, car il n'investit qu'une partie du capital et entre en retard.
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
À chaque nouvelle session : ouvre le terminal dans le dossier et tape `.venv\Scripts\activate`.

## Utilisation

| Commande | Effet |
|---|---|
| `python -m bot.backtest` | Teste la stratégie sur 5 ans d'historique |
| `python -m bot.main` | Lance le bot (Ctrl+C pour l'arrêter) |
| `python -m bot.main --once` | Une seule vérification (test de connexion) |
| `python -m bot.main --status` | Capital, position, historique des trades |
| `python -m bot.main --close` | Vend la position maintenant |

Créer un fichier nommé `STOP` dans le dossier arrête aussi le bot.

## Passer en réel

1. Kraken → **Paramètres → API → Créer une clé**, avec uniquement : Query Funds,
   Query Open Orders & Trades, Query Closed Orders & Trades, Create & Modify Orders,
   Cancel/Close Orders. **Jamais « Withdraw Funds ».**
2. Dans `.env` : `API_KEY=`, `API_SECRET=`, puis `MODE=live`.
3. Avoir des euros sur le compte Kraken. Le bot ne vend que ce qu'il a lui-même acheté.

Le bot décide toutes les 4h, à la clôture des bougies. S'il est éteint, il ne pourra pas vendre
si la tendance se retourne : garde-le allumé, ou utilise `--close` avant une longue absence.
Ne partage jamais ton fichier `.env`.
