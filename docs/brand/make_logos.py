"""Build BrandShield's logo files: the mark, the outlined wordmark and lockups.

The wordmark is Fraunces SemiBold at display optical size, converted to paths
so the files look the same everywhere (no font needed to render them).
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "pylib"))

from fontTools.pens.boundsPen import BoundsPen  # noqa: E402
from fontTools.pens.svgPathPen import SVGPathPen  # noqa: E402
from fontTools.pens.transformPen import TransformPen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
from fontTools.varLib.instancer import instantiateVariableFont  # noqa: E402

INK = "#121212"
PAPER = "#f4f0e8"
VERMILION = "#d2381e"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- the mark
# A shield holding two lines of "text"; the short line ends in a vermilion dot:
# a mention, flagged. 64-unit grid.
SHIELD = "M32 3 L57 11.5 V30.5 C57 46 46.5 56.5 32 61 C17.5 56.5 7 46 7 30.5 V11.5 Z"
LINE_1 = (17, 21, 30, 6)   # x, y, w, h
LINE_2 = (17, 33, 17, 6)
DOT = (42.5, 36, 5)        # cx, cy, r


def mark_group(shield, lines, dot, x=0.0, y=0.0, scale=1.0):
    l1, l2 = LINE_1, LINE_2
    return (f'<g transform="translate({x:.2f} {y:.2f}) scale({scale:.4f})">'
            f'<path d="{SHIELD}" fill="{shield}"/>'
            f'<rect x="{l1[0]}" y="{l1[1]}" width="{l1[2]}" height="{l1[3]}" fill="{lines}"/>'
            f'<rect x="{l2[0]}" y="{l2[1]}" width="{l2[2]}" height="{l2[3]}" fill="{lines}"/>'
            f'<circle cx="{DOT[0]}" cy="{DOT[1]}" r="{DOT[2]}" fill="{dot}"/></g>')


def mono_mark():
    # one ink: lines and dot knocked out of the shield (even-odd), for stamps and print
    l1, l2 = LINE_1, LINE_2
    cx, cy, r = DOT
    holes = (f"M{l1[0]} {l1[1]}h{l1[2]}v{l1[3]}h-{l1[2]}Z "
             f"M{l2[0]} {l2[1]}h{l2[2]}v{l2[3]}h-{l2[2]}Z "
             f"M{cx - r} {cy}a{r} {r} 0 1 0 {2 * r} 0a{r} {r} 0 1 0 -{2 * r} 0Z")
    return f'<path fill-rule="evenodd" d="{SHIELD} {holes}" fill="{INK}"/>'


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" '
            f'width="{w:.0f}" height="{h:.0f}" role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')


# ------------------------------------------------------------ the wordmark
font = TTFont(HERE / "fraunces.ttf")
font = instantiateVariableFont(font, {"wght": 600, "opsz": 72, "SOFT": 0, "WONK": 0})
glyphs = font.getGlyphSet()
cmap = font.getBestCmap()
hmtx = font["hmtx"]
upm = font["head"].unitsPerEm
kern = {}
if "GPOS" in font:  # pair kerning from the first PairPos format-1 subtables (enough for these letters)
    for lookup in font["GPOS"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if getattr(st, "LookupType", None) == 2 and st.Format == 1:
                for first, pairset in zip(st.Coverage.glyphs, st.PairSet):
                    for rec in pairset.PairValueRecord:
                        if rec.Value1 and getattr(rec.Value1, "XAdvance", 0):
                            kern[(first, rec.SecondGlyph)] = rec.Value1.XAdvance


def outline(text, color_for):
    """Return (svg path elements, width, ascent-box) for text in font units, baseline at y=0."""
    x = 0
    parts = []
    names = [cmap[ord(c)] for c in text]
    for i, (ch, name) in enumerate(zip(text, names)):
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, x, 0)))
        d = pen.getCommands()
        if d:
            parts.append(f'<path d="{d}" fill="{color_for(i, ch)}"/>')
        x += hmtx[name][0]
        if i + 1 < len(names):
            x += kern.get((name, names[i + 1]), 0)
    bp = BoundsPen(glyphs)
    for name in names:
        glyphs[name].draw(bp)
    return parts, x


TEXT = "BrandShield."
cap = font["OS/2"].sCapHeight
desc = 0
parts_ink, width = outline(TEXT, lambda i, c: VERMILION if c == "." else INK)
parts_rev, _ = outline(TEXT, lambda i, c: VERMILION if c == "." else PAPER)

# wordmark alone: cap height 100 units -> scale
S = 100 / cap
pad = 0.08 * cap * S
ww, wh = width * S + 2 * pad, cap * S * 1.32 + 2 * pad
base_y = pad + cap * S * 1.02
wm = f'<g transform="translate({pad:.2f} {base_y:.2f}) scale({S:.5f})">{"".join(parts_ink)}</g>'
(OUT / "brandshield-wordmark.svg").write_text(svg(ww, wh, wm, "BrandShield"), encoding="utf-8")


def lockup(parts, shield, lines, bg=None):
    # mark height = 1.5 x cap height; gap = 0.35 x mark; baseline aligned to the mark's line 2
    m = 150 / 64          # mark scale (64-unit mark -> 150 units tall)
    mark_w = 64 * m
    gap = 0.32 * mark_w
    text_w = width * S
    total_w, total_h = mark_w + gap + text_w, 64 * m
    base = 46 * m          # baseline sits a touch below the shield's centre
    pad = 0.12 * total_h
    body = ""
    if bg:
        body += f'<rect width="{total_w + 2 * pad:.2f}" height="{total_h + 2 * pad:.2f}" fill="{bg}"/>'
    body += mark_group(shield, lines, VERMILION, pad, pad, m)
    body += f'<g transform="translate({pad + mark_w + gap:.2f} {pad + base:.2f}) scale({S:.5f})">{"".join(parts)}</g>'
    return total_w + 2 * pad, total_h + 2 * pad, body


w, h, b = lockup(parts_ink, INK, PAPER)
(OUT / "brandshield-lockup.svg").write_text(svg(w, h, b, "BrandShield"), encoding="utf-8")
w, h, b = lockup(parts_rev, PAPER, INK, bg=INK)
(OUT / "brandshield-lockup-on-ink.svg").write_text(svg(w, h, b, "BrandShield"), encoding="utf-8")

(OUT / "brandshield-mark.svg").write_text(svg(64, 64, mark_group(INK, PAPER, VERMILION), "BrandShield mark"), encoding="utf-8")
(OUT / "brandshield-mark-on-ink.svg").write_text(
    svg(64, 64, f'<rect width="64" height="64" fill="{INK}"/>' + mark_group(PAPER, INK, VERMILION, 4, 4, 56 / 64), "BrandShield mark"),
    encoding="utf-8")
(OUT / "brandshield-mark-mono.svg").write_text(svg(64, 64, mono_mark(), "BrandShield mark"), encoding="utf-8")
# favicon: the mark on a paper tile so it reads on dark browser tabs too
(OUT / "favicon.svg").write_text(
    svg(64, 64, f'<rect width="64" height="64" rx="12" fill="{PAPER}"/>' + mark_group(INK, PAPER, VERMILION, 2, 2, 60 / 64), "BrandShield"),
    encoding="utf-8")
print("wordmark width units:", round(width), "kern pairs:", len(kern))
for f in sorted(OUT.iterdir()):
    print(f.name, f.stat().st_size)
