#!/usr/bin/env python3
"""Génère les vidéos TikTok 9:16 (1080x1920) : fond vidéo + texte style Snap + voix off.

Usage :
    python3 make_videos.py                          # génère les 3 vidéos (voix Microsoft « Rémy », internet requis)
    python3 make_videos.py --voix kokoro            # voix féminine hors-ligne
    python3 make_videos.py --voix aucune            # sans voix (pour enregistrer la tienne dans CapCut)
    python3 make_videos.py --voix piper             # voix masculine hors-ligne (moins naturelle)
    python3 make_videos.py --avant a.png --apres b.png
        # version « avant/après » avec TES vraies captures (jour 1 / aujourd'hui)

Fonds : mets tes propres clips (.mp4/.mov) dans videos/fonds/ et ils seront utilisés (recadrés en
9:16, assombris). Sinon, un fond animé « satisfaisant » est généré automatiquement.

Les sous-titres sont calés sur la voix : chaque segment dure le temps de sa phrase.
"""
import argparse
import asyncio
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

import fond_anime

OUT = Path(__file__).resolve().parent
FONDS = OUT / "fonds"
CACHE = Path.home() / ".cache" / "tiktok-voix"
W, H, SR = 1080, 1920, 24000

KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
PIPER_URL = "https://github.com/rhasspy/piper/releases/download/"

# Orthographe phonétique pour les moteurs hors-ligne (sinon « dropshipping » est lu à l'anglaise).
RESPELL = {"dropshipping": "dropchipinng", "Shopify": "chopifaille"}

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Big,Inter,110,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,7,2,5,80,80,0,1
Style: Accent,Inter,150,&H0000E5FF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,8,2,5,80,80,0,1
Style: Snap,Inter,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,1,0,0,0,100,100,0,0,3,24,0,5,0,0,0,1
Style: Label,Inter,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,6,2,8,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

POP = r"{\fad(80,80)\t(0,120,\fscx108\fscy108)\t(120,220,\fscx100\fscy100)}"
GAP, TAIL = 0.18, 0.7
Y = "&H0000E5FF&"  # jaune


def S(voice, *items, images=()):
    """Un segment : la phrase lue + les textes affichés pendant qu'elle est lue.
    item = (style, texte, y) ou (style, texte, y, n) pour rester affiché n segments.
    images = [(fichier, y, hauteur_max)] affichées jusqu'à la fin."""
    return {"voice": voice, "items": items, "images": images}


# ---------------------------------------------------------------- voix

def _download(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print("Téléchargement", dest.name)
        urllib.request.urlretrieve(url, dest)
    return dest


class Voice:
    def __init__(self, engine):
        self.engine = engine
        if engine == "kokoro":
            from kokoro_onnx import Kokoro
            self.k = Kokoro(str(_download(KOKORO_URL + "kokoro-v1.0.onnx", CACHE / "kokoro-v1.0.onnx")),
                            str(_download(KOKORO_URL + "voices-v1.0.bin", CACHE / "voices-v1.0.bin")))
        elif engine == "piper":
            if not (CACHE / "piper" / "piper").exists():
                tgz = _download(PIPER_URL + "2023.11.14-2/piper_linux_x86_64.tar.gz", CACHE / "piper.tgz")
                subprocess.run(["tar", "xzf", tgz, "-C", CACHE], check=True)
            if not (CACHE / "fr-gilles-low.onnx").exists():
                tgz = _download(PIPER_URL + "v0.0.2/voice-fr-gilles-low.tar.gz", CACHE / "gilles.tgz")
                subprocess.run(["tar", "xzf", tgz, "-C", CACHE], check=True)

    def say(self, text):
        """Renvoie un tableau float32 mono à 24 kHz."""
        if self.engine != "edge":
            for a, b in RESPELL.items():
                text = text.replace(a, b)
        if self.engine == "aucune":  # silence de la durée d'une lecture normale (~14 caractères/s)
            return np.zeros(int(max(1.2, len(text) / 14) * SR), dtype=np.float32)
        if self.engine == "kokoro":
            audio, sr = self.k.create(text, voice="ff_siwis", speed=1.08, lang="fr-fr")
            return audio.astype(np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "voix"
            if self.engine == "piper":
                subprocess.run([CACHE / "piper" / "piper", "--model", CACHE / "fr-gilles-low.onnx",
                                "--length_scale", "0.9", "--output_file", raw],
                               input=text.encode(), check=True, capture_output=True)
            else:
                import edge_tts
                asyncio.run(edge_tts.Communicate(text, "fr-FR-RemyMultilingualNeural", rate="+10%",
                                                   proxy=os.environ.get("HTTPS_PROXY")).save(str(raw)))
            wav = Path(tmp) / "voix.wav"
            trim = "silenceremove=start_periods=1:start_threshold=-45dB"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", f"{trim},areverse,{trim},areverse",
                            "-ar", str(SR), "-ac", "1", wav], check=True)
            audio, _ = sf.read(wav, dtype="float32")
            return audio


