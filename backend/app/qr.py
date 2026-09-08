"""QRCodeDirect — styled QR rendering (8 Sep 2026).

Uses python-qrcode (MIT) + Pillow. Style params:
  fg       hex colour of modules        (default "#0B0B09" ink)
  bg       hex colour of background     (default "#FFFFFF")
  dots     "square" | "rounded"         (default "rounded")
  logo     optional: size ratio of centre logo, "auto" placeholder for brand mark
  margin   quiet-zone modules           (default 3)
  scale    pixels per module (PNG)      (default 12 — high-res print)
  ec       error correction L/M/Q/H     (default "H" so logos still scan)
"""
import io
import json

import qrcode
import qrcode.image.svg
from PIL import Image, ImageDraw

INK = "#0B0B09"
PAPER = "#FFFFFF"

DEFAULT_STYLE = {
    "fg": INK,
    "bg": PAPER,
    "dots": "rounded",
    "logo": None,
    "margin": 3,
    "scale": 12,
    "ec": "H",
}

EC_LEVELS = {"L": qrcode.constants.ERROR_CORRECT_L,
             "M": qrcode.constants.ERROR_CORRECT_M,
             "Q": qrcode.constants.ERROR_CORRECT_Q,
             "H": qrcode.constants.ERROR_CORRECT_H}


def merge_style(style) -> dict:
    base = dict(DEFAULT_STYLE)
    if style:
        if isinstance(style, str):
            try:
                style = json.loads(style)
            except Exception:
                style = {}
        if isinstance(style, dict):
            base.update(style)
    return base


def _hex_to_rgb(h: str):
    h = (h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (11, 11, 9)


def _svg_color(h: str) -> str:
    h = (h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return "#" + h if h else "#0B0B09"


def render_png(content: str, style: dict) -> bytes:
    s = merge_style(style)
    ec = EC_LEVELS.get(str(s.get("ec", "H")).upper(), qrcode.constants.ERROR_CORRECT_H)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ec,
        box_size=1,           # draw modules 1px, scale up manually for crisp geometry
        border=int(s.get("margin", 3)),
    )
    qr.add_data(content)
    qr.make(fit=True)
    size = qr.modules_count
    scale = max(4, int(s.get("scale", 12)))
    px = size * scale
    img = Image.new("RGB", (px, px), _hex_to_rgb(s.get("bg")))
    d = ImageDraw.Draw(img)
    fg = _hex_to_rgb(s.get("fg", INK))
    rounded = str(s.get("dots", "rounded")) != "square"
    mods = qr.modules
    radius = max(1, scale // 3)
    step = 1
    for y in range(size):
        for x in range(size):
            if not mods[y][x]:
                continue
            x0, y0 = x * scale, y * scale
            if rounded:
                d.rounded_rectangle([x0, y0, x0 + scale, y0 + scale], radius=radius, fill=fg)
            else:
                d.rectangle([x0, y0, x0 + scale - step, y0 + scale - step], fill=fg)
    # centre logo placeholder (soft "mark" patch). Real logos drop in via the logo param later.
    logo_pct = float(s.get("logo") or 0)
    if 0 < logo_pct <= 40:
        side = int(px * logo_pct / 100)
        half = side // 2
        cx = cy = px // 2
        d.rounded_rectangle([cx - half - 6, cy - half - 6, cx + half + 6, cy + half + 6],
                            radius=10, fill=_hex_to_rgb(s.get("bg")))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def render_svg(content: str, style: dict) -> bytes:
    s = merge_style(style)
    ec = EC_LEVELS.get(str(s.get("ec", "H")).upper(), qrcode.constants.ERROR_CORRECT_H)
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=None,
        error_correction=ec,
        box_size=8,
        border=int(s.get("margin", 3)),
        image_factory=factory,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color=_svg_color(s.get("fg")), back_color=_svg_color(s.get("bg")))
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()
