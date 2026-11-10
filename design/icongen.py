#!/usr/bin/python3
"""Summit OS 1.21 icon set: one shared squircle body, lighting and glass highlight,
with a glyph per app. Writes SVGs to the folder given as argv[1]."""
import math, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "icons"
os.makedirs(OUT, exist_ok=True)

def squircle(x, y, s, n=5.0, steps=96):
    """Superellipse (iOS/macOS-style continuous corner) inside the square x,y,s."""
    cx, cy, r = x + s / 2, y + s / 2, s / 2
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, si = math.cos(t), math.sin(t)
        px = cx + r * (abs(c) ** (2 / n)) * (1 if c >= 0 else -1)
        py = cy + r * (abs(si) ** (2 / n)) * (1 if si >= 0 else -1)
        pts.append(f"{px:.2f},{py:.2f}")
    return "M" + " L".join(pts) + " Z"

BODY = squircle(10, 10, 108)

def icon(name, top, bottom, glyph, extra_defs="", dark_glyph_shadow=True):
    gs = ('<filter id="gsh" x="-20%" y="-20%" width="140%" height="140%">'
          '<feDropShadow dx="0" dy="1.6" stdDeviation="1.6" flood-color="#000" flood-opacity=".22"/></filter>'
          if dark_glyph_shadow else "")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>
 <radialGradient id="gloss" cx=".5" cy="0" r=".9" fx=".5" fy="0"><stop offset="0" stop-color="#fff" stop-opacity=".46"/><stop offset=".55" stop-color="#fff" stop-opacity=".08"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
 <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset=".62" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".16"/></linearGradient>
 <linearGradient id="rim" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".62"/><stop offset=".45" stop-color="#fff" stop-opacity=".10"/><stop offset="1" stop-color="#fff" stop-opacity=".22"/></linearGradient>
 <filter id="drop" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.4"/></filter>
 <clipPath id="clip"><path d="{BODY}"/></clipPath>
 {gs}
 {extra_defs}
</defs>
<path d="{BODY}" transform="translate(0 3)" fill="#000" opacity=".26" filter="url(#drop)"/>
<path d="{BODY}" fill="url(#bg)"/>
<g clip-path="url(#clip)">
 <g{' filter="url(#gsh)"' if dark_glyph_shadow else ''}>{glyph}</g>
 <rect x="0" y="0" width="128" height="128" fill="url(#floor)"/>
 <ellipse cx="64" cy="4" rx="78" ry="58" fill="url(#gloss)"/>
