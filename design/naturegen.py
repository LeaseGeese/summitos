#!/usr/bin/env python3
"""Summit OS nature wallpapers: illustrated landscapes built from layered silhouettes.

  python3 design/naturegen.py OUTDIR [WIDTH HEIGHT] [scene ...]

Each scene renders as a day (-light) and a dusk/night (-dark) picture. Layers are drawn back to front; each
one is a noise-shaped silhouette with its own gradient, a soft light/shade side, and atmospheric haze that
fades distant layers into the sky. Edges are anti-aliased analytically and a fine grain dithers the gradients.
"""
import sys, math
import numpy as np
from PIL import Image, ImageFilter

# ------------------------------------------------------------------ noise
def _hash(i, seed):
    h = (i.astype(np.int64) * 374761393 + seed * 668265263 + 1013904223) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF).astype(np.float64) / float(0xFFFFFF)

def noise1(x, seed=0):
    i = np.floor(x); f = x - i; u = f * f * f * (f * (f * 6 - 15) + 10)
    a = _hash(i, seed); b = _hash(i + 1, seed)
    return a + (b - a) * u

def fbm1(x, octaves=6, seed=0, gain=0.5, lac=2.0):
    s = 0; amp = 1; tot = 0
    for o in range(octaves):
        s = s + amp * noise1(x, seed + o * 13); tot += amp; x = x * lac + 7.3; amp *= gain
    return s / tot

def ridge1(x, octaves=7, seed=0, gain=0.55, sharp=1.0):
    """Mountain profile: folded noise gives peaks with crisp tops and soft valleys."""
    s = 0; amp = 1; tot = 0
    for o in range(octaves):
        n = 1 - np.abs(noise1(x, seed + o * 13) * 2 - 1)
        s = s + amp * n ** (1 + sharp * (o == 0)); tot += amp; x = x * 2.1 + 3.7; amp *= gain
    return s / tot

def _hash2(ix, iy, seed):
    h = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF).astype(np.float32) / float(0xFFFFFF)

def noise2(x, y, seed=0):
    ix = np.floor(x); iy = np.floor(y); fx = (x - ix).astype(np.float32); fy = (y - iy).astype(np.float32)
    ux = fx * fx * (3 - 2 * fx); uy = fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy, seed); b = _hash2(ix + 1, iy, seed); c = _hash2(ix, iy + 1, seed); d = _hash2(ix + 1, iy + 1, seed)
    return (a + (b - a) * ux) * (1 - uy) + (c + (d - c) * ux) * uy

def fbm2(x, y, octaves=5, seed=0):
    s = 0; amp = 1; tot = 0
    for o in range(octaves):
        s = s + amp * noise2(x, y, seed + o * 7); tot += amp; x = x * 2.02 + 1.3; y = y * 2.02 - 0.7; amp *= 0.5
    return s / tot

def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

def C(h):
    h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255

def lerp(a, b, t):
    t = np.asarray(t, np.float32)
    return a + (b - a) * (t[..., None] if t.ndim else t)

def blur(a, r):
    return np.array(Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), np.float32) / 255

