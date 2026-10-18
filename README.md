# Compte TikTok « 0 € → dropshipping, je montre tout »

Kit de lancement d'un compte TikTok build-in-public : on part de 0 €, on lance une boutique
dropshipping et on documente **les vrais chiffres**, sans faux train de vie.

| Fichier | Contenu |
|---|---|
| `01-positionnement.md` | Nom du compte, bio, promesse, règles de contenu |
| `02-plan-0-euro.md` | Lancer une boutique sans budget, étape par étape (+ obligations légales) |
| `03-scripts-30-jours.md` | 30 scripts prêts à tourner ou à monter |
| `04-monetisation.md` | Comment gagner de l'argent avec le compte, dans l'ordre |
| `05-checklist-gratuite.md` | Le « cadeau » à offrir en échange d'un email |
| `videos/` | 3 vidéos 9:16 prêtes à poster + le script qui les génère |

Règle d'or : **tout chiffre montré à l'écran doit être réel et capturé.**

## Régénérer les vidéos
```bash
pip install edge-tts kokoro-onnx soundfile numpy pillow   # + ffmpeg
cd videos && python3 make_videos.py               # voix masculine Microsoft « Rémy » (internet requis)
python3 make_videos.py --voix kokoro              # voix féminine hors-ligne (téléchargée au 1er lancement)
```
- **Fonds** : dépose tes propres clips dans `videos/fonds/` (filmés au téléphone, ou des vidéos libres de droits Pexels/Pixabay). Sinon un fond animé est généré.
- **Textes et voix** : modifie les fonctions `jour1()`, `faux_millionnaires()`, `avant_apres()` dans `make_videos.py`.
