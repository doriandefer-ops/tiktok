# Paris IA — prototype

Site d'abonnement qui publie les probabilités de chaque match de 10 championnats de football
(Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Liga Portugal, Pro League, Süper Lig, Premiership écossaise).

## Lancer en local

```bash
pip install -r requirements.txt
cd backend
python3 data.py        # télécharge résultats + cotes (football-data.co.uk)
python3 backtest.py    # backtest walk-forward -> data/backtest.json, data/history.json
python3 predict.py     # probabilités des prochains matchs -> data/predictions.json
uvicorn app:app --port 8000
```

Ouvrir http://localhost:8000. Sans clés Stripe, le bouton d'abonnement active l'offre directement (mode démo).

## Contenu

| Fichier | Rôle |
| --- | --- |
| `backend/data.py` | Téléchargement des résultats et cotes de 4 saisons |
| `backend/model.py` | Modèle Dixon-Coles pondéré dans le temps : 1X2, +2,5 buts, BTTS, buts attendus, scores |
| `backend/backtest.py` | Réentraînement hebdomadaire sans regard vers le futur, ROI et CLV contre le marché |
| `backend/predict.py` | Probabilités publiées (35 % modèle, 65 % marché) et écarts avec les meilleures cotes |
| `backend/app.py` | API FastAPI : comptes (18+), offres Gratuit / Premium / Pro, Stripe Checkout + webhook |
| `frontend/` | Site : matchs, bilan public, offres, mentions de prévention obligatoires |

## Stripe (paiement réel)

Créer deux prix récurrents (19,99 € et 39,99 €/mois) puis définir :
`STRIPE_SECRET_KEY`, `STRIPE_PRICE_PREMIUM`, `STRIPE_PRICE_PRO`, `STRIPE_WEBHOOK_SECRET`, `APP_SECRET`, `SITE_URL`.
Webhook à pointer sur `/api/stripe/webhook` (événements `checkout.session.completed`, `customer.subscription.deleted`).

## Résultat du backtest (3 987 matchs depuis août 2025)

Le modèle seul est moins précis que les cotes (log-loss 0,998 contre 0,969 à la clôture) et ses
« value bets » perdent 18 % en mise fixe. À améliorer avant tout lancement payant : xG, compositions,
blessés, suivi du CLV.

## Limites du prototype

- `fixtures.csv` ne couvre que les prochains jours ; en production, utiliser une API de calendrier (API-Football…).
- Mise à jour à lancer via une tâche planifiée (`predict.py` toutes les heures).
- Données football-data.co.uk : vérifier les conditions d'usage commercial, sinon passer à une source payante.