# ------------------------------------------------------------------ canvas
class Canvas:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.x = np.arange(W, dtype=np.float64) / W                  # 0..1 across
        self.yy = np.arange(H, dtype=np.float32)[:, None] / H        # 0..1 down
        self.img = np.zeros((H, W, 3), np.float32)

    def gradient(self, stops):
        """Vertical gradient. stops: [(y, colour), ...] in 0..1."""
        y = self.yy[:, 0]; out = np.zeros((self.H, 3), np.float32)
        out[:] = stops[-1][1]
        for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
            m = (y >= y0) & (y <= y1)
            if m.any(): out[m] = lerp(c0, c1, ss(y0, y1, y[m]) if y1 > y0 else np.zeros(m.sum(), np.float32))
        out[y < stops[0][0]] = stops[0][1]
        self.img[:] = out[:, None, :]

    def glow(self, cx, cy, colour, strength, falloff=4.0, core=0.0, core_falloff=16.0):
        d = np.sqrt(((self.x[None, :] - cx) * self.W / self.H) ** 2 + (self.yy - cy) ** 2).astype(np.float32)
        g = np.exp(-d * falloff) * strength + np.exp(-d * core_falloff) * core
        self.img += colour * g[..., None]

    def disc(self, cx, cy, r, colour, soft=1.5):
        d = np.sqrt(((self.x[None, :] - cx) * self.W) ** 2 + ((self.yy - cy) * self.H) ** 2).astype(np.float32)
        a = np.clip((r * self.H - d) / soft + 0.5, 0, 1)
        self.img = lerp(self.img, np.broadcast_to(colour, self.img.shape), a)

    def layer(self, top, c_top, c_bot, depth=0.25, haze=None, haze_amt=0.0, light=None, light_amt=0.0,
              texture=0.0, seed=0, rim=None, rim_amt=0.0, bottom=None):
        """Fill everything below the curve `top` (0..1 per column). Colour runs c_top -> c_bot over `depth`
        of the screen height. `light` is a per-column 0..1 shade factor (sun side); haze fades toward a colour."""
        ytop = top[None, :].astype(np.float32)
        cov = np.clip((self.yy - ytop) * self.H + 0.5, 0, 1)        # analytic anti-aliasing of the edge
        if bottom is not None:
            cov = cov * np.clip((np.asarray(bottom, np.float32)[None, :] if np.ndim(bottom) else bottom) * self.H - self.yy * self.H + 0.5, 0, 1)
        if not cov.any(): return
        below = (self.yy - ytop).clip(0)
        col = lerp(c_top, c_bot, ss(0, 1, below / depth))
        if light is not None:
            # shading spreads out and softens with distance below the ridge, so faces read as broad planes
            # instead of vertical stripes: average the ridge light over a window that widens with depth
            Wn = self.W; cs = np.concatenate([[0], np.cumsum(light - 0.5)])
            half = (2 + below * Wn * 0.45).astype(np.int64)
            xi = np.arange(Wn)[None, :]
            lo = np.clip(xi - half, 0, Wn); hi = np.clip(xi + half + 1, 0, Wn)
            sh = (cs[hi] - cs[lo]) / np.maximum(hi - lo, 1)
            sh = sh * np.exp(-below / (depth * 1.1))
            col = col * (1 + light_amt * sh[..., None].astype(np.float32) * 2)
        if rim is not None:
            col = col + rim * rim_amt * np.exp(-below * self.H / 2.5)[..., None]
        if texture:
            n = fbm2(self.x[None, :] * 260, self.yy * 260 * self.H / self.W, 3, seed)
            col = col * (1 + (n[..., None] - 0.5) * texture)
        if haze is not None and haze_amt:
            col = lerp(col, haze, haze_amt)
        self.img = lerp(self.img, col, cov)

    def mist(self, y0, y1, colour, amount, seed=99):
        y = self.yy; mid = (y0 + y1) / 2
        m = ss(y0, mid, y) * (1 - ss(mid, y1, y)) * amount
        m = m * (0.55 + 0.9 * fbm2(self.x[None, :] * 5, y * 25, 4, seed))
        self.img = lerp(self.img, np.broadcast_to(colour, self.img.shape), np.clip(m, 0, 1))

    def stars(self, seed, until=0.6, density=0.0011, colour=(1, 1, 1)):
        rng = np.random.default_rng(seed)
        n = int(self.W * self.H * density)
        xs = rng.integers(0, self.W, n); ys = (rng.random(n) ** 1.4 * until * self.H).astype(int)
        b = ((rng.random(n) ** 5) * 1.6 + 0.12).astype(np.float32)
        s = np.zeros((self.H, self.W), np.float32); np.maximum.at(s, (ys, xs), b)
        s = blur(np.clip(s, 0, 1), 0.65) * 2.8
        s *= ss(until, until * 0.35, self.yy)
        self.img += np.clip(s, 0, 1)[..., None] * np.array(colour, np.float32)

    def clouds(self, y0, y1, colour, amount, seed, scale=3.0, cover=0.55, shade=None):
        y = self.yy; x = self.x[None, :]
        band = ss(y0, y0 + (y1 - y0) * 0.3, y) * (1 - ss(y0 + (y1 - y0) * 0.55, y1, y))
        # clouds stretch out and thin toward the horizon
        persp = 1 + 3 * ss(y0, y1, y)
        n = fbm2(x * scale * 2.0, y * scale * 5 * persp, 6, seed)
        c = blur(ss(cover, cover + 0.25, n) * band, self.H / 500)
        col = np.broadcast_to(colour, self.img.shape)
        if shade is not None:      # bellies are darker than sunlit tops
            n2 = fbm2(x * scale * 2.0, (y - 0.03) * scale * 5 * persp, 6, seed)
            top = blur(ss(cover, cover + 0.25, n2) * band, self.H / 500)
            belly = np.clip((c - top) * 3 + 0.35, 0, 1)
            col = lerp(col, np.broadcast_to(shade, self.img.shape), belly)
        self.img = lerp(self.img, col, c * amount)

    def finish(self, seed=1, vignette=0.16, grain=1.1):
        H, W = self.H, self.W
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx / W - 0.5) * 1.25) ** 2 + (yy / H - 0.5) ** 2)
        img = self.img * (1 - vignette * ss(0.38, 0.95, d))[..., None]
        rng = np.random.default_rng(seed)
        img8 = np.clip(img, 0, 1) * 255 + rng.normal(0, grain, img.shape)
        return Image.fromarray(np.clip(img8 + 0.5, 0, 255).astype(np.uint8))

