# Procédure quotidienne (tâche planifiée)

1. `git pull origin master`, puis `pip install -q edge-tts pillow numpy soundfile`.
2. S'il reste moins de 5 histoires non publiées (`histoires/*.json` absentes de `publiees.txt`),
   écrire 3 nouvelles histoires au même format, numérotées à la suite. Sujets : personnes réelles,
   peu connues, destin surprenant ; faits vérifiés sur Wikipédia (`/api/rest_v1/page/summary/<Titre>`).
3. `python3 make_histoire.py --suivante` → `sorties/NNN-nom.mp4`. Vérifier 2-3 images extraites
   (`ffmpeg -ss 5 -i ... -frames:v 1`) : sous-titres lisibles, images cohérentes.
4. Commit + push de la vidéo et des nouvelles histoires sur `master`.
5. Vérifier que `https://raw.githubusercontent.com/doriandefer-ops/tiktok/master/destins-oublies/sorties/NNN-nom.mp4`
   répond 200 (le dépôt doit être public).
6. Metricool `createScheduledPost` : blogId `7545702`, réseau `tiktok`, aujourd'hui à 18:30 Europe/Paris
   (ou dans 15 min si 18:30 est passé), `text` = `legende`, `media` = [URL raw],
   `tiktokData` = {"privacyOption": "PUBLIC_TO_EVERYONE", "isAigc": true, "title": titre}, `autoPublish` true,
   **`draft` true** : le post reste en brouillon dans Metricool, l'utilisateur le relit et le valide avant publication.
   Donner le lien `plannerUrl` du brouillon dans le compte rendu.
7. Ajouter `NNN-nom` à `publiees.txt`, commit + push.
