"""Generate assets/icon.ico (needs Pillow; only run when you want to redraw the icon)."""
import os
from PIL import Image, ImageDraw

S = 512
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((16, 16, S - 16, S - 16), radius=110, fill=(20, 35, 26, 255))
d.ellipse((76, 76, S - 76, S - 76), outline=(92, 255, 122, 255), width=26)          # timer ring
d.pieslice((76, 76, S - 76, S - 76), start=-90, end=150, fill=(46, 139, 87, 255))     # elapsed wedge
d.ellipse((140, 140, S - 140, S - 140), fill=(20, 35, 26, 255))
# leaf
leaf = [(256, 175), (320, 215), (340, 270), (300, 335), (256, 350), (212, 335), (172, 270), (192, 215)]
d.polygon(leaf, fill=(105, 255, 71, 255))
d.line((256, 350, 256, 205), fill=(20, 35, 26, 255), width=10)
out = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
im.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", os.path.abspath(out))