def profile_light(top, sun_from_left=True, width=9):
    """Shade factor from a silhouette's slope: faces turned to the sun are light, the others in shade."""
    d = np.gradient(top) * len(top)
    s = np.tanh(-d * (1 if sun_from_left else -1) * 1.5)
    s = np.convolve(s, np.ones(width) / width, mode="same")
    return 0.5 + 0.5 * s

# ------------------------------------------------------------------ scenes
def peaks(W, H, dark):
    c = Canvas(W, H); x = c.x
    if not dark:
        c.gradient([(0, C("#2f6fd6")), (0.38, C("#7fb2ec")), (0.60, C("#d9e9f8")), (1, C("#eef5fb"))])
        c.glow(0.22, 0.26, C("#fff4dc"), 0.20, 3.2, 0.35, 20)
        c.clouds(0.04, 0.40, C("#ffffff"), 0.85, 5, cover=0.58, shade=C("#c4d4ec"))
        haze = C("#dbe8f6"); rim = C("#ffffff")
        layers = [  # (base y, height, colour top, colour bottom, haze, light amount, seed, sharpness)
            (0.52, 0.30, C("#f3f6fc"), C("#9fb4d4"), 0.20, 0.55, 3, 1.4),
            (0.61, 0.20, C("#8ea7cc"), C("#5f7aa6"), 0.18, 0.45, 8, 1.0),
            (0.71, 0.15, C("#557ca0"), C("#2e5577"), 0.10, 0.35, 12, 0.8),
            (0.81, 0.11, C("#2f6a5c"), C("#1a4639"), 0.04, 0.25, 15, 0.4),
            (0.91, 0.08, C("#1c4a37"), C("#0e2a1f"), 0.00, 0.20, 19, 0.2),
        ]
    else:
        c.gradient([(0, C("#060a1e")), (0.35, C("#141c48")), (0.60, C("#3d3f7c")), (1, C("#6a5d96"))])
        c.stars(4, 0.55)
        c.glow(0.78, 0.15, C("#aab8ff"), 0.10, 5, 0.25, 26)
        c.disc(0.78, 0.15, 0.022, C("#f4f6ff"))
        haze = C("#4a4a85"); rim = C("#c9d2ff")
        layers = [
            (0.52, 0.30, C("#c3cbee"), C("#4b5287"), 0.20, 0.60, 3, 1.4),
            (0.61, 0.20, C("#4a5089"), C("#2a2f5f"), 0.18, 0.40, 8, 1.0),
            (0.71, 0.15, C("#29305e"), C("#181d40"), 0.10, 0.30, 12, 0.8),
            (0.81, 0.11, C("#16213d"), C("#0c1428"), 0.04, 0.20, 15, 0.4),
            (0.91, 0.08, C("#0b1324"), C("#050a14"), 0.00, 0.15, 19, 0.2),
        ]
    for i, (base, amp, ct, cb, hz, la, seed, sharp) in enumerate(layers):
        top = base - amp * ridge1(x * (2.2 + i * 1.3) + seed, 7, seed, 0.5 - i * 0.03, sharp) ** (1.6 - i * 0.12)
        if i == 0:   # the hero range: one tall summit right of centre
            top = top - 0.11 * np.exp(-((x - 0.63) / 0.10) ** 2) * (0.7 + 0.3 * fbm1(x * 30, 4, 7))
        c.layer(top, ct, cb, depth=amp * 1.3 + 0.05, haze=haze, haze_amt=hz, light=profile_light(top, not dark),
                light_amt=la, texture=0.05, seed=seed, rim=rim if i == 0 else None, rim_amt=0.10)
        if i in (0, 1, 2): c.mist(base - 0.03, base + 0.07, haze, 0.40 - i * 0.08, seed=300 + i)
    return c.finish(2, vignette=0.10 if not dark else 0.24)

