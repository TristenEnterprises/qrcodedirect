"""QRCodeDirect — styled QR rendering (8 Sep 2026).

Uses python-qrcode (MIT) + Pillow. Style params:
  fg_mode       "solid" | "gradient"      (default "solid")
  fg            hex colour of modules     (default "#0B0B09" ink)
  fg_gradient   [hex1, hex2] for gradient (default ["#0B0B09", "#E85D3F"])
  fg_angle      gradient angle degrees    (default 45)
  bg            hex colour of background  (default "#FFFFFF")
  dots          "square" | "rounded"      (default "rounded")
  logo          null | {data: <data-url>, scale: % of QR width}
  margin        quiet-zone modules        (default 3)
  scale         pixels per module (PNG)   (default 12 — high-res print)
  ec            error correction L/M/Q/H  (default "H" so logos still scan)
"""
import base64
import io
import json

import qrcode
import qrcode.image.svg
from PIL import Image, ImageDraw

INK = "#0B0B09"
PAPER = "#FFFFFF"
ACCENT = "#E85D3F"

DEFAULT_STYLE = {
    "fg_mode": "solid",
    "fg": INK,
    "fg_gradient": [INK, ACCENT],
    "fg_angle": 45,
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

MAX_LOGO_B64 = 1_400_000  # ~1 MB of base64 in the style blob


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


def _gradient_image(size_px: int, colors: list, angle: float) -> Image.Image:
    """Linear gradient across an angle (0 = left→right, 90 = top→bottom)."""
    c1 = _hex_to_rgb((colors or [None, None])[0])
    c2 = _hex_to_rgb((colors or [None, None])[1] if len(colors or []) > 1 else None)
    base = Image.new("RGB", (max(2, size_px), 1))
    for x in range(base.width):
        t = x / (base.width - 1)
        base.putpixel((x, 0), tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    a = angle % 360
    if abs(a - 90) < 0.01:
        return base.resize((1, size_px)).resize((size_px, size_px))
    if abs(a % 180) < 0.01:
        return base.resize((size_px, size_px))
    # oversize + rotate so the whole canvas is covered at any angle.
    # Build the stripe as a full square so non-axis angles fill the canvas
    # (a 1px-tall stripe rotated 135deg leaves only a thin diagonal → black crop).
    diag = int(size_px * 1.5) + 2
    big = base.resize((diag, diag))
    rot = big.rotate(-a, expand=True, resample=Image.BICUBIC)
    # crop centre square
    w, h = rot.size
    left, top = (w - size_px) // 2, (h - size_px) // 2
    return rot.crop((left, top, left + size_px, top + size_px))


def _load_logo(logo) -> Image.Image | None:
    if not logo or not isinstance(logo, dict):
        return None
    data = str(logo.get("data") or "")
    if len(data) > MAX_LOGO_B64 or not data.startswith("data:image/"):
        return None
    try:
        header, b64 = data.split(",", 1)
        raw = base64.b64decode(b64)
        img = Image.open(io.BytesIO(raw))
        img.load()
        if img.mode in ("P", "L"):
            img = img.convert("RGBA")
        elif img.mode == "RGB":
            img = img.convert("RGBA")
        return img
    except Exception:
        return None


def _module_colour(gradient: Image.Image | None, solid: tuple, x0: int, y0: int,
                   mid: int) -> tuple:
    if gradient is None:
        return solid
    return gradient.getpixel((min(gradient.width - 1, x0 + mid), min(gradient.height - 1, y0 + mid)))


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
    real = qr.modules_count  # EXCLUDES the quiet zone
    border = int(s.get("margin", 3))
    total = real + border * 2
    scale = max(4, int(s.get("scale", 12)))
    px = total * scale
    bg_rgb = _hex_to_rgb(s.get("bg"))
    img = Image.new("RGB", (px, px), bg_rgb)
    d = ImageDraw.Draw(img)
    solid = _hex_to_rgb(s.get("fg", INK))
    grad = None
    if str(s.get("fg_mode", "solid")) == "gradient":
        colors = s.get("fg_gradient") or [INK, ACCENT]
        if isinstance(colors, str):
            colors = [colors, ACCENT]
        grad = _gradient_image(px, list(colors)[:2], float(s.get("fg_angle", 45)))
    rounded = str(s.get("dots", "rounded")) != "square"
    mods = qr.modules
    radius = max(1, scale // 3)
    step = 1

    # logo region (punch-out box in real-module coords)
    logo_scale_pct = 0.0
    if s.get("logo") and isinstance(s.get("logo"), dict):
        logo_scale_pct = float(s.get("logo", {}).get("scale", 18))
        logo_scale_pct = max(8, min(28, logo_scale_pct))  # keep it scannable
    punch = int(px * logo_scale_pct / 100 / 2) + int(scale * 0.6)  # half-side + slim pad

    for y in range(real):
        for x in range(real):
            if not mods[y][x]:
                continue
            x0, y0 = (x + border) * scale, (y + border) * scale
            # finder patterns stay square — rounding them hurts scan reliability
            in_finder = (x < 7 and y < 7) or (x >= real - 7 and y < 7) or (x < 7 and y >= real - 7)
            if logo_scale_pct and _overlaps_logo(x0, y0, scale, px, punch):
                continue  # leave blank under the logo backing
            col = _module_colour(grad, solid, x0, y0, scale // 2)
            if rounded and not in_finder:
                d.rounded_rectangle([x0, y0, x0 + scale, y0 + scale], radius=radius, fill=col)
            else:
                d.rectangle([x0, y0, x0 + scale - step, y0 + scale - step], fill=col)

    if logo_scale_pct:
        half = int(px * logo_scale_pct / 100 / 2)
        cx = cy = px // 2
        d.rounded_rectangle([cx - half - 6, cy - half - 6, cx + half + 6, cy + half + 6],
                            radius=8, fill=bg_rgb)
        logo_im = _load_logo(s.get("logo"))
        if logo_im is not None:
            logo_im.thumbnail((half * 2, half * 2), Image.LANCZOS)
            img.paste(logo_im, (cx - logo_im.width // 2, cy - logo_im.height // 2),
                      logo_im if logo_im.mode == "RGBA" else None)
        else:
            # tiny corner tick so a logo slot without image still looks intentional
            d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=_hex_to_rgb(s.get("fg", INK)))

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _overlaps_logo(x0: int, y0: int, scale: int, px: int, punch: int) -> bool:
    cx = cy = px // 2
    mx, my = x0 + scale // 2, y0 + scale // 2
    return abs(mx - cx) < punch and abs(my - cy) < punch


def luminance(hex_colour) -> float:
    """Approximate relative luminance 0..1 of a #rgb/#rrggbb colour."""
    try:
        r, g, b = _hex_to_rgb(hex_colour)
    except Exception:
        return 0.0
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def validate_style(style: dict) -> list[str]:
    """Return human-readable warnings (not errors) for style choices that would
    produce an unscannable QR. Called from the API on create/patch."""
    warnings = []
    if not isinstance(style, dict):
        return ["style must be an object"]
    fg_mode = str(style.get("fg_mode", "solid"))
    logo = style.get("logo")
    has_logo = isinstance(logo, dict) and bool(logo.get("data"))
    if fg_mode == "gradient":
        stops = style.get("fg_gradient") or []
        if isinstance(stops, str):
            stops = [stops]
        lightest = max([luminance(c) for c in stops[:2]], default=0.0)
    else:
        lightest = luminance(style.get("fg"))
    if has_logo and lightest > 0.32:
        warnings.append(
            "With a centre logo the module colour needs to stay dark so the code scans "
            "reliably — pick a darker colour or gradient, or remove the logo.")
    if has_logo:
        try:
            pct = float(logo.get("scale", 18))
            if pct > 26:
                warnings.append("Keep the logo at 26% or smaller or the code may not scan.")
        except Exception:
            pass
    return warnings


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
