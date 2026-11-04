"""crop.py IMAGE X0 Y0 X1 Y1 [SCALE] OUT: saves the box of IMAGE, enlarged SCALE times (default 2), to OUT."""

import sys

from PIL import Image

img, x0, y0, x1, y1 = sys.argv[1], *map(int, sys.argv[2:6])
scale = float(sys.argv[6]) if len(sys.argv) > 7 else 2.0
out = sys.argv[-1]
im = Image.open(img).crop((x0, y0, x1, y1))
im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS).save(out)
print(out, im.width, im.height)