def dunes(W, H, dark):
    c = Canvas(W, H); x = c.x
    if not dark:
        c.gradient([(0, C("#4a8fdb")), (0.35, C("#9cc6ee")), (0.55, C("#f6dcc0")), (1, C("#f3c497"))])
        c.glow(0.84, 0.48, C("#ffe1b0"), 0.30, 3.5, 0.6, 18)
        sand = [(C("#f6cf9f"), C("#dfa06a")), (C("#f1b97f"), C("#d48a52")), (C("#eaa362"), C("#c06c38")),
                (C("#e0904d"), C("#a85827")), (C("#d47f3f"), C("#8f441c"))]
        haze = C("#f6d7b8")
    else:
        c.gradient([(0, C("#05081c")), (0.35, C("#151a46")), (0.55, C("#3e3266")), (1, C("#6b4a6e"))])
        c.stars(9, 0.52)
        c.glow(0.2, 0.18, C("#b4c0ff"), 0.08, 5, 0.2, 26); c.disc(0.2, 0.18, 0.018, C("#f6f2ff"))
        sand = [(C("#76628f"), C("#463a68")), (C("#64527f"), C("#352c56")), (C("#52436d"), C("#28224a")),
                (C("#40345c"), C("#1c1836")), (C("#30284a"), C("#121026"))]
        haze = C("#4f3f6e")
    bases = [0.56, 0.635, 0.72, 0.81, 0.92]
    for i, b in enumerate(bases):
        u = x * (1.3 + i * 0.6) + i * 3.1
        # dunes: long swells topped by crests; the crest is sharp where the wind side meets the slip face
        swell = fbm1(u, 3, 30 + i, 0.45)
        ph = u * math.pi * 1.1 + fbm1(u * 0.6, 2, 40 + i) * 2.5
        saw = (ph / math.pi) % 1.0
        crest = np.where(saw < 0.66, ss(0, 0.66, saw), 1 - ss(0.66, 1.0, saw))     # gentle rise, short steep fall
        top = b - (0.045 + i * 0.012) * (swell * 1.2 + crest * 1.0)
        ct, cb = sand[i]
        lit = profile_light(top, sun_from_left=False, width=5)
        lit = np.where(lit < 0.45, lit * 0.55, lit)       # slip faces fall into deep shade
        c.layer(top, ct, cb, depth=0.10 + i * 0.03, haze=haze, haze_amt=max(0, 0.30 - i * 0.08),
                light=lit, light_amt=0.6, texture=0.05, seed=50 + i)
    return c.finish(3, vignette=0.12 if not dark else 0.26)

def hills(W, H, dark):
    c = Canvas(W, H); x = c.x
    if not dark:
        c.gradient([(0, C("#4f9ae8")), (0.40, C("#a6d0f4")), (0.62, C("#eaf4fb")), (1, C("#f3f8fb"))])
        c.glow(0.70, 0.16, C("#fffbe6"), 0.20, 3.0, 0.3, 18)
        c.clouds(0.04, 0.46, C("#ffffff"), 0.95, 21, scale=2.2, cover=0.55, shade=C("#cddcee"))
        greens = [(C("#b3cfae"), C("#8db291")), (C("#99c77a"), C("#64a056")), (C("#7fba5d"), C("#4d8e3e")),
                  (C("#63a845"), C("#38782f")), (C("#4c9437"), C("#255c20"))]
        haze = C("#dcebf3")
    else:
        c.gradient([(0, C("#0b1430")), (0.36, C("#2c3a78")), (0.55, C("#c27a93")), (0.66, C("#f2a582")), (1, C("#f6b98a"))])
        c.glow(0.30, 0.62, C("#ffb37a"), 0.30, 3.0, 0.4, 14)
        c.clouds(0.10, 0.45, C("#f19aa6"), 0.6, 21, scale=2.2, cover=0.6, shade=C("#5b4a8a"))
        greens = [(C("#7a6a9a"), C("#5a4f7e")), (C("#55608a"), C("#3a4466")), (C("#384b66"), C("#24334b")),
                  (C("#24374e"), C("#162438")), (C("#16273a"), C("#0a1422"))]
        haze = C("#c78aa0")
    bases = [0.58, 0.645, 0.725, 0.815, 0.92]
    for i, b in enumerate(bases):
        u = x * (1.1 + i * 0.45) + i * 2.3
        top = b - (0.07 + i * 0.03) * (fbm1(u, 3, 60 + i, 0.4) * 1.7 - 0.25)
        ct, cb = greens[i]
        c.layer(top, ct, cb, depth=0.12 + i * 0.03, haze=haze, haze_amt=max(0, 0.30 - i * 0.08),
                light=profile_light(top, dark, 25), light_amt=0.55, texture=0.06, seed=70 + i)
        if i == 1: c.mist(b - 0.01, b + 0.08, haze, 0.25)
    return c.finish(4, vignette=0.10 if not dark else 0.22)

