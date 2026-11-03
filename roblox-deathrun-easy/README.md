# Deathrun Easy — 500 niveaux (Roblox)

Un parcours d'obstacles « deathrun » **facile** de **500 niveaux**, générés automatiquement
au lancement du serveur. Aucun modèle à construire à la main : les scripts créent toute la carte.

## Ce qu'il y a dans le jeu
- **500 niveaux** sur 20 rangées de 25, au-dessus d'une mer de lave.
- **8 types de pièges** : sauts de plateforme, barres rouges à sauter, barres qui tournent,
  blocs qui glissent, dalles qui disparaissent, lasers qui s'allument, escaliers, poutres en zigzag.
- **Facile** : aucun trou ne dépasse 5,5 studs (un saut normal en fait ~8). Les 10 premiers
  niveaux n'utilisent que les pièges les plus simples, ça se corse un peu jusqu'au niveau 500.
- **Checkpoints** : la plateforme verte au bout de chaque niveau sauvegarde ta progression ;
  quand tu meurs, tu réapparais au début de ton niveau (en 1 seconde).
- **Sauvegarde** (DataStore) : niveau, record et victoires sont gardés entre les parties.
- **Interface** : « Niveau X / 500 », barre de progression, boutons ◀ ▶ pour revoir les niveaux
  déjà débloqués et « Aller à mon record ».
- **Classement** (leaderstats) : Niveau et Victoires. Finir le niveau 500 = +1 victoire et retour au niveau 1.

## Lancer le jeu (le plus simple)
1. Ouvre **Roblox Studio**.
2. *Fichier → Ouvrir depuis un fichier* → choisis `DeathrunEasy.rbxlx`.
3. Clique sur **Jouer** (F5). La carte se génère en quelques secondes.

Pour que la sauvegarde marche : publie le jeu (*Fichier → Publier sur Roblox*), puis
*Paramètres du jeu → Sécurité → Autoriser l'accès Studio aux services API*.

## Autre méthode : copier-coller les scripts
Dans un nouveau projet « Baseplate » :

| Fichier | Où le mettre dans Studio | Type |
|---|---|---|
| `src/shared/Config.luau` | ReplicatedStorage → dossier `DeathrunShared` → `Config` | ModuleScript |
| `src/server/LevelGenerator.luau` | ServerScriptService → dossier `DeathrunServer` → `LevelGenerator` | ModuleScript |
| `src/server/Main.server.luau` | ServerScriptService → dossier `DeathrunServer` → `Main` | Script |
| `src/client/Client.client.luau` | StarterPlayer → StarterPlayerScripts → `Client` | LocalScript |

Les noms des dossiers et des scripts doivent être exactement ceux-là.
Avec [Rojo](https://rojo.space), `rojo serve` utilise directement `default.project.json`.

## Personnaliser
Tout se règle dans `src/shared/Config.luau` :
- `TOTAL_STAGES` — nombre de niveaux (500).
- `SEED` — change ce nombre pour obtenir 500 niveaux complètement différents.
- `BASE_HEIGHT`, `STAGE_LENGTH`, `ROW_SPACING` — taille de la carte.

Pour ajouter un nouveau piège : écris une fonction `Obstacles.monPiege(ctx)` dans
`LevelGenerator.luau` (le chemin doit aller de x = 16 à x = 64) et ajoute `"monPiege"` à `ALL_OBSTACLES`.

Après avoir modifié un fichier de `src/`, regénère le fichier de jeu :
```bash
python3 build_place.py
```
