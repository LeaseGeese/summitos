# Summit mark: two peaks, the nearer one cut by a thin snow line; one colour, negative space only.
def mark(fill="#fff", snow=True, sw=3.0, gap=5.0, uid="m"):
    ax, ay = 50.0, 30.0; bl = (10.0, 98.0); br = (90.0, 98.0)          # main peak
    k = (br[0] - ax) / (br[1] - ay)                                     # main right edge slope dx/dy
    off = (gap + sw) * ((1 + k * k) ** 0.5)                              # horizontal offset of the gap
    sx, sy = 86.0, 56.0; sr = (118.0, 98.0)                             # far peak
    ks = (sr[0] - sx) / (sr[1] - sy)
    y = (sx + ks * sy - (ax + off) + k * ay) / (k + ks); x = sx - ks * (y - sy)
    far = f"M{sx} {sy} L{sr[0]} {sr[1]} L{br[0] + off:.2f} {sr[1]} L{x:.2f} {y:.2f} Z"
    main = f"M{ax} {ay} L{br[0]} {br[1]} L{bl[0]} {bl[1]} Z"
    kl = (ax - bl[0]) / (bl[1] - ay)
    def lx(yy): return ax - kl * (yy - ay)
    def rx(yy): return ax + k * (yy - ay)
    y0 = 58.0
    cut = f"M{lx(y0) - 6:.1f} {y0 + 3} L{lx(y0) + 9:.1f} {y0 - 6} L{ax - 2:.1f} {y0 + 5} L{rx(y0) - 10:.1f} {y0 - 6} L{rx(y0) + 6:.1f} {y0 + 4}"
    mask = (f'<mask id="{uid}"><rect width="128" height="128" fill="#fff"/>'
            f'<path d="{cut}" fill="none" stroke="#000" stroke-width="{gap * 0.9}" stroke-linejoin="round" stroke-linecap="round"/></mask>') if snow else ""
    g = (f'<g fill="{fill}" stroke="{fill}" stroke-width="{sw}" stroke-linejoin="round">'
         f'<path d="{main}"{" mask=" + chr(34) + "url(#" + uid + ")" + chr(34) if snow else ""}/><path d="{far}"/></g>')
    return mask, g
if __name__ == "__main__":
    import sys
    m, g = mark()
    open("glyph.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><defs>{m}</defs><g transform="translate(0 -4)">{g}</g></svg>')
    m, g = mark(snow=False)
    open("glyph-plain.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><g transform="translate(0 -4)">{g}</g></svg>')
