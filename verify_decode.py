import sys
sys.path.insert(0, "/opt/qrcodedirect/backend")
from app.qr import render_png
import base64

content = "https://qrcodedirect.com/r/your-moment"

for tag, style in (
    ("b-square", {"fg": "#0B0B09", "bg": "#FFFFFF", "dots": "square", "scale": 12, "ec": "H"}),
    ("c-rounded", {"fg": "#0B0B09", "bg": "#FFFFFF", "dots": "rounded", "scale": 12, "ec": "H"}),
    ("sample-qr", {"fg": "#0B0B09", "bg": "#FAF6EE", "dots": "rounded", "scale": 16, "logo": 18, "ec": "H"}),
):
    png = render_png(content, style)
    open(f"/tmp/{tag}.png", "wb").write(png)

import cv2
for tag in ("b-square", "c-rounded", "sample-qr"):
    data, pts, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(f"/tmp/{tag}.png"))
    print(tag, "->", data if data else "NO DECODE")