def coast(W, H, dark):
    c = Canvas(W, H); x = c.x; hz = 0.60
    if not dark:
        c.gradient([(0, C("#3a62b8")), (0.30, C("#b07bb5")), (0.50, C("#f7a37a")), (hz, C("#ffd7a1")),
                    (hz + 0.0005, C("#6f86a8")), (0.75, C("#3c5f88")), (1, C("#1d3557"))])
        sx = 0.30
        c.clouds(0.06, 0.44, C("#ffc3a0"), 0.6, 33, cover=0.6, shade=C("#8a5d9b"))
        c.glow(sx, hz - 0.03, C("#ffd28f"), 0.40, 3.0, 0.8, 12)
        c.disc(sx, hz - 0.028, 0.034, C("#fff1cf"))
        glint_c = C("#ffe0b0")
        cliffs = [(C("#b07f8c"), C("#86607a")), (C("#7b5070"), C("#523550")), (C("#4a2c44"), C("#1f1221"))]
        haze = C("#f2b39a")
    else:
        c.gradient([(0, C("#050a1c")), (0.35, C("#13245a")), (hz, C("#3c5aa0")),
                    (hz + 0.0005, C("#253a6a")), (0.75, C("#13244a")), (1, C("#040a18"))])
        sx = 0.70
        c.stars(13, 0.5)
        c.glow(sx, 0.22, C("#aab9ff"), 0.10, 5, 0.25, 26); c.disc(sx, 0.22, 0.02, C("#f5f6ff"))
        glint_c = C("#c4d0ff")
        cliffs = [(C("#2e3a68"), C("#1d2548")), (C("#1d264a"), C("#111733")), (C("#0f152c"), C("#060914"))]
        haze = C("#2c3f7a")
    yy = c.yy; below = (yy > hz)
    dist = np.clip((yy - hz) / (1 - hz), 0, 1)
    # waves: thin horizontal glints that grow toward the viewer, gathered in a path under the sun/moon
    xs = x[None, :]
    waves = fbm2(xs * (14 / (dist * 3 + 0.08)) , (yy - hz) * (900 / (dist * 2 + 0.25)), 4, 77)
    path = np.exp(-((xs - sx) / (0.03 + dist * 0.22)) ** 2)
    glint = ss(0.56, 0.78, waves) * (0.25 + 0.75 * path) * below
    c.img = c.img + glint_c * (glint * (1 - dist * 0.4))[..., None] * 0.55
    c.img = lerp(c.img, haze, np.exp(-(yy - hz).clip(0) * 45) * below * 0.5)
    # headlands on the right, each one further along the coast and fainter
    for i, (ct, cb) in enumerate(cliffs):
        start = (0.40, 0.56, 0.68)[i]
        face = (0.03, 0.04, 0.24)[i]
        hgt = (0.045, 0.10, 0.27)[i]
        land = ss(start, start + face, x + (0.012, 0.012, 0.03)[i] * (fbm1(x * 60 + i, 4, 80 + i) - 0.5))
        if i == 2: land = land ** 0.75 * (1 + 0.05 * (fbm1(x * 25, 5, 71) - 0.5))   # a rugged slope, not a wall
        crown = 0.75 + 0.35 * fbm1(x * (3 + i * 2) + i, 6, 90 + i) + 0.10 * ss(start + face, 1.0, x)
        foot = hz + (0.004, 0.018, 0.5)[i]               # where the headland meets the sea
        top = hz + (0.004, 0.018, 0.04)[i] - land * hgt * crown
        if i == 2:   # the near headland rises out of the sea from below the frame, so it has no flat wall
            top = 1.04 - land * (1.04 - hz + hgt * crown)
        top = np.where(land < 0.02, 2.0, top)
        c.layer(top, ct, cb, depth=hgt + 0.06, haze=haze, haze_amt=(0.45, 0.25, 0.0)[i],
                light=profile_light(top, not dark, 7), light_amt=0.55, texture=0.08, seed=95 + i,
                rim=glint_c if i == 2 else None, rim_amt=0.10, bottom=foot if i < 2 else None)
        if i < 2:   # surf along the foot of the cliffs
            surf = np.exp(-((c.yy - foot) * c.H / 1.5) ** 2) * (land[None, :] > 0.5) * (0.35 + 0.4 * fbm2(x[None, :] * 200, c.yy * 50, 3, 97 + i))
            c.img = lerp(c.img, np.broadcast_to(glint_c, c.img.shape), surf * (0.35 if not dark else 0.2))
        if i < 2: c.mist(hz - hgt * 0.5, hz + 0.02, haze, 0.35, seed=96 + i)
    return c.finish(5, vignette=0.14 if not dark else 0.26)

