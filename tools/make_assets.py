#!/usr/bin/env python3
"""Genera los recursos de la interfaz a partir de tools/source.png (la ilustración de Kage no Michi).

Requiere: opencv-python-headless, numpy, pillow.
Uso: python3 tools/make_assets.py

La ilustración (1536×1024) lleva pintados el logotipo, una barra de título y los cinco botones del
menú a la derecha. El logotipo se queda en el fondo (se superpone a la luna y no se puede separar
limpiamente); los botones se recortan como sprites y se borran del fondo.
"""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "ui")
src = cv2.imread(os.path.join(HERE, "source.png"), cv2.IMREAD_COLOR)
H, W = src.shape[:2]
assert (W, H) == (1536, 1024), (W, H)

# Botones en la ilustración (x0, y0, x1, y1): JUGAR (rojo) y los oscuros.
JUGAR = (1022, 384, 1468, 474)
DARK = [(1032, 484, 1458, 570), (1032, 579, 1458, 665), (1032, 674, 1458, 760), (1032, 769, 1458, 855)]
ICON_BOXES = {  # icono de cada botón (x0, y0, x1, y1)
    "icon_play": (1084, 402, 1142, 460),
    "icon_options": (1084, 500, 1140, 556),
    "icon_achievements": (1086, 597, 1138, 649),
    "icon_credits": (1088, 692, 1139, 743),
    "icon_quit": (1092, 785, 1146, 836),
}


def lum(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)


def text_mask(region, lo, keep_edges):
    """Píxeles claros del interior (texto e icono), sin tocar el trazo del borde."""
    L = lum(region)
    b, g, r = [region[:, :, i].astype(np.float32) for i in range(3)]
    m = ((L > lo) & (r - b < 90)).astype(np.uint8) * 255
    t, bt, lft, rgt = keep_edges
    m[:t, :] = 0
    m[-bt:, :] = 0
    m[:, :lft] = 0
    m[:, -rgt:] = 0
    return cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=2)


# --- 1) Botón seleccionado: la pincelada roja de JUGAR, sin icono ni texto, con alfa ---------------
x0, y0, x1, y1 = JUGAR
red = src[y0:y1, x0:x1].copy()
red_clean = cv2.inpaint(red, text_mask(red, 140, (14, 14, 60, 60)), 6, cv2.INPAINT_TELEA)
b, g, r = [red_clean[:, :, i].astype(np.float32) for i in range(3)]
redness = np.clip((r - np.maximum(g, b) - 10) / 45.0, 0, 1)
body = (redness > 0.3).astype(np.uint8) * 255
body = cv2.morphologyEx(body, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
cnts, _ = cv2.findContours(body, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
solid = np.zeros_like(body)
cv2.drawContours(solid, [c for c in cnts if cv2.contourArea(c) > 2000], -1, 255, -1)
solid = cv2.erode(solid, np.ones((5, 5), np.uint8))
# el interior del botón es oscuro: también forma parte del sprite
alpha = np.maximum(redness, solid.astype(np.float32) / 255.0)
alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
cv2.imwrite(os.path.join(OUT, "btn_selected.png"), np.dstack([red_clean, (alpha * 255).astype(np.uint8)]))

# --- 2) Iconos: claros sobre oscuro → alfa por luminancia; el shader los tiñe -------------------
for name, (ix0, iy0, ix1, iy1) in ICON_BOXES.items():
    crop = src[iy0:iy1, ix0:ix1].copy()
    L = lum(crop)
    b, g, r = [crop[:, :, i].astype(np.float32) for i in range(3)]
    sat = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    on_red = name == "icon_play"
    lo, span = (95, 100) if on_red else (60, 80)
    a = np.clip((L - lo) / span, 0, 1) * np.clip(1.0 - (sat - 45) / 60.0, 0, 1)
    gray = np.clip(L * (1.1 if on_red else 1.4), 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(OUT, name + ".png"), np.dstack([gray, gray, gray, (a * 255).astype(np.uint8)]))

# --- 3) Botón oscuro suelto (menús, pausa y diálogos): OPCIONES sin texto ni icono ---------------
x0, y0, x1, y1 = DARK[0]
dark = src[y0:y1, x0:x1].copy()
dark = cv2.inpaint(dark, text_mask(dark, 90, (14, 14, 60, 70)), 7, cv2.INPAINT_TELEA)
L = lum(dark)
h, w = L.shape
fa = np.zeros((h, w), np.float32)
fa[6:-6, 10:-10] = 1.0
fa = cv2.GaussianBlur(fa, (0, 0), 4)
a = np.maximum(fa * 0.92, np.clip((L - 60) / 80.0, 0, 1) * fa.clip(0.3, 1))
cv2.imwrite(os.path.join(OUT, "btn_normal.png"), np.dstack([dark, (a * 255).astype(np.uint8)]))

# --- 4) Fondo sin botones (el menú los dibuja encima) -------------------------------------------
clean = src.copy()
mask = np.zeros((H, W), np.uint8)
for (bx0, by0, bx1, by1) in [JUGAR] + DARK:
    mask[by0 - 14:by1 + 10, bx0 - 30:bx1 + 22] = 255
small = cv2.resize(clean, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
small_mask = cv2.resize(mask, (W // 4, H // 4), interpolation=cv2.INTER_NEAREST)
filled = cv2.resize(cv2.inpaint(small, small_mask, 10, cv2.INPAINT_TELEA), (W, H), interpolation=cv2.INTER_CUBIC)
# el resplandor rojo de JUGAR no debe teñir el relleno: se lleva hacia el azul oscuro del bosque
fb, fg, fr = [filled[:, :, i].astype(np.float32) for i in range(3)]
gray = (fb + fg + fr) / 3.0
filled = np.dstack([gray * 1.05, gray * 0.95, np.minimum(fr, gray * 1.1)]) * 0.75
rng = np.random.default_rng(7)
noise = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 2.0)
filled = np.clip(filled * (1.0 + noise[..., None] * 0.4), 0, 255)
soft = np.clip(cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 18) * 1.5, 0, 1)[..., None]
clean = (filled * soft + clean.astype(np.float32) * (1 - soft)).astype(np.uint8)
# barra de título pintada en la ilustración: se sustituye por la fila inferior repetida
clean[:40] = clean[40:41]
cv2.imwrite(os.path.join(OUT, "background_clean.jpg"), clean, [cv2.IMWRITE_JPEG_QUALITY, 94])

# --- 5) Máscara de agua: el reflejo de la luna en el arroyo ondula ligeramente ------------------
b, g, r = [src[:, :, i].astype(np.float32) for i in range(3)]
L = lum(src)
water = np.clip((L - 70) / 90.0, 0, 1) * np.clip((b - r + 10) / 40.0, 0, 1)
zone = np.zeros((H, W), np.float32)
pts = np.array([[820, 1024], [850, 860], [900, 790], [960, 760], [1040, 790], [1080, 900], [1100, 1024]], np.int32)
cv2.fillPoly(zone, [pts], 1.0)
zone = cv2.GaussianBlur(zone, (0, 0), 12)
water = cv2.GaussianBlur(water * zone, (0, 0), 2)
cv2.imwrite(os.path.join(OUT, "fire_mask.png"), (np.clip(water * 1.5, 0, 1) * 255).astype(np.uint8))
print("Recursos generados en", os.path.abspath(OUT))
