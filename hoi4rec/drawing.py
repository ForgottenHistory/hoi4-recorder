"""Small drawing helpers for province maps (shared by the recorder's map tools and the planner's heatmaps)."""
import os

import numpy as np
from PIL import Image, ImageFont

SEA = (172, 198, 222)


def ramp(stops, x):
    x = min(max(x, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(x), len(stops) - 2)
    f = x - i
    return tuple(int(a + (b - a) * f) for a, b in zip(stops[i], stops[i + 1]))


def font(size):
    for name in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name), size)
        except OSError:
            pass
    return ImageFont.load_default()


def panel(ids, crop, scale, colours, base):
    """Colour each province pixel by colours.get(id, base(id)), draw province and controller borders."""
    y0, y1, x0, x1 = crop
    sub = ids[y0:y1, x0:x1]
    uniq, inv = np.unique(sub, return_inverse=True)
    lut = np.array([colours.get(int(u), base(int(u))) for u in uniq], np.uint8)
    rgb = lut[inv.reshape(sub.shape)]
    edge = np.zeros(sub.shape, bool)
    edge[:, 1:] |= sub[:, 1:] != sub[:, :-1]
    edge[1:, :] |= sub[1:, :] != sub[:-1, :]
    rgb[edge] = (rgb[edge] * 0.72).astype(np.uint8)
    img = Image.fromarray(rgb, "RGB")
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)