def lake(W, H, dark):
    c = Canvas(W, H); x = c.x; hz = 0.60
    if not dark:
        c.gradient([(0, C("#3c7bd6")), (0.35, C("#8fbdee")), (hz, C("#fbe2c4")), (1, C("#fbe2c4"))])
        c.glow(0.75, 0.28, C("#fff0d0"), 0.25, 3, 0.4, 16)
        c.clouds(0.03, 0.36, C("#ffffff"), 0.8, 41, cover=0.6, shade=C("#d6c4c8"))
        mts = [(C("#f6f6fb"), C("#a9b4d6")), (C("#7d8fb8"), C("#4e6188")), (C("#3a5a4a"), C("#1b3326"))]
        haze, water = C("#e4e8f4"), C("#3d6d93")
    else:
        c.gradient([(0, C("#030712")), (0.35, C("#0a1d33")), (hz, C("#1e4a5c")), (1, C("#1e4a5c"))])
        c.stars(17, 0.5)
        yy = c.yy; xx = x[None, :]
        band = 0.27 + 0.07 * np.sin(xx * 5 + 1.0) + 0.035 * np.sin(xx * 13 + 0.3)
        rays = fbm2(xx * 90, yy * 1.5, 3, 120)
        curtain = np.exp(-((yy - band) / 0.045) ** 2) * 1.1 + np.exp(-np.clip(band - yy, 0, None) / 0.07) * (yy < band) * ss(0.45, 0.85, rays) * 0.6
        curtain *= 0.55 + 0.45 * fbm2(xx * 6, yy * 3, 3, 121)
        col = lerp(np.broadcast_to(C("#3cf0a8"), c.img.shape), np.broadcast_to(C("#9a6bff"), c.img.shape), ss(0.0, 0.16, band - yy))
        c.img += col * np.clip(curtain, 0, 1)[..., None] * 0.5 * ss(hz, hz - 0.2, yy)[..., None]
        mts = [(C("#a9bfd0"), C("#36506a")), (C("#2d4258"), C("#18283a")), (C("#0f1d22"), C("#060d0f"))]
        haze, water = C("#1e4a5c"), C("#05111a")
    for i, (ct, cb) in enumerate(mts):
        base = hz + 0.001
        amp = (0.25, 0.13, 0.04)[i]
        top = base - amp * ridge1(x * (1.8 + i * 1.7) + 11 * i, 7, 130 + i, 0.5, 1.2 - i * 0.4) ** (1.5 - i * 0.2)
        if i == 2:     # a fringe of pines on the far shore
            top = top - 0.014 * ss(0.3, 0.95, np.abs(np.sin(x * 700 + fbm1(x * 40, 3, 140) * 6))) * (0.5 + fbm1(x * 9, 3, 141))
        top = np.minimum(top, hz)
        c.layer(top, ct, cb, depth=amp * 1.2 + 0.02, haze=haze, haze_amt=(0.16, 0.10, 0.02)[i],
                light=profile_light(top, dark), light_amt=0.5 - i * 0.12, texture=0.05, seed=150 + i,
                rim=C("#ffffff") if i == 0 else None, rim_amt=0.1)
    # mirror the scene into the lake, with soft ripples and a fresnel fade to deep water
    Hn, Wn = c.H, c.W; hy = int(hz * Hn)
    rows = np.arange(Hn); cols = np.arange(Wn)
    d = np.maximum(rows - hy, 1).astype(np.float32)[:, None]
    ripple = (fbm2(cols[None, :] / Wn * 4, 1800.0 / d, 4, 160) - 0.5) * np.minimum(d * 0.06, 7)
    src = np.clip(2 * hy - rows[:, None] + ripple, 0, hy - 1).astype(int)
    refl = c.img[src, cols[None, :]]
    depthf = (rows[:, None] - hy) / Hn
    fres = 0.85 - 0.45 * ss(0, 0.4, depthf)
    wat = lerp(np.broadcast_to(water, refl.shape), refl * 0.92, fres)
    streak = ss(0.66, 0.72, fbm2(cols[None, :] / Wn * 10, rows[:, None] / Hn * 260, 3, 170)) * (0.06 if not dark else 0.04)
    wat = wat + streak[..., None]
    c.img = np.where((rows[:, None] > hy)[..., None], wat, c.img)
    c.img += np.exp(-np.abs(rows - hy) / 1.6)[:, None, None] * (0.06 if not dark else 0.03)
    return c.finish(6, vignette=0.12 if not dark else 0.28)

