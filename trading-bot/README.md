# Bot de trading Alpaca

Bot simple qui suit la tendance sur des ETF américains (par défaut **SPY** = S&P 500 et **QQQ** = Nasdaq 100).
Il tourne sur un compte **paper** (argent fictif) par défaut.

## La stratégie
Chaque jour, pour chaque symbole :
- moyenne des 20 derniers jours **au-dessus** de celle des 50 jours → on achète (si on n'a rien) ;
- en dessous → on vend tout.

Garde-fous (dans `config.py`) :
- 25 % du capital max par position ;
- si le compte perd 3 % dans la journée → plus aucun achat ce jour-là ;
- plafond total engagé (`CAPITAL_MAX_USD`) ;
- ni vente à découvert ni effet de levier ;
- argent réel **seulement** si `ALPACA_LIVE=oui`.

⚠️ Aucune stratégie ne garantit un gain. Celle-ci sert surtout à éviter les grosses chutes, et en marché
qui monte fort elle fait souvent **moins bien** que d'acheter et garder. Lance le backtest pour en juger.

## Installation
```bash
cd trading-bot
pip install -r requirements.txt
cp .env.example .env        # puis colle tes clés PAPER dedans
set -a; source .env; set +a # charge les clés dans le terminal
```

## Utilisation
```bash
python backtest.py          # 1. regarde ce que la stratégie aurait donné sur 5 ans
python bot.py --simul       # 2. ce qu'il ferait aujourd'hui, sans passer d'ordre
python bot.py               # 3. passe vraiment les ordres (sur le compte paper)
python -m pytest tests      # tests hors ligne
```

Il faut lancer `bot.py` **une fois par jour, marché US ouvert** (15h30–22h heure de Paris), par exemple
vers 21h30 avec une tâche planifiée (cron, ou un cron job Render).
