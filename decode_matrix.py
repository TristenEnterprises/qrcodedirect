import sys, base64, io
sys.path.insert(0, "/opt/qrcodedirect/backend")
import qrcode
from PIL import Image
from app.qr import render_png

content = "https://qrcodedirect.com/r/your-moment"

# (a) plain library render, default style
q = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=3)
q.add_data(content); q.make(fit=True)
im = q.make_image(fill_color="black", back_color="white")
buf = io.BytesIO(); im.save(buf, "PNG"); open("/tmp/a-plain.png", "wb").write(buf.getvalue())

# (b) our renderer, square dots
png = render_png(content, {"fg": "#0B0B09", "bg": "#FFFFFF", "dots": "square", "scale": 12, "ec": "H"})
open("/tmp/b-square.png", "wb").write(png)

# (c) our renderer, rounded
png = render_png(content, {"fg": "#0B0B09", "bg": "#FFFFFF", "dots": "rounded", "scale": 12, "ec": "H"})
open("/tmp/c-rounded.png", "wb").write(png)

for tag in ("a-plain", "b-square", "c-rounded"):
    raw = open(f"/tmp/{tag}.png", "rb").read()
    open(f"/tmp/{tag}.b64", "w").write(base64.b64encode(raw).decode())
    print(tag, len(raw))