def forest(W, H, dark):
    c = Canvas(W, H); x = c.x
    if not dark:
        c.gradient([(0, C("#8fb7d2")), (0.45, C("#dce8ea")), (1, C("#eef1ea"))])
        c.glow(0.62, 0.20, C("#fff6dc"), 0.35, 2.5, 0.4, 14)
        tones = [C("#b5c8c5"), C("#8fa9a5"), C("#678883"), C("#43665f"), C("#26453d"), C("#122822")]
        haze = C("#e2ebe8")
    else:
        c.gradient([(0, C("#070c1a")), (0.45, C("#1a2a44")), (1, C("#2f4660"))])
        c.stars(23, 0.42, 0.0008)
        c.glow(0.62, 0.18, C("#b6c8ff"), 0.15, 4, 0.3, 22); c.disc(0.62, 0.18, 0.024, C("#f2f5ff"))
        tones = [C("#3b5170"), C("#2e425e"), C("#22334c"), C("#17253a"), C("#0e1828"), C("#060c16")]
        haze = C("#33496a")
    rng = np.random.default_rng(31)
    for i, tone in enumerate(tones):
        base = 0.52 + i * 0.085
        ground = base + 0.035 * (fbm1(x * 2 + i, 3, 200 + i) - 0.5)
        top = ground.copy()
        n = int(36 + i * 16); size = 0.07 + i * 0.032
        for _ in range(n):     # pines: tall narrow cones with a softly ragged outline
            cx = rng.random(); h = size * (0.55 + 0.6 * rng.random()); w = h * (0.20 + 0.07 * rng.random())
            dx = np.abs(x - cx) / w
            jag = 1 + 0.10 * np.abs(np.sin(dx * 30 + cx * 99)) * (dx > 0.15)
            tree = ground - h * np.clip(1 - dx * jag, 0, 1) ** 1.2
            top = np.minimum(top, np.where(dx < 1, tree, 2.0))
        c.layer(top, tone, tone * 0.82, depth=0.3, texture=0.03, seed=210 + i)
        if i < 5: c.mist(base - 0.05, base + 0.06, haze, 0.55 - i * 0.07, seed=220 + i)
    return c.finish(7, vignette=0.12 if not dark else 0.28)

SCENES = {"peaks": peaks, "dunes": dunes, "hills": hills, "coast": coast, "lake": lake, "forest": forest}

if __name__ == "__main__":
    out = sys.argv[1]
    W, H = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1920, 1080)
    for nm in sys.argv[4:] or list(SCENES):
        for dark in (False, True):
            SCENES[nm](W, H, dark).save(f"{out}/summit-{nm}-{'dark' if dark else 'light'}.jpg", quality=92)
            print(nm, "dark" if dark else "light", flush=True)
