# Bot de trading

Bot automatique en Python qui se connecte à ton compte via **CCXT**
(Binance, Kraken, Coinbase, Bybit, OKX, Bitget, KuCoin… plus de 100 plateformes crypto).

> ⚠️ **Avertissement** : le trading comporte un risque de perte en capital.
> Aucune stratégie ne garantit des gains. Ce bot démarre en **mode simulation** (`MODE=paper`) :
> teste-le plusieurs semaines avant de passer en réel, et uniquement avec de l'argent que tu peux perdre.

## Ce que fait le bot

| | |
|---|---|
| **Stratégie** | Achat quand l'EMA 12 croise au-dessus de l'EMA 26, prix au-dessus de l'EMA 26 et RSI < 70 |
| **Sorties** | Stop-loss à 2×ATR, take-profit à 3×ATR, ou croisement baissier des EMA |
| **Risque** | 1 % du capital risqué par trade, max 25 % du capital par position |
| **Sécurité** | Arrêt des nouveaux trades si −3 % sur la journée ; fichier `STOP` = arrêt d'urgence |
| **Mémoire** | Position et historique dans `state.json` (le bot reprend après un redémarrage) |
| **Journal** | `logs/bot.log` |

Spot uniquement, achat seul (pas de vente à découvert, pas de levier). Tous les paramètres
sont réglables dans `.env`.

## Installation

```bash
cd trading-bot
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # puis édite .env
```

## Étape 1 — Backtest (tester sur l'historique)

```bash
python -m bot.backtest --candles 3000
```
Compare `return_pct` à `buy_and_hold_pct` et regarde `max_drawdown_pct`.
Si la stratégie ne bat pas le simple « acheter et garder », ajuste les paramètres.

## Étape 2 — Simulation avec les vrais prix (`MODE=paper`)

```bash
python -m bot.main
```
Aucune clé API nécessaire. Laisse tourner quelques semaines.

## Étape 3 — Connexion à ton compte (`MODE=live`)

1. Sur ta plateforme : **Profil → Gestion des API → Créer une clé**.
2. Permissions : ✅ **Lecture** + ✅ **Trading spot**. ❌ **NE COCHE JAMAIS « Retrait »**.
3. Si possible, restreins la clé à l'adresse IP de la machine qui fait tourner le bot.
4. Dans `.env` : `EXCHANGE=`, `API_KEY=`, `API_SECRET=` (et `API_PASSWORD=` pour OKX/KuCoin/Bitget).
5. Optionnel mais conseillé : `SANDBOX=true` d'abord si ta plateforme a un testnet.
6. `MODE=live` puis `python -m bot.main`.

Le compte doit contenir la devise de cotation (ex. USDT pour `BTC/USDT`).
Le bot ne vend que ce qu'il a lui-même acheté.

## Commandes utiles

```bash
python -m bot.main --once     # une seule itération (vérifier que tout est connecté)
python -m bot.main --close    # fermer la position ouverte maintenant
touch STOP                    # arrêter le bot proprement (rm STOP pour relancer)
python -m pytest tests        # tests
```

## Important

- Le stop-loss est **surveillé par le bot** (toutes les 30 s) : si le bot est éteint,
  le stop n'est pas appliqué. Fais-le tourner sur une machine allumée en permanence
  (petit serveur/VPS) ou ferme ta position avant de l'arrêter.
- Ne partage jamais ton fichier `.env` ; il est exclu de git.
- Courtiers actions français (Boursorama, Degiro, Trade Republic…) : pas d'API publique,
  donc non compatibles. Pour les actions, il faudrait un courtier avec API
  (Interactive Brokers, Alpaca) — un module dédié peut être ajouté.