# ---------------------------------------------------------------- rendu

def ts(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def event(start, end, style, text, y):
    return f"Dialogue: 0,{ts(start)},{ts(end)},{style},,0,0,0,,{{\\pos({W // 2},{y})}}{POP}{text}\n"


THEMES = [
    dict(hue0=0.6, top=(8, 8, 16), bottom=(30, 27, 75)),
    dict(hue0=0.0, top=(16, 8, 8), bottom=(60, 13, 13)),
    dict(hue0=0.38, top=(8, 16, 14), bottom=(13, 59, 46)),
]


def background(name, duration, seed, tmp):
    clips = sorted(p for p in FONDS.glob("*") if p.suffix.lower() in (".mp4", ".mov", ".webm")) if FONDS.exists() else []
    if clips:
        clip = clips[seed % len(clips)]
        return ["-stream_loop", "-1", "-i", str(clip)], (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1,"
            "eq=brightness=-0.12:saturation=1.1")
    path = Path(tmp) / f"{name}-fond.mp4"
    fond_anime.generate(path, duration + 0.5, seed=seed, **THEMES[seed % len(THEMES)])
    return ["-i", str(path)], "null"


def render(name, segments, voice, seed):
    clips, events, overlays, bounds, t = [], [], [], [], 0.25
    for seg in segments:
        audio = voice.say(seg["voice"])
        clips.append((t, audio))
        bounds.append((t, t + len(audio) / SR))
        t += len(audio) / SR + GAP
    duration = t - GAP + TAIL
    for i, seg in enumerate(segments):
        for item in seg["items"]:
            style, text, y, keep = (*item, 1) if len(item) == 3 else item
            last = min(i + keep, len(bounds)) - 1
            end = bounds[last][1] + (GAP if last < len(bounds) - 1 else TAIL)
            events.append(event(bounds[i][0], end, style, text, y))
        for img, y, h in seg["images"]:
            overlays.append((img, y, h, bounds[i][0]))

    track = np.zeros(int(duration * SR) + 1, dtype=np.float32)
    for start, audio in clips:
        a = int(start * SR)
        track[a:a + len(audio)] += audio
    track *= 0.95 / max(1e-6, float(np.abs(track).max()))

    with tempfile.TemporaryDirectory() as tmp:
        ass = Path(tmp) / "subs.ass"
        ass.write_text(ASS_HEADER + "".join(events), encoding="utf-8")
        wav = Path(tmp) / "voix.wav"
        sf.write(wav, track, SR)
        bg_in, bg_filter = background(name, duration, seed, tmp)
        inputs = [*bg_in, "-i", str(wav)]
        chain, last = [f"[0:v]{bg_filter}[bg]"], "[bg]"
        for i, (img, y, h, t0) in enumerate(overlays):
            inputs += ["-loop", "1", "-t", f"{duration:.2f}", "-i", str(img)]
            chain.append(f"[{i + 2}:v]scale=900:{h}:force_original_aspect_ratio=decrease[img{i}]")
            chain.append(f"{last}[img{i}]overlay=(main_w-overlay_w)/2:{y}+({h}-overlay_h)/2:enable='gte(t,{t0:.2f})'[v{i}]")
            last = f"[v{i}]"
        chain.append(f"{last}subtitles={ass}:fontsdir=/usr/share/fonts[vout]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
                        "-filter_complex", ";".join(chain),
                        "-map", "[vout]", "-map", "1:a", "-t", f"{duration:.2f}",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                        str(OUT / name)], check=True)
    print(f"OK {OUT / name} ({duration:.1f} s)")


# ---------------------------------------------------------------- les vidéos