</g>
<path d="{BODY}" fill="none" stroke="url(#rim)" stroke-width="1.6" transform="translate(64 64) scale(.985) translate(-64 -64)"/>
</svg>'''
    with open(os.path.join(OUT, name + ".svg"), "w") as f:
        f.write(svg)

def gear(cx, cy, r_out, r_in, teeth, hole, tooth_w=0.42):
    pts = []
    for i in range(teeth):
        a0 = 2 * math.pi * i / teeth
        step = 2 * math.pi / teeth
        for frac, rr in ((0.0, r_in), (0.5 - tooth_w / 2 - 0.06, r_in), (0.5 - tooth_w / 2, r_out),
                         (0.5 + tooth_w / 2, r_out), (0.5 + tooth_w / 2 + 0.06, r_in)):
            a = a0 + step * frac
            pts.append(f"{cx + rr * math.cos(a):.2f},{cy + rr * math.sin(a):.2f}")
    outer = "M" + " L".join(pts) + " Z"
    inner = f"M{cx + hole},{cy} a{hole},{hole} 0 1,0 {-2 * hole},0 a{hole},{hole} 0 1,0 {2 * hole},0 Z"
    return outer + " " + inner

IMAC = ["#3B82F6", "#A855F7", "#EC4899", "#F97316", "#FACC15", "#22C55E", "#14B8A6", "#6366F1", "#EF4444"]

# ---------------------------------------------------------------- dock apps
icon("summit-files", "#6FD3FF", "#0A6CFF", '''
 <path d="M26 40a7 7 0 0 1 7-7h20.5a6 6 0 0 1 4.6 2.1l4.8 5.6H95a7 7 0 0 1 7 7v4H26z" fill="#D9EEFF"/>
 <rect x="22" y="48" width="84" height="52" rx="8" fill="#fff"/>
 <rect x="22" y="48" width="84" height="12" rx="6" fill="#EAF5FF"/>
 <rect x="50" y="76" width="28" height="5.5" rx="2.75" fill="#2F86F6"/>''')

tiles = ""
for i, col in enumerate(IMAC):
    x, y = 31 + (i % 3) * 23, 31 + (i // 3) * 23
    tiles += f'<rect x="{x}" y="{y}" width="18" height="18" rx="5.5" fill="{col}"/><rect x="{x}" y="{y}" width="18" height="8" rx="4" fill="#fff" opacity=".28"/>'
icon("summit-launchpad", "#4A4F63", "#16181F", tiles)

icon("summit-web", "#5EE7F6", "#2563EB", '''
 <circle cx="64" cy="64" r="34" fill="#fff" opacity=".20"/>
 <circle cx="64" cy="64" r="34" fill="none" stroke="#fff" stroke-width="5"/>
 <ellipse cx="64" cy="64" rx="14" ry="34" fill="none" stroke="#fff" stroke-width="4.2"/>
 <path d="M30 64h68M35 46h58M35 82h58" stroke="#fff" stroke-width="4.2" stroke-linecap="round" fill="none"/>
 <ellipse cx="64" cy="64" rx="46" ry="13" fill="none" stroke="#FFE27A" stroke-width="3.6" transform="rotate(-24 64 64)" stroke-dasharray="120 18"/>''')

icon("summit-terminal", "#5B6070", "#1C1E25", '''
 <rect x="22" y="28" width="84" height="72" rx="10" fill="#0E1015"/>
 <rect x="22" y="28" width="84" height="13" rx="6.5" fill="#2A2D36"/>
 <circle cx="31" cy="34.5" r="2.6" fill="#FF5F57"/><circle cx="39" cy="34.5" r="2.6" fill="#FEBC2E"/><circle cx="47" cy="34.5" r="2.6" fill="#28C840"/>
 <path d="M34 56l14 11-14 11" fill="none" stroke="#34E27A" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
 <rect x="54" y="74" width="24" height="6" rx="3" fill="#E8EAF0"/>''')

icon("summit-textedit", "#FFE77A", "#F5A300", '''
 <path d="M34 22h44l16 16v66a6 6 0 0 1-6 6H34a6 6 0 0 1-6-6V28a6 6 0 0 1 6-6z" fill="#fff"/>
 <path d="M78 22v12a4 4 0 0 0 4 4h12z" fill="#FFE6A3"/>
 <path d="M38 50h42M38 61h42M38 72h30M38 83h22" stroke="#C9CDD6" stroke-width="4" stroke-linecap="round"/>
 <g transform="rotate(42 86 82)">
  <rect x="80" y="48" width="12" height="44" rx="2.5" fill="#FF7A1A"/>
  <rect x="80" y="48" width="12" height="7" rx="2.5" fill="#FF9EC1"/>
  <rect x="80" y="55" width="12" height="3" fill="#D8DCE3"/>
  <path d="M80 92h12l-6 11z" fill="#F5D7A8"/><path d="M84 99.4h4l-2 3.6z" fill="#333"/>
 </g>''')

keys = ""
for r in range(4):
    for c in range(4):
        x, y = 30 + c * 18, 52 + r * 13
        col = "#FF9F0A" if c == 3 else ("#A5A8B3" if r == 0 else "#4A4D58")
        keys += f'<rect x="{x}" y="{y}" width="14" height="10" rx="3.2" fill="{col}"/>'
icon("summit-calculator", "#5E6270", "#22242C", f'''
 <rect x="26" y="24" width="76" height="22" rx="6" fill="#B9F5C9"/>
 <rect x="26" y="24" width="76" height="22" rx="6" fill="#fff" opacity=".25"/>
 <rect x="66" y="31" width="28" height="8" rx="2" fill="#1F3B2A" opacity=".75"/>
 {keys}''')

icon("summit-monitor", "#5EF0B5", "#0E9F6E", '''
 <path d="M24 46h80M24 64h80M24 82h80" stroke="#fff" stroke-opacity=".22" stroke-width="2"/>
 <path d="M22 66h20l7-20 11 40 10-30 6 10h30" fill="none" stroke="#fff" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>''')

icon("summit-settings", "#E6E9EE", "#8C929D", f'''
 <defs><linearGradient id="gearg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6E7480"/><stop offset="1" stop-color="#3F444D"/></linearGradient></defs>
 <path d="{gear(64, 64, 40, 31, 12, 0.01)}" fill="url(#gearg)" fill-rule="evenodd"/>
 <circle cx="64" cy="64" r="21" fill="#D5D9E0"/>
 <circle cx="64" cy="64" r="21" fill="none" stroke="#2F343C" stroke-opacity=".25" stroke-width="2"/>
 <circle cx="64" cy="64" r="9" fill="#4B515B"/>''')

icon("summit-connect", "#60A5FA", "#6D28D9", '''
 <rect x="20" y="30" width="58" height="40" rx="5" fill="#fff"/>
 <rect x="25" y="35" width="48" height="30" rx="2.5" fill="#C7D7FE"/>
 <path d="M44 70h10l2 9H42z" fill="#fff"/><rect x="36" y="78" width="26" height="4.5" rx="2.25" fill="#fff"/>
 <rect x="62" y="58" width="44" height="28" rx="4" fill="#fff"/>
 <rect x="66" y="62" width="36" height="20" rx="2" fill="#E9D5FF"/>
 <rect x="56" y="86" width="56" height="5" rx="2.5" fill="#fff"/>''')

# ---------------------------------------------------------------- other apps (Launchpad)
icon("summit-archive", "#F6C177", "#B7712C", '''
 <rect x="24" y="36" width="80" height="62" rx="8" fill="#FFF3E0"/>
 <rect x="20" y="30" width="88" height="16" rx="6" fill="#fff"/>
 <rect x="58" y="30" width="12" height="68" fill="#C98A4B"/>
 <path d="M58 52h6M64 58h6M58 64h6M64 70h6M58 76h6" stroke="#FFF3E0" stroke-width="3"/>
 <rect x="56" y="80" width="16" height="12" rx="3" fill="#8B5A2B"/>''')

icon("summit-bluetooth", "#6EA8FF", "#1D4ED8", '''
 <path d="M50 44l30 24-16 13V31l16 13-30 24" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>''')

icon("summit-disks", "#C3CAD5", "#5B6473", '''
 <rect x="26" y="26" width="76" height="76" rx="12" fill="#F2F4F7"/>
 <circle cx="60" cy="62" r="25" fill="#D3D8E0"/><circle cx="60" cy="62" r="25" fill="none" stroke="#B5BCC7" stroke-width="2"/>
 <circle cx="60" cy="62" r="6" fill="#8D95A3"/>
 <path d="M90 36L68 66" stroke="#4B5563" stroke-width="6" stroke-linecap="round"/><circle cx="90" cy="36" r="6" fill="#4B5563"/>
 <circle cx="36" cy="92" r="3" fill="#22C55E"/>''')

icon("summit-docviewer", "#FF8A8A", "#D92D2D", '''
 <path d="M36 22h40l16 16v62a6 6 0 0 1-6 6H36a6 6 0 0 1-6-6V28a6 6 0 0 1 6-6z" fill="#fff"/>
 <path d="M76 22v12a4 4 0 0 0 4 4h12z" fill="#FFD1D1"/>
 <rect x="38" y="46" width="44" height="24" rx="4" fill="#FECACA"/>
 <path d="M40 66l12-12 9 8 7-6 12 10" fill="none" stroke="#EF4444" stroke-width="3.5" stroke-linejoin="round"/>
 <path d="M38 80h44M38 90h30" stroke="#D1D5DB" stroke-width="4" stroke-linecap="round"/>''')

icon("summit-photos", "#FFB86B", "#F0457A", '''
 <rect x="22" y="30" width="84" height="68" rx="9" fill="#fff"/>
 <rect x="29" y="37" width="70" height="54" rx="5" fill="#7DD3FC"/>
 <circle cx="82" cy="52" r="7" fill="#FDE047"/>
 <path d="M29 91l22-28 14 16 9-10 25 22z" fill="#34D399"/>
 <path d="M29 91l22-28 9 10-14 18z" fill="#10B981"/>''')

icon("summit-media", "#C084FC", "#6D28D9", '''
 <circle cx="64" cy="64" r="34" fill="#fff" opacity=".22"/>
 <circle cx="64" cy="64" r="34" fill="none" stroke="#fff" stroke-width="5"/>
 <path d="M56 46l26 18-26 18z" fill="#fff" stroke="#fff" stroke-width="4" stroke-linejoin="round"/>''')

def arc(cx, cy, r, a0, a1):
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{cx},{cy} L{x0:.2f},{y0:.2f} A{r},{r} 0 {large},1 {x1:.2f},{y1:.2f} Z"
icon("summit-partitions", "#64748B", "#1E293B", f'''
 <path d="{arc(64,64,34,-90,60)}" fill="#3B82F6"/>
 <path d="{arc(64,64,34,60,170)}" fill="#22C55E"/>
 <path d="{arc(64,64,34,170,230)}" fill="#FACC15"/>
 <path d="{arc(66,62,34,230,270)}" fill="#F97316"/>
 <circle cx="64" cy="64" r="13" fill="#1E293B"/>''')

icon("summit-screenshot", "#7C8494", "#2F343E", '''
 <path d="M26 44V32a6 6 0 0 1 6-6h12M84 26h12a6 6 0 0 1 6 6v12M102 84v12a6 6 0 0 1-6 6H84M44 102H32a6 6 0 0 1-6-6V84" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
 <rect x="40" y="48" width="48" height="34" rx="7" fill="#fff"/>
 <rect x="54" y="42" width="20" height="8" rx="3" fill="#fff"/>
 <circle cx="64" cy="65" r="11" fill="#2F343E"/><circle cx="64" cy="65" r="6" fill="#60A5FA"/>''')

icon("summit-sound", "#FF7A95", "#E11D48", '''
 <path d="M28 52h14l18-15v54L42 76H28z" fill="#fff" stroke="#fff" stroke-width="4" stroke-linejoin="round"/>
 <path d="M72 50a20 20 0 0 1 0 28M82 40a34 34 0 0 1 0 48" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/>''')

# ---------------------------------------------------------------- trash (glass bin, no squircle)
def trash(name, full):
    paper = ""
    if full:
        paper = '''<path d="M42 34c6-10 18-12 24-4 6-9 20-6 22 4 4 3 2 10-3 10H44c-6 0-8-6-2-10z" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1.5"/>
        <path d="M52 30l6 9M70 28l-3 11M80 33l-6 7" stroke="#CBD5E1" stroke-width="1.5"/>'''
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
<defs>
 <linearGradient id="body" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#B9C0CB"/><stop offset=".22" stop-color="#EEF1F5"/><stop offset=".55" stop-color="#D3D8E0"/><stop offset="1" stop-color="#9AA2AE"/></linearGradient>
 <linearGradient id="inner" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5B6270"/><stop offset="1" stop-color="#8A93A1"/></linearGradient>
 <filter id="drop" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.2"/></filter>
</defs>
<ellipse cx="64" cy="112" rx="34" ry="6" fill="#000" opacity=".22" filter="url(#drop)"/>
<path d="M28 40l8 66a6 6 0 0 0 6 5h44a6 6 0 0 0 6-5l8-66z" fill="url(#body)" opacity=".96"/>
<ellipse cx="64" cy="40" rx="36" ry="8" fill="url(#inner)"/>
{paper}
<path d="M44 52l3 50M56 53l1 51M72 53l-1 51M84 52l-3 50" stroke="#fff" stroke-opacity=".75" stroke-width="3" stroke-linecap="round"/>
<path d="M44 52l3 50M56 53l1 51M72 53l-1 51M84 52l-3 50" stroke="#8D95A3" stroke-opacity=".45" stroke-width="1.2" transform="translate(2 0)"/>
<ellipse cx="64" cy="40" rx="36" ry="8" fill="none" stroke="#F8FAFC" stroke-width="3"/>
</svg>'''
    with open(os.path.join(OUT, name + ".svg"), "w") as f:
        f.write(svg)
trash("summit-trash", False)
trash("summit-trash-full", True)
print("icons written to", OUT)

# Software Update (1.22): a circular arrow around a download arrow
icon("summit-update", "#3ED3A1", "#0E8F7A", '''
 <path d="M64 30a34 34 0 1 1-30.6 19.2" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round"/>
 <path d="M24.5 34.5 L33.6 49.6 L48.6 41.8 Z" fill="#fff" stroke="#fff" stroke-width="3" stroke-linejoin="round"/>
 <path d="M64 46v28" stroke="#fff" stroke-width="9" stroke-linecap="round"/>
 <path d="M51 64l13 14 13-14" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
''')

# App Store: an original shopping-bag glyph with a download arrow
icon("summit-appstore", "#8A7CFF", "#3B4BE0", '''
 <path d="M44 48 C44 32 52 25 64 25 C76 25 84 32 84 48" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
 <path d="M30 46 H98 L93 98 Q92 104 86 104 H42 Q36 104 35 98 Z" fill="#fff"/>
 <path d="M64 58 V84" stroke="#5B5CF0" stroke-width="7" stroke-linecap="round"/>
 <path d="M53 74 L64 86 L75 74" fill="none" stroke="#5B5CF0" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>''')
