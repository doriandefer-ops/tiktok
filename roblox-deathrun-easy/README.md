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

## Boutique (gagner des Robux)
Le jeu contient déjà :
- un bouton **⏭ Passer** (côté gauche de l'écran) et une **🛒 Boutique** ;
- **Passer le niveau** et **Passer 10 niveaux** (produits développeur, achetables plusieurs fois) ;
- les Game Pass **⚡ Vitesse ×2** et **🌈 Traînée arc-en-ciel** (achetés pour toujours, et le
  joueur peut les activer ou les couper dans la boutique) ;
- un message **« Bloqué ? Passe le niveau ! »** après 3 morts sur le même niveau.

Les achats sont vérifiés par le serveur. Un achat n'est jamais donné deux fois, même si Roblox renvoie le reçu.

### Brancher tes articles (une seule fois)
1. Publie le jeu : *Fichier → Publier sur Roblox*.
2. Va sur **create.roblox.com → Créations → ton jeu → Monétisation**.
3. **Produits développeur** → crée « Passer le niveau » (ex. 15 R$) et « Passer 10 niveaux » (ex. 89 R$).
4. **Passes** → crée « Vitesse ×2 » (ex. 99 R$) et « Traînée arc-en-ciel » (ex. 49 R$), et mets-les **en vente**.
5. Copie le numéro (ID) de chaque article et colle-le dans `src/shared/Config.luau` :
   ```lua
   SkipStage = { id = 123456789, ... },
   ```
6. Relance `python3 build_place.py`, rouvre le fichier dans Studio et republie.

Tant qu'un ID vaut `0`, l'article affiche « Bientôt » au lieu d'un prix. Dans Studio, les achats
sont des tests gratuits : tu peux tout essayer sans payer.

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
