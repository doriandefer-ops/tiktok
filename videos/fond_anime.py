#!/usr/bin/env python3
"""Fond animé « satisfaisant » : une balle rebondit dans un cercle et grossit à chaque rebond,
en laissant une traînée colorée. Rendu image par image avec Pillow, encodé par ffmpeg."""
import colorsys
import math
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw

W, H, FPS = 1080, 1920, 30


def _gradient(top, bottom):
    t = np.linspace(0, 1, H)[:, None, None]
    g = (1 - t) * np.array(top) + t * np.array(bottom)
    return Image.fromarray(np.broadcast_to(g, (H, W, 3)).astype(np.uint8))


def generate(path, duration, seed=0, hue0=0.6, top=(8, 8, 16), bottom=(28, 24, 70)):
    rnd = random.Random(seed)
    cx, cy, R = W / 2, H / 2, 470
    base = _gradient(top, bottom)
    trail = base.copy()
    ImageDraw.Draw(trail).ellipse((cx - R - 8, cy - R - 8, cx + R + 8, cy + R + 8), outline=(255, 255, 255), width=8)

    def reset():
        return [cx + rnd.uniform(-60, 60), cy - 200], [rnd.uniform(-500, 500), 0.0], 22.0

    p, v, r = reset()
    g, hue, steps = 2200.0, hue0, 8
    dt = 1 / FPS / steps
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", str(path)],
        stdin=subprocess.PIPE)
    for _ in range(int(duration * FPS)):
        draw_t = ImageDraw.Draw(trail)
        for _ in range(steps):
            v[1] += g * dt
            p[0] += v[0] * dt
            p[1] += v[1] * dt
            dx, dy = p[0] - cx, p[1] - cy
            d = math.hypot(dx, dy)
            if d + r > R:
                nx, ny = dx / d, dy / d
                dot = v[0] * nx + v[1] * ny
                v[0] -= 2 * dot * nx
                v[1] -= 2 * dot * ny
                p[0], p[1] = cx + nx * (R - r), cy + ny * (R - r)
                r += 7
                hue = (hue + 0.035) % 1
                if r > R * 0.7:
                    trail = base.copy()
                    draw_t = ImageDraw.Draw(trail)
                    draw_t.ellipse((cx - R - 8, cy - R - 8, cx + R + 8, cy + R + 8), outline=(255, 255, 255), width=8)
                    p, v, r = reset()
        col = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.85, 1))
        draw_t.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), outline=col, width=3)
        frame = trail.copy()
        ImageDraw.Draw(frame).ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=col, outline=(255, 255, 255), width=5)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()


if __name__ == "__main__":
    generate("fond_test.mp4", 6)
