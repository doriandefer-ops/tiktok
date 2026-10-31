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

## Résultat du backtest

Réglages choisis sur la saison 2025-26, vérifiés sur 786 matchs de 2026-27 jamais vus (log-loss 1X2, plus bas = mieux) :

| Modèle | Log-loss |
| --- | --- |
| v1 : buts seuls | 1,008 |
| v2 : buts 30 % + tirs cadrés 70 % (`SHOTS = 0.7`) | 0,977 |
| Marché à l'ouverture (cotes moyennes) | 0,961 |
| Marché à la clôture | 0,956 |

Le modèle reste moins précis que le marché. Quand il s'en écarte nettement, c'est lui qui se trompe
(il surestime les outsiders), et aucune des 54 règles de sélection testées n'est rentable sur les deux périodes.
Le site publie donc 30 % modèle + 70 % marché sans marge, affiche les cotes justes et la marge des bookmakers,
et garde les « écarts » dans une section Laboratoire, non recommandée. Pistes pour vraiment battre le marché :
compositions et blessés, xG par tir, données de transferts.

## Affichage

Chaque issue est formulée en probabilité (« Le modèle estime à 57 % les chances d'une victoire de Galatasaray »),
jamais comme un pari à jouer. Cette formulation ne suffit pas seule à rendre le site légal : le discours
commercial ne doit pas non plus laisser croire que le service augmente les chances de gagner.

## Limites du prototype

- `fixtures.csv` ne couvre que les prochains jours ; en production, utiliser une API de calendrier (API-Football…).
- Mise à jour à lancer via une tâche planifiée (`predict.py` toutes les heures).
- Données football-data.co.uk : vérifier les conditions d'usage commercial, sinon passer à une source payante.
