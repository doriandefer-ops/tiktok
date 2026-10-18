#!/usr/bin/env python3
"""Génère les vidéos TikTok 9:16 (1080x1920) avec ffmpeg + sous-titres ASS.

Usage :
    python3 make_videos.py                      # génère les 3 vidéos
    python3 make_videos.py --avant a.png --apres b.png
        # version « avant/après » avec TES vraies captures (jour 1 / aujourd'hui)

Pas de musique : ajoute un son tendance directement dans l'app TikTok.
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
W, H = 1080, 1920

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Big,Inter,110,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,6,0,5,80,80,0,1
Style: Accent,Inter,150,&H0000E5FF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,7,0,5,80,80,0,1
Style: Snap,Inter,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,1,0,0,0,100,100,0,0,3,24,0,5,0,0,0,1
Style: Small,Inter,52,&H00DDDDDD,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,2,140,140,430,1
Style: Label,Inter,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,0,8,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

POP = r"{\fad(80,80)\t(0,120,\fscx108\fscy108)\t(120,220,\fscx100\fscy100)}"


def ts(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def event(start, end, style, text, y=None, pop=True):
    pos = rf"{{\pos({W // 2},{y})}}" if y is not None else ""
    return f"Dialogue: 0,{ts(start)},{ts(end)},{style},,0,0,0,,{pos}{POP if pop else ''}{text}\n"


def render(name, duration, events, bg=("0x0B0B12", "0x1E1B4B"), overlays=()):
    """overlays : liste de (image, y, hauteur_max, début, fin), centrée, largeur max 900."""
    with tempfile.TemporaryDirectory() as tmp:
        ass = Path(tmp) / "subs.ass"
        ass.write_text(ASS_HEADER + "".join(events), encoding="utf-8")
        inputs = [
            "-f", "lavfi", "-i",
            f"gradients=s={W}x{H}:c0={bg[0]}:c1={bg[1]}:x0=0:y0=0:x1={W}:y1={H}:d={duration}:r=30:speed=0.01",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        ]
        chain, last = [], "[0:v]"
        for i, (img, y, h, t0, t1) in enumerate(overlays):
            inputs += ["-loop", "1", "-t", str(duration), "-i", str(img)]
            idx = i + 2
            chain.append(f"[{idx}:v]scale=900:{h}:force_original_aspect_ratio=decrease[img{i}]")
            chain.append(f"{last}[img{i}]overlay=(main_w-overlay_w)/2:{y}+({h}-overlay_h)/2:enable='between(t,{t0},{t1})'[v{i}]")
            last = f"[v{i}]"
        chain.append(f"{last}vignette=PI/5,subtitles={ass}:fontsdir=/usr/share/fonts[vout]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
               "-filter_complex", ";".join(chain),
               "-map", "[vout]", "-map", "1:a", "-t", str(duration),
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
               str(OUT / name)]
        subprocess.run(cmd, check=True)
    print("OK", OUT / name)


def jour1():
    e = [
        event(0.0, 2.2, "Snap", "J'ai 0 € sur mon compte.", y=760),
        event(0.3, 2.2, "Accent", "0 €", y=1050),
        event(2.2, 4.6, "Big", "Je lance un\\Ndropshipping", y=900),
        event(4.6, 7.0, "Big", "et je vous montre\\N{\\c&H0000E5FF&}TOUT", y=900),
        event(7.0, 9.6, "Snap", "Pas de Lambo louée. Pas de faux virements.", y=900),
        event(9.6, 12.2, "Big", "Juste mes\\N{\\c&H0000E5FF&}vrais chiffres", y=900),
        event(12.2, 14.8, "Snap", "Objectif : 1ère vente avant le jour 30", y=900),
        event(14.8, 18.0, "Accent", "JOUR 1/90", y=820),
        event(14.8, 18.0, "Big", "Abonne-toi\\Npour voir si j'y arrive", y=1150, pop=False),
        event(0.0, 18.0, "Small", "#dropshipping  #partirdezero", pop=False),
    ]
    render("01-jour1.mp4", 18, e)


def faux_millionnaires():
    rows = [
        ("Chiffre d'affaires", "50 000 €", "&H0050DC50&"),
        ("− Produits", "−17 000 €", "&H005050FF&"),
        ("− Pub", "−20 000 €", "&H005050FF&"),
        ("− Frais & apps", "−3 000 €", "&H005050FF&"),
        ("− URSSAF", "−6 000 €", "&H005050FF&"),
    ]
    e = [
        event(0.0, 2.6, "Snap", "« Je fais 50 000 € par mois en dropshipping »", y=800),
        event(0.4, 2.6, "Big", "😏", y=1050),
        event(2.6, 5.0, "Big", "Regarde le\\N{\\c&H0000E5FF&}bénéfice,\\Npas le CA", y=900),
    ]
    t = 5.0
    for i, (label, val, col) in enumerate(rows):
        y = 560 + i * 150
        e.append(event(t + i * 0.9, 13.0, "Snap",
                       f"{label}   {{\\c{col}}}{val}", y=y))
    e += [
        event(9.6, 13.0, "Accent", "= 4 000 €", y=1420),
        event(9.6, 13.0, "Small", "Exemple illustratif — ça varie énormément selon les boutiques", pop=False),
        event(13.0, 16.0, "Big", "Moi je vous montre\\Nle {\\c&H0000E5FF&}NET.\\NChaque jour.", y=900),
        event(16.0, 19.0, "Snap", "Commente « NET » si on t'a déjà vendu du rêve", y=900),
    ]
    render("02-faux-millionnaires.mp4", 19, e, bg=("0x120B0B", "0x3B0D0D"))


def avant_apres(avant=None, apres=None):
    real = bool(avant and apres)
    e = [
        event(0.0, 2.4, "Snap", "Dropshipping à 0 € : avant / après", y=900),
        event(2.4, 16.0, "Label", "AVANT · Jour 1", y=90, pop=False),
        event(8.0, 16.0, "Label", "APRÈS · Aujourd'hui" if real else "APRÈS · Jour 30", y=970, pop=False),
    ]
    overlays = []
    if real:
        overlays = [(avant, 170, 760, 2.4, 16.0), (apres, 1070, 760, 8.0, 16.0)]
        e.append(event(0.0, 16.0, "Small", "Captures réelles, sans filtre", y=1880, pop=False))
    else:
        e += [
            event(3.0, 16.0, "Snap", "0 €   ·   0 boutique   ·   0 abonné", y=470),
            event(4.0, 16.0, "Accent", "0 €", y=700),
            event(8.6, 16.0, "Accent", "?", y=1350),
            event(10.5, 16.0, "Snap", "Réponse dans 30 jours. Vrais chiffres.", y=1600),
            event(12.5, 16.0, "Small", "Abonne-toi pour voir l'après", pop=False),
        ]
    render("03-avant-apres-reel.mp4" if real else "03-avant-apres.mp4", 16, e,
           bg=("0x0B1210", "0x0D3B2E"), overlays=overlays)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--avant", help="capture du jour 1 (png/jpg)")
    p.add_argument("--apres", help="capture d'aujourd'hui (png/jpg)")
    a = p.parse_args()
    if a.avant and a.apres:
        avant_apres(a.avant, a.apres)
    else:
        jour1()
        faux_millionnaires()
        avant_apres()
