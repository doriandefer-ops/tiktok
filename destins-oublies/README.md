# Destins oubliés — compte TikTok d'histoires vraies

Chaque jour, une vidéo de 40-60 s sur **une personne inconnue de l'Histoire au destin incroyable**,
avec un retournement final. Inspiré du format « histoires historiques » (type @pixels.stories.fr),
mais angle différent : pas de grands événements, des **destins individuels oubliés**.

| Fichier | Rôle |
|---|---|
| `histoires/NNN-nom.json` | Le script : phrases lues, texte choc à l'écran, image Wikipédia par plan, légende du post |
| `make_histoire.py` | Génère la vidéo 9:16 (voix « Rémy », images d'archives animées, sous-titres) |
| `sorties/NNN-nom.mp4` | Les vidéos prêtes (servies à Metricool via raw.githubusercontent.com) |
| `publiees.txt` | Histoires déjà programmées sur TikTok (une par ligne) |
| `PUBLIER.md` | La procédure quotidienne suivie par la tâche planifiée |

```bash
pip install edge-tts pillow numpy soundfile   # + ffmpeg
python3 make_histoire.py --suivante           # rend la prochaine histoire non publiée
```

## Règles éditoriales
- **Que des faits vérifiables** (article Wikipédia de la personne au minimum). Pas de chiffre inventé.
- Images : uniquement des images libres de Wikimedia Commons (le script refuse les images « fair use »).
- Accroche choc en 1 phrase, 8-10 plans, chute finale, CTA « Abonne-toi : un destin oublié chaque jour ».
- Pas de sujet déjà traité (voir `histoires/`). Varier époques, pays, hommes/femmes.
- Vidéo déclarée « contenu généré par IA » sur TikTok (voix de synthèse).
