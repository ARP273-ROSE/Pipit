#!/usr/bin/env python3
"""Logo de Pipit : UNE source SVG (logo.svg), tout le reste en est rendu.

    QT_QPA_PLATFORM=offscreen python make_logo.py      (PyQt6 + Pillow)

Le symbole « éjecter » en blanc sur fond vert olive, un pipit perché sur sa
pointe. À 16 pixels (zone près de l'horloge) seul le symbole reste lisible :
c'est voulu. Sorties : logo.svg (la source), logo_{16,32,64,128,256,512}.png,
logo.png (= 256) et logo.ico (installeur Windows, multi-tailles).
"""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
OLIVE_CLAIR, OLIVE, OLIVE_NUIT, BLANC, BRUN = "#7FA04A", "#4E6E2A", "#2F4518", "#FFFFFF", "#6B4A2B"

# pipit stylisé, de profil, tourné vers la droite, pattes sur la pointe (256, 150)
PIPIT = ("M206,118 C214,96 240,86 262,92 C276,80 296,80 304,92 L322,96 L304,104 "
         "C306,124 292,142 268,148 L262,150 L250,150 C232,148 214,140 200,128 "
         "L150,124 L196,112 Z")


def construire_svg() -> str:
    n = 512
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{n}" height="{n}" viewBox="0 0 {n} {n}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="fond" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{OLIVE_CLAIR}"/>
      <stop offset="0.55" stop-color="{OLIVE}"/>
      <stop offset="1" stop-color="{OLIVE_NUIT}"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="480" height="480" rx="104" fill="url(#fond)"/>
  <polygon points="256,150 404,322 108,322" fill="{BLANC}" stroke="{BLANC}" stroke-width="18" stroke-linejoin="round"/>
  <rect x="108" y="356" width="296" height="54" rx="14" fill="{BLANC}"/>
  <path d="{PIPIT}" fill="{BRUN}" stroke="{BLANC}" stroke-width="6" stroke-linejoin="round"/>
  <circle cx="284" cy="102" r="6" fill="{BLANC}"/>
</svg>
'''


def rendre(svg: Path, sortie: Path, taille: int) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    img = QImage(taille, taille, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    QSvgRenderer(str(svg)).render(p, QRectF(0, 0, taille, taille))
    p.end()
    img.save(str(sortie), "PNG")


def main():
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)  # noqa: F841 — requis pour le rendu
    svg = ICI / "logo.svg"
    svg.write_text(construire_svg(), encoding="utf-8")
    for taille in (16, 32, 64, 128, 256, 512):
        rendre(svg, ICI / f"logo_{taille}.png", taille)
    (ICI / "logo.png").write_bytes((ICI / "logo_256.png").read_bytes())
    from PIL import Image
    img = Image.open(ICI / "logo_512.png").convert("RGBA")
    img.save(ICI / "logo.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                      (64, 64), (128, 128), (256, 256)])
    print("logo.svg -> logo_*.png, logo.png, logo.ico")


if __name__ == "__main__":
    main()
