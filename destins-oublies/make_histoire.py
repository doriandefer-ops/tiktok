#!/usr/bin/env python3
"""« Destins oubliés » : génère une vidéo TikTok 9:16 à partir d'une histoire JSON.

Usage :
    python3 make_histoire.py histoires/001-yamaguchi.json      # -> sorties/001-yamaguchi.mp4
    python3 make_histoire.py --suivante                        # 1re histoire pas encore publiée

Format d'une histoire (histoires/NNN-nom.json) :
    {"titre": "...", "legende": "texte du post + hashtags",
     "segments": [{"voix": "phrase lue", "ecran": "texte choc (optionnel)",
                   "image": "Titre_page_Wikipedia_en" | "fr:Titre_page_fr"}]}
Les images sont l'image principale de l'article Wikipédia (souvent du domaine public).
"""
import argparse
import asyncio
import json
import os
import re
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
HIST, SORTIES, CACHE = ROOT / "histoires", ROOT / "sorties", ROOT / ".cache"
PUBLIEES = ROOT / "publiees.txt"
W, H, FPS, SR = 1080, 1920, 30, 24000
UA = "DestinsOubliesBot/1.0 (https://github.com/doriandefer-ops/tiktok)"
VOIX = "fr-FR-RemyMultilingualNeural"
CA = "/root/.ccr/ca-bundle.crt"
SSL = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter Black,88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,8,3,5,70,70,0,1
Style: Choc,Inter Black,120,&H0040D8FF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,9,3,5,70,70,0,1
Style: Marque,Inter,46,&H00E6F0F5,&H00FFFFFF,&H00000000,&H66000000,1,0,0,0,100,100,6,0,3,14,0,8,0,0,110,1
"""
EVENTS = "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
POP = r"{\fad(60,60)\t(0,100,\fscx110\fscy110)\t(100,200,\fscx100\fscy100)}"
GAP = 0.12


# ---------------------------------------------------------------- voix

def voix(text, tmp):
    import edge_tts
    import edge_tts.communicate
    edge_tts.communicate._SSL_CTX = SSL
    raw, wav = Path(tmp) / "v.mp3", Path(tmp) / "v.wav"
    asyncio.run(edge_tts.Communicate(text, VOIX, rate="+8%", pitch="-4Hz",
                                     proxy=os.environ.get("HTTPS_PROXY")).save(str(raw)))
    trim = "silenceremove=start_periods=1:start_threshold=-45dB"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    f"{trim},areverse,{trim},areverse", "-ar", str(SR), "-ac", "1", wav], check=True)
    return sf.read(wav, dtype="float32")[0]


# ---------------------------------------------------------------- images

def _get(url, essais=4):
    import time
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, context=SSL, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == essais - 1:
                raise
            time.sleep(3 * 2 ** k)


def image(ref):
    """Télécharge (avec cache) l'image principale d'un article Wikipédia ("Titre" en anglais, ou "fr:Titre")."""
    CACHE.mkdir(exist_ok=True)
    dest = CACHE / (re.sub(r"[^\w-]", "_", ref)[:80] + ".img")
    if dest.exists():
        return dest
    lang, title = ref.split(":", 1) if ref[:3] in ("fr:", "en:") else ("en", ref)
    info = json.loads(_get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                           + urllib.parse.quote(title.replace(" ", "_"))))
    orig, thumb = info.get("originalimage"), info.get("thumbnail")
    if not orig:
        raise LookupError(f"pas d'image pour {ref}")
    if "/wikipedia/commons/" not in orig["source"]:  # image non libre (fair use) : on n'en veut pas
        raise LookupError(f"image non libre pour {ref}")
    url = orig["source"]
    # Wikimedia limite les originaux : on prend la miniature standard 1280 px quand elle existe.
    if thumb and orig["width"] > 1280 and "px-" in thumb["source"]:
        url = re.sub(r"/\d+px-", "/1280px-", thumb["source"])
    dest.write_bytes(_get(url))
    return dest


def cadre(src, out):
    """Image 9:16 un peu plus grande que l'écran (marge pour le zoom) : fond flou + image nette, ton archive."""
    big = (int(W * 1.18), int(H * 1.18))
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    fond = ImageOps.fit(im, big).filter(ImageFilter.GaussianBlur(40))
    fond = ImageEnhance.Brightness(fond).enhance(0.45)
    fg = im.copy()
    fg.thumbnail((big[0], int(big[1] * 0.62)))
    if fg.width < big[0] * 0.8:  # petite image : on l'agrandit
        r = big[0] * 0.92 / fg.width
        fg = fg.resize((int(fg.width * r), int(fg.height * r)), Image.LANCZOS)
    fond.paste(fg, ((big[0] - fg.width) // 2, (big[1] - fg.height) // 2 - 60))
    gris = ImageOps.grayscale(fond)
    sepia = ImageOps.colorize(gris, (25, 18, 12), (245, 228, 200))
    fond = Image.blend(fond, sepia, 0.55)
    y, x = np.ogrid[:big[1], :big[0]]
    d = np.sqrt(((x - big[0] / 2) / (big[0] / 2)) ** 2 + ((y - big[1] / 2) / (big[1] / 2)) ** 2)
    vign = np.clip(1.15 - 0.55 * d, 0.35, 1)[..., None]
    Image.fromarray((np.asarray(fond) * vign).astype(np.uint8)).save(out, quality=95)


def plan(img, duree, i, out):
    """Clip animé (Ken Burns) d'une image fixe."""
    n = max(2, int(duree * FPS) + 2)
    z = (f"1+0.10*on/{n}" if i % 2 == 0 else f"1.10-0.10*on/{n}")
    x = ["iw/2-(iw/zoom/2)", f"(iw-iw/zoom)*on/{n}", f"(iw-iw/zoom)*(1-on/{n})"][i % 3]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", img, "-vf",
                    f"scale={int(W * 1.18) * 2}:-1,zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)':"
                    f"d={n}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p",
                    "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out], check=True)


# ---------------------------------------------------------------- sous-titres

def ts(t):
    h, rem = divmod(max(0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def morceaux(text, t0, t1):
    """Découpe la phrase en blocs de ~3 mots, timés au prorata des caractères."""
    mots = text.split()
    blocs, cur = [], []
    for m in mots:
        cur.append(m)
        if len(cur) >= 3 or m[-1] in ".,!?:;…":
            blocs.append(" ".join(cur))
            cur = []
    if cur:
        blocs.append(" ".join(cur))
    total = sum(len(b) + 2 for b in blocs)
    t, out = t0, []
    for b in blocs:
        d = (t1 - t0) * (len(b) + 2) / total
        out.append((t, t + d, b))
        t += d
    return out


# ---------------------------------------------------------------- rendu

def render(path):
    h = json.loads(Path(path).read_text(encoding="utf-8"))
    SORTIES.mkdir(exist_ok=True)
    out = SORTIES / (Path(path).stem + ".mp4")
    with tempfile.TemporaryDirectory() as tmp:
        audios, events, clips, t = [], [], [], 0.0
        imgs = []
        for seg in h["segments"]:
            try:
                imgs.append(image(seg["image"]) if seg.get("image") else None)
            except Exception as e:  # image introuvable ou non libre : on réutilise une voisine
                print("image ignorée", seg.get("image"), e)
                imgs.append(None)
        if not any(imgs):
            raise SystemExit("Aucune image utilisable pour cette histoire")
        first = next(i for i in imgs if i)
        for i in range(len(imgs)):
            imgs[i] = imgs[i] or (imgs[i - 1] if i else first)
        for i, seg in enumerate(h["segments"]):
            a = voix(seg["voix"], tmp)
            dur = len(a) / SR + GAP + (0.8 if i == len(h["segments"]) - 1 else 0)
            audios.append((t, a))
            for s, e, b in morceaux(seg["voix"], t, t + len(a) / SR):
                events.append(f"Dialogue: 0,{ts(s)},{ts(e)},Sub,,0,0,0,,{{\\pos({W // 2},1380)}}{POP}{b.upper()}\n")
            if seg.get("ecran"):
                events.append(f"Dialogue: 1,{ts(t)},{ts(t + dur)},Choc,,0,0,0,,{{\\pos({W // 2},360)}}{POP}{seg['ecran']}\n")
            src = imgs[i]
            frame = Path(tmp) / f"f{i}.jpg"
            cadre(src, frame)
            clip = Path(tmp) / f"c{i}.mp4"
            plan(frame, dur, i, clip)
            clips.append((clip, dur))
            t += dur
        events.append(f"Dialogue: 2,0:00:00.00,{ts(t)},Marque,,0,0,0,,DESTINS OUBLIÉS\n")

        track = np.zeros(int(t * SR) + SR, dtype=np.float32)
        for s, a in audios:
            track[int(s * SR):int(s * SR) + len(a)] += a
        track *= 0.95 / max(1e-6, float(np.abs(track).max()))
        wav = Path(tmp) / "voix.wav"
        sf.write(wav, track[:int(t * SR)], SR)
        lst = Path(tmp) / "liste.txt"
        lst.write_text("".join(f"file '{c}'\nduration {d:.3f}\n" for c, d in clips))
        ass = Path(tmp) / "subs.ass"
        ass.write_text(ASS_HEADER + EVENTS + "".join(events), encoding="utf-8")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                        "-i", wav, "-vf", f"subtitles={ass}:fontsdir=/usr/share/fonts",
                        "-map", "0:v", "-map", "1:a", "-t", f"{t:.2f}", "-r", str(FPS),
                        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], check=True)
    print(f"OK {out} ({t:.1f} s)")
    return out


def suivante():
    faites = set(PUBLIEES.read_text().split()) if PUBLIEES.exists() else set()
    for p in sorted(HIST.glob("*.json")):
        if p.stem not in faites:
            return p
    raise SystemExit("Plus d'histoire en stock : écris-en une nouvelle dans histoires/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("histoire", nargs="?")
    ap.add_argument("--suivante", action="store_true")
    a = ap.parse_args()
    render(suivante() if a.suivante or not a.histoire else a.histoire)
