# 07 — Organisation du projet et supports pédagogiques

## Arborescence

```
masterclass-trading/
├── README.md                          ← index du projet
├── 00_PLAN_DIRECTEUR/                 ← ce dossier (architecture, stratégie, charte, calendrier)
│
├── MODULE_01_COMPRENDRE_LE_TRADING/
│   ├── README.md                      ← objectifs, liste des chapitres, statut de production
│   ├── CH00_bande_annonce/
│   ├── CH01_quest_ce_que_le_trading/
│   │   ├── CH01_script.md             ← script mot pour mot + visuels + B-roll
│   │   ├── CH01_shorts.md             ← 3 à 7 Shorts complets
│   │   ├── CH01_miniature.md          ← brief + 2 variantes (A/B)
│   │   ├── CH01_seo.md                ← titres, description, tags, timestamps, commentaire épinglé
│   │   └── CH01_montage.md            ← liste des animations, inserts, musiques, notes au monteur
│   ├── …
│   ├── M01_fiche_recap.md
│   ├── M01_vocabulaire.md
│   ├── M01_quiz.md                    ← questions + corrigé
│   ├── M01_exercices.md               ← énoncés + corrections détaillées
│   └── M01_cas_pratique.md
├── MODULE_02_LIRE_UN_GRAPHIQUE/
├── MODULE_03_ANALYSE_TECHNIQUE/
├── MODULE_04_CONSTRUIRE_UNE_STRATEGIE/
├── MODULE_05_RISK_MANAGEMENT/
├── MODULE_06_PSYCHOLOGIE/
├── MODULE_07_BACKTESTING_STATISTIQUES/
├── MODULE_08_PLAN_DE_TRADING/
├── MODULE_09_PASSAGE_AU_REEL/
├── MODULE_10_ALLER_PLUS_LOIN/
│
├── CHARTE_GRAPHIQUE/                  ← palette, polices, gabarits de miniatures, lower thirds
├── MONTAGE/                           ← modèles de projets, animations réutilisables, musiques (licences)
├── SEO/                               ← modèle de description, banque de tags, hashtags, mentions légales
├── CHECKLISTS/                        ← checklist conformité avant publication, checklist tournage
├── JOURNAL_TRADING/                   ← journal vierge (CSV / Sheets), grille de revue hebdo
├── RESSOURCES/                        ← sources officielles, données historiques, licences.md
└── EXERCICES/  (vue transverse)       ← index de tous les exercices, par compétence
```

**Pourquoi des dossiers par chapitre plutôt que des dossiers `/SCRIPTS`, `/SHORTS` et `/SEO` séparés ?** Un chapitre est une unité de production : on le tourne, le monte et le publie d'un bloc, donc tout ce qui le concerne est rangé au même endroit. Les dossiers transverses (`SEO/`, `MONTAGE/`, `CHECKLISTS/`…) contiennent seulement les **gabarits** et les éléments partagés.

## Conventions de nommage

- Modules : `MODULE_XX_NOM_EN_MAJUSCULES`.
- Chapitres : `CHXX_nom_en_minuscules`, numérotés de 00 à 30 sur toute la formation (pas de remise à zéro par module).
- Fichiers : `CHXX_type.md`, avec `type` ∈ `script | shorts | miniature | seo | montage`.
- Shorts : identifiant `CHXX-S1` à `CHXX-S7`, repris dans les noms des exports vidéo (`CH17-S2_moins50_plus100.mp4`).
- Supports de module : `MXX_type.md`, avec `type` ∈ `fiche_recap | vocabulaire | quiz | exercices | cas_pratique`.

## Supports pédagogiques par module

