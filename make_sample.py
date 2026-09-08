import sys
sys.path.insert(0, "/opt/qrcodedirect/backend")
from app.qr import render_png

# premium sample: warm ink on cream, rounded dots + centre logo patch
png = render_png("https://qrcodedirect.com/r/your-moment",
                 {"fg": "#0B0B09", "bg": "#FAF6EE", "dots": "rounded",
                  "scale": 16, "logo": 18, "ec": "H"})
open("/opt/qrcodedirect/sample-qr.png", "wb").write(png)
from PIL import Image
im = Image.open("/opt/qrcodedirect/sample-qr.png")
print("sample saved:", im.size)
