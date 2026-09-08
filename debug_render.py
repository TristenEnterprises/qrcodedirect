import sys
sys.path.insert(0, "/opt/qrcodedirect/backend")
import qrcode, io
from PIL import Image, ImageChops

content = "https://qrcodedirect.com/r/your-moment"

# plain reference via the library's own image path
q = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=3)
q.add_data(content); q.make(fit=True)
print("modules_count (lib):", q.modules_count)
im = q.make_image(fill_color="black", back_color="white").convert("RGB")

# our renderer square — reproduce core loop inline to inspect
import qrcode
qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=1, border=3)
qr.add_data(content); qr.make(fit=True)
size = qr.modules_count
print("modules_count (ours):", size, "rows len:", len(qr.modules), len(qr.modules[0]))
scale = 12
img = Image.new("RGB", (size * scale, size * scale), (255, 255, 255))
from PIL import ImageDraw
d = ImageDraw.Draw(img)
mods = qr.modules
for y in range(size):
    for x in range(size):
        if mods[y][x]:
            d.rectangle([x*scale, y*scale, x*scale+scale-1, y*scale+scale-1], fill=(11, 11, 9))
print("ours dims:", img.size, "ref dims:", im.size)

# if same dims, diff pixel-for-pixel
if img.size == im.size:
    diff = ImageChops.difference(img.convert("RGB"), im.convert("RGB"))
    bbox = diff.getbbox()
    print("diff bbox:", bbox)
    if bbox:
        # sample some differing regions
        crop = diff.crop(bbox)
        print("diff size:", crop.size)
    import collections
    # count mismatched modules at scale resolution
    mism = 0
    pxo = img.load(); pxr = im.convert("RGB").load()
    for yy in range(size):
        for xx in range(size):
            if pxo[xx*scale, yy*scale] != pxr[xx*scale, yy*scale]:
                mism += 1
    print("mismatched module samples:", mism)
