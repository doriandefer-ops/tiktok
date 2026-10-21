"""Musique de fond d'ambiance « documentaire », générée (aucun droit d'auteur).

Nappes en mineur, basse tenue et notes de piano espacées. Si des fichiers audio sont déposés dans
musiques/ (mp3/wav/m4a, libres de droits), l'un d'eux est utilisé à la place.
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

DOSSIER = Path(__file__).resolve().parent / "musiques"

# Progressions (fréquences fondamentales en Hz) : Am-F-C-G, Dm-Bb-F-C, Em-C-G-D
PROGRESSIONS = [
    [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66)],
    [(146.83, 174.61, 220.0), (116.54, 146.83, 174.61), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0)],
    [(164.81, 196.0, 246.94), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66), (146.83, 185.0, 220.0)],
]


def _lisse(x, k=4):
    """Passe-bas simple (moyenne glissante) pour adoucir les nappes."""
    return np.convolve(x, np.ones(k) / k, mode="same")


def generer(duree, sr, seed=0):
    rng = np.random.default_rng(seed)
    prog = PROGRESSIONS[seed % len(PROGRESSIONS)]
    n = int(duree * sr) + sr
    t = np.arange(n) / sr
    out = np.zeros(n)
    accord = 4.0  # secondes par accord
    for i in range(int(np.ceil(duree / accord)) + 1):
        a, b = int(i * accord * sr), min(n, int((i + 1) * accord * sr + 1.5 * sr))
        if a >= n:
            break
        seg = t[a:b] - t[a]
        env = np.minimum(1, seg / 1.2) * np.minimum(1, np.maximum(0, (b - a) / sr - seg) / 1.5)
        for f in prog[i % len(prog)]:
            for det in (-0.6, 0.0, 0.6):  # nappe légèrement désaccordée
                out[a:b] += env * 0.05 * np.sin(2 * np.pi * (f + det) * seg + rng.uniform(0, 6.28))
        f0 = prog[i % len(prog)][0] / 2
        out[a:b] += env * 0.10 * np.sin(2 * np.pi * f0 * seg)  # basse
        for k in range(2):  # deux notes de « piano » par accord
            note = prog[i % len(prog)][rng.integers(0, 3)] * 2
            s = a + int((k * 2 + rng.uniform(0.2, 0.8)) * sr)
            if s >= n:
                continue
            m = min(n - s, int(2.5 * sr))
            tt = np.arange(m) / sr
            out[s:s + m] += 0.06 * np.exp(-tt * 1.8) * (np.sin(2 * np.pi * note * tt)
                                                       + 0.3 * np.sin(4 * np.pi * note * tt))
    out = _lisse(out)
    out[: int(1.5 * sr)] *= np.linspace(0, 1, int(1.5 * sr))
    fin = int(duree * sr)
    out = out[:fin]
    out[-int(1.5 * sr):] *= np.linspace(1, 0, int(1.5 * sr))
    return (out / max(1e-6, np.abs(out).max())).astype(np.float32)


def piste(duree, sr, seed=0):
    """Piste normalisée (crête 1.0) : fichier de musiques/ si présent, sinon musique générée."""
    fichiers = sorted(p for p in DOSSIER.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")) \
        if DOSSIER.exists() else []
    if not fichiers:
        return generer(duree, sr, seed)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "m.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
                        "-i", fichiers[seed % len(fichiers)], "-t", f"{duree:.2f}",
                        "-af", f"afade=t=in:d=1.5,afade=t=out:st={max(0, duree - 1.5):.2f}:d=1.5",
                        "-ar", str(sr), "-ac", "1", wav], check=True)
        a, _ = sf.read(wav, dtype="float32")
    return a / max(1e-6, float(np.abs(a).max()))


def mixer(voix, musique, niveau=0.14):
    """Voix + musique en fond, la musique baisse quand la voix parle (ducking simple)."""
    n = len(voix)
    musique = np.resize(musique, n) if len(musique) < n else musique[:n]
    env = np.abs(voix)
    k = 2400
    env = np.convolve(env, np.ones(k) / k, mode="same")
    duck = 1 - 0.45 * np.clip(env / (env.max() + 1e-6) * 4, 0, 1)
    mix = voix + niveau * musique * duck
    return (mix * 0.95 / max(1e-6, float(np.abs(mix).max()))).astype(np.float32)