| Module | Fiche récap | Vocabulaire (nb de termes) | Quiz | Exercices types | Cas pratique | Outil livré |
|---|---|---|---|---|---|---|
| **M1** | Les marchés et les frais sur 1 page | 25 (spread, swap, marge, pip, lot…) | 10 Q | Calculer le coût d'un aller-retour, le levier effectif, choisir un type d'ordre | « Le stop qui a sauté » (gap) | Tableau comparatif des marchés |
| **M2** | Lire un graphique en 5 étapes | 15 | 10 Q | Identifier la tendance, tracer des zones, repérer une cassure de structure | Analyse multi-timeframe d'un graphique historique | Checklist « lecture d'un graphique » |
| **M3** | Grille en 7 points pour chaque indicateur | 15 | 10 Q | Lire un RSI, une divergence, calculer un stop à 1,5 ATR | Une confluence qui échoue | Antisèche des indicateurs |
| **M4** | Les 6 briques d'une stratégie | 12 | 10 Q | Transformer une idée floue en règle, calculer un R:R et le taux de réussite d'équilibre | Une stratégie jouée hors de son contexte | Gabarit « fiche stratégie » |
| **M5** ⭐ | Les 3 formules du risque | 12 | 12 Q | Taille de position, perte → gain nécessaire, simulation d'une série de pertes | « Deux traders, même stratégie, risques différents » | **Calculateur de taille de position** (Sheets) |
| **M6** | Les 5 pièges et leurs règles d'arrêt | 10 | 8 Q | Identifier le biais dans 6 situations décrites | La journée qui dérape | Checklist « état émotionnel avant séance » |
| **M7** | Le tableau de bord d'une stratégie | 14 | 12 Q | Calculer l'expectancy et le profit factor, repérer un biais de backtest | « Cette stratégie a-t-elle un intérêt ? » (3 jeux de données fictifs) | **Modèle de backtest** (Sheets) |
| **M8** | Le plan sur 1 page | 8 | 8 Q | Remplir chaque rubrique, détecter les incohérences d'un plan | Corriger un plan mal écrit | **Plan de trading vierge** + **journal de trading** |
| **M9** | Les conditions minimales avant le réel | 8 | 8 Q | Estimer slippage et frais, comparer une démo et un réel | Le même trade en démo et en réel | Checklist « démo validée ? » (critères écrits à l'avance) |
| **M10** | Les 10 signaux d'arnaque | 10 | 10 Q | Vérifier 3 brokers fictifs, analyser 3 fausses pubs | « Le mentor Instagram » | Checklist « vérifier un broker » |

### Exemples d'exercices (aperçu du niveau attendu)

**Exercice M5 : calculer la taille d'une position**
> Capital : 4 000 €. Risque maximum par trade : 1 %. Entrée sur une action à 50,00 €, stop d'invalidation à 48,40 €.
> Combien d'actions peux-tu acheter au maximum ?

*Correction* : risque en euros = 4 000 × 1 % = **40 €**. Distance au stop = 50,00 − 48,40 = **1,60 €** par action. Taille = 40 ÷ 1,60 = **25 actions** (soit 1 250 € de position).
Point clé : la taille découle du stop, pas l'inverse. Les frais et un éventuel gap peuvent augmenter la perte réelle au-delà de 40 €.

**Exercice M7 : l'expectancy est-elle positive ?**
> Sur 120 trades fictifs : 66 gagnants (gain moyen 80 €), 54 perdants (perte moyenne 110 €). Frais moyens : 4 € par trade.

*Correction* : taux de réussite = 55 %. Expectancy brute = 0,55 × 80 − 0,45 × 110 = 44 − 49,5 = **−5,50 € par trade**. Nette de frais : **−9,50 €**.
Conclusion : malgré une majorité de trades gagnants, cette stratégie perd de l'argent en moyenne. Et 120 trades restent un échantillon limité.

**Exercice M2 : identifier l'invalidation**
> Graphique fictif : une tendance haussière avec les creux 100 → 104 → 108 et les sommets 106 → 111 → 115. Où l'idée « la tendance haussière continue » est-elle invalidée ?

*Correction* : sous le dernier creux (108), et pas sous un montant arbitraire. La cassure de 108 casse la structure de creux de plus en plus hauts. En pratique, on prévoit une marge (par exemple une fraction d'ATR) pour ne pas être sorti par le simple bruit.

## Outils transverses

| Fichier (à produire) | Dossier |
|---|---|
| `journal_trading_vierge.csv` + version Google Sheets | `JOURNAL_TRADING/` |
| `grille_revue_hebdomadaire.md` | `JOURNAL_TRADING/` |
| `plan_trading_vierge.md` (11 rubriques) | `MODULE_08_PLAN_DE_TRADING/` |
| `checklist_conformite_publication.md` | `CHECKLISTS/` |
| `checklist_tournage.md` | `CHECKLISTS/` |
| `modele_description_youtube.md` + `banque_hashtags.md` | `SEO/` |
| `sources_officielles.md` (AMF, ACPR, ESMA, impots.gouv) + `licences.md` | `RESSOURCES/` |
