#!/usr/bin/env python3
"""Summit OS photo wallpapers: real mountain photographs, each as a light (day) and dark (night) picture.

usage: photowalls.py <sources dir> <out dir>      (writes summit-<name>-{light,dark}.jpg, blur/ and thumbs/)

Where a real night photograph of the same place exists it is used; otherwise the night picture is the
day photograph graded to moonlight (darker, cooler, less saturated, sky darkest). Sources and credits:
see /usr/share/backgrounds/summitos/CREDITS.
"""
import sys, os
import numpy as np
from PIL import Image, ImageFilter
Image.MAX_IMAGE_PIXELS = None
W, H = 1920, 1080
E = "elementary-wp/backgrounds/"; P = "pop-os-wp/original/"; K = "plasma/x/usr/share/wallpapers/"
# name: (light source, dark source or None = grade the light one, vertical focus 0..1 for each)
SETS = {
    "summit":    (K + "Mountain/contents/images/5120x2880.png", K + "Mountain/contents/images_dark/5120x2880.png", 0.5, 0.5),
    "peaks":     (E + "Canazei Granite Ridges.jpg", None, 0.45, 0.45),
    "yosemite":  (E + "Photo of Valley.jpg", E + "Snow-Capped Mountain.jpg", 0.4, 0.45),
    "lake":      (E + "A Large Body of Water Surrounded By Mountains.jpg", None, 0.35, 0.35),
    "highlands": (P + "sean-afnan-244576.jpg", None, 0.55, 0.55),
    "desert":    (P + "jasper-van-der-meij-97274-edit.jpg", P + "jad-limcaco-183877.jpg", 0.45, 0.4),
    "dunes":     (E + "A Trail of Footprints In The Sand.jpg", P + "jared-evans-119758.jpg", 0.5, 0.55),
    "coast":     (E + "odin.jpg", E + "odin-dark.jpg", 0.5, 0.5),
}

def fit(path, focus):
    im = Image.open(path).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = (im.width - W) // 2; y = round((im.height - H) * focus)
    return im.crop((x, y, x + W, y + H))

def night(im):
    """Moonlight grade of a daytime photograph."""
    a = np.asarray(im, float) / 255
    lum = (a * [0.2126, 0.7152, 0.0722]).sum(2, keepdims=True)
    a = lum + (a - lum) * 0.55                                   # less colour
    a = a ** 1.35                                                # deeper shadows, highlights kept
    a *= np.array([0.42, 0.52, 0.74])                            # cool, dim
    # the sky (bright, smooth, upper part) goes darkest, with a gentle top-to-horizon gradient
    y = np.linspace(0, 1, H)[:, None, None]
    smooth = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(14)), float)[..., None] / 255
    sky = np.clip((smooth - 0.55) / 0.25, 0, 1) * np.clip((0.75 - y) / 0.35, 0, 1)
    a *= 1 - 0.45 * sky * (1 - 0.6 * y)
    a += np.array([0.012, 0.016, 0.03])
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype("uint8"))

def calm(im, dark):
    """Keep the menu bar and desktop icons readable: no blown highlights at the very top."""
    a = np.asarray(im, float) / 255
    y = np.linspace(0, 1, H)[:, None, None]
    a *= 1 - (0.10 if dark else 0.05) * np.clip(1 - y / 0.12, 0, 1)
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype("uint8"))

def main(src, out):
    for d in ("", "blur", "thumbs"): os.makedirs(os.path.join(out, d), exist_ok=True)
    for name, (light, dark, fl, fd) in SETS.items():
        L = fit(os.path.join(src, light), fl)
        D = fit(os.path.join(src, dark), fd) if dark else night(L)
        for im, mode in ((L, "light"), (D, "dark")):
            im = calm(im, mode == "dark")
            base = f"summit-{name}-{mode}"
            im.save(f"{out}/{base}.jpg", quality=90, optimize=True, progressive=True)
            im.resize((480, 270), Image.LANCZOS).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BICUBIC) \
              .save(f"{out}/blur/{base}.jpg", quality=80)
            im.resize((240, 135), Image.LANCZOS).save(f"{out}/thumbs/{base}.png", optimize=True)
        print(name)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