def jour1():
    return [
        S("J'ai zéro euro sur mon compte.",
          ("Snap", "J'ai 0 € sur mon compte.", 700), ("Accent", "0 €", 1000)),
        S("Et je lance un dropshipping…",
          ("Big", "Je lance un\\Ndropshipping", 960)),
        S("en vous montrant absolument tout.",
          ("Big", f"et je vous montre\\N{{\\c{Y}}}TOUT", 960)),
        S("Pas de Lambo louée. Pas de faux virements.",
          ("Snap", "Pas de Lambo louée. Pas de faux virements.", 960)),
        S("Juste mes vrais chiffres.",
          ("Big", f"Juste mes\\N{{\\c{Y}}}vrais chiffres", 960)),
        S("Objectif : ma première vente avant le jour trente.",
          ("Snap", "Objectif : 1ère vente avant le jour 30", 960)),
        S("Jour un sur quatre-vingt-dix. Abonne-toi pour voir si j'y arrive.",
          ("Accent", "JOUR 1/90", 820), ("Big", "Abonne-toi\\Npour voir si j'y arrive", 1150)),
    ]


def faux_millionnaires():
    rows = [("Chiffre d'affaires", "50 000 €", "&H0050DC50&", "Cinquante mille euros de chiffre d'affaires."),
            ("− Produits", "−17 000 €", "&H005050FF&", "Moins dix-sept mille de produits."),
            ("− Pub", "−20 000 €", "&H005050FF&", "Moins vingt mille de pub."),
            ("− Frais & apps", "−3 000 €", "&H005050FF&", "Moins trois mille de frais et d'applis."),
            ("− URSSAF", "−6 000 €", "&H005050FF&", "Moins six mille d'Urssaf.")]
    segs = [
        S("« Je fais cinquante mille euros par mois en dropshipping. »",
          ("Snap", "« Je fais 50 000 € par mois en dropshipping »", 960)),
        S("D'accord. Mais regarde le bénéfice, pas le chiffre d'affaires.",
          ("Big", f"Regarde le\\N{{\\c{Y}}}bénéfice,\\Npas le CA", 960)),
    ]
    for i, (label, val, col, voice) in enumerate(rows):
        segs.append(S(voice, ("Snap", f"{label}   {{\\c{col}}}{val}", 560 + i * 150, len(rows) - i + 1)))
    segs += [
        S("Il reste quatre mille euros. Et ce n'est qu'un exemple : parfois, c'est encore moins.",
          ("Accent", "= 4 000 €", 1420)),
        S("Moi, je vous montre le net. Chaque jour.",
          ("Big", f"Moi je vous montre\\Nle {{\\c{Y}}}NET.\\NChaque jour.", 960)),
        S("Commente « net » si on t'a déjà vendu du rêve.",
          ("Snap", "Commente « NET » si on t'a déjà vendu du rêve", 960)),
    ]
    return segs


def avant_apres(avant=None, apres=None):
    if avant and apres:
        return [
            S("Dropshipping à zéro euro : avant, après. Captures réelles, sans filtre.",
              ("Snap", "Dropshipping à 0 € : avant / après", 960)),
            S("Avant : jour un.", ("Label", "AVANT · Jour 1", 90, 2), images=[(avant, 170, 760)]),
            S("Et aujourd'hui.", ("Label", "APRÈS · Aujourd'hui", 970), images=[(apres, 1070, 760)]),
            S("Abonne-toi pour voir la suite.", ("Snap", "Abonne-toi pour la suite", 980)),
        ]
    return [
        S("Dropshipping à zéro euro : l'avant, et l'après.",
          ("Snap", "Dropshipping à 0 € : avant / après", 960)),
        S("Avant : jour un. Zéro euro, zéro boutique, zéro abonné.",
          ("Label", "AVANT · Jour 1", 90, 3), ("Snap", "0 €   ·   0 boutique   ·   0 abonné", 470, 3),
          ("Accent", "0 €", 700, 3)),
        S("Après : jour trente.", ("Label", "APRÈS · Jour 30", 990, 2), ("Accent", "?", 1350, 2)),
        S("La réponse dans trente jours, avec les vrais chiffres. Abonne-toi pour voir l'après.",
          ("Snap", "Réponse dans 30 jours. Vrais chiffres.", 1600)),
    ]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--voix", choices=["edge", "kokoro", "piper", "aucune"], default="edge")
    p.add_argument("--avant", help="capture du jour 1 (png/jpg)")
    p.add_argument("--apres", help="capture d'aujourd'hui (png/jpg)")
    a = p.parse_args()
    v = Voice(a.voix)
    if a.avant and a.apres:
        render("03-avant-apres-reel.mp4", avant_apres(a.avant, a.apres), v, seed=2)
    else:
        render("01-jour1.mp4", jour1(), v, seed=0)
        render("02-faux-millionnaires.mp4", faux_millionnaires(), v, seed=1)
        render("03-avant-apres.mp4", avant_apres(), v, seed=2)
