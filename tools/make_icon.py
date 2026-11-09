"""
Draws the CleanX program icon from code (no third-party artwork).

    python tools/make_icon.py      -> icons/cleanx.ico  (+ icons/clean_<size>.png previews)

Motif: a broom sweeping across a teal lab tile, with a laser beam, sparkles and
dust. Small sizes get a simplified drawing so they stay readable.
Requires Pillow (pip install pillow).
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, '..', 'icons')
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
PNG_SIZES = [16, 24, 32, 64, 96, 256]

INK = (24, 30, 44, 255)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def star(d, cx, cy, r, fill, k=0.28):
    """4-pointed sparkle"""
    pts = []
    for i in range(8):
        a = math.radians(i * 45 - 90)
        rr = r if i % 2 == 0 else r * k
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def render(size):
    """Render the icon for a target size. Drawn on a 256 grid, supersampled."""
    detail = 2 if size >= 48 else (1 if size >= 24 else 0)
    S = 4 if size < 128 else 2              # supersampling
    N = 256 * S
    f = N / 256.0

    def P(x, y):
        return (x * f, y * f)

    def W(v):
        return max(1, int(v * f))

    img = Image.new('RGBA', (N, N), (0, 0, 0, 0))

    # --- tile: rounded square with vertical teal gradient
    grad = Image.new('RGBA', (N, N))
    gd = ImageDraw.Draw(grad)
    top, bot = (0, 190, 196, 255), (0, 104, 140, 255)
    for y in range(N):
        gd.line([(0, y), (N, y)], fill=lerp(top, bot, y / N))
    mask = Image.new('L', (N, N), 0)
    pad = 6 if detail else 2
    ImageDraw.Draw(mask).rounded_rectangle([*P(pad, pad), *P(256 - pad, 256 - pad)], radius=W(54), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img, 'RGBA')

    # soft highlight in the upper half
    if detail:
        hl = Image.new('RGBA', (N, N), (0, 0, 0, 0))
        ImageDraw.Draw(hl).ellipse([*P(-40, -120), *P(296, 120)], fill=(255, 255, 255, 38))
        hm = Image.new('L', (N, N), 0)
        hm.paste(mask)
        img.paste(Image.alpha_composite(img, hl), (0, 0), hm)
        d = ImageDraw.Draw(img, 'RGBA')

    # --- laser beam behind the broom (red, with glow)
    if detail >= 1:
        beam_y0, beam_y1 = 84, 118
        glow = Image.new('RGBA', (N, N), (0, 0, 0, 0))
        ImageDraw.Draw(glow).line([P(pad, beam_y0), P(256 - pad, beam_y1)], fill=(255, 40, 40, 200), width=W(18))
        glow = glow.filter(ImageFilter.GaussianBlur(W(7)))
        gm = Image.new('L', (N, N), 0)
        gm.paste(mask)
        img.paste(Image.alpha_composite(img, glow), (0, 0), gm)
        d = ImageDraw.Draw(img, 'RGBA')
        d.line([P(pad + 2, beam_y0), P(256 - pad - 2, beam_y1)], fill=(255, 70, 60, 255), width=W(7))
        d.line([P(pad + 2, beam_y0), P(256 - pad - 2, beam_y1)], fill=(255, 220, 210, 255), width=W(2.2))

    # --- broom geometry: handle from upper right down to the bristles at lower left
    h0, h1 = (204, 30), (122, 132)                  # handle top / ferrule
    dx, dy = h1[0] - h0[0], h1[1] - h0[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L                         # along the handle
    px, py = uy, -ux                                # perpendicular

    hw = 22 if detail == 0 else 17                  # handle thickness
    ol = 9 if detail == 0 else 7                    # outline thickness
    d.line([P(*h0), P(*h1)], fill=INK, width=W(hw + ol))
    d.line([P(*h0), P(*h1)], fill=(232, 160, 88, 255), width=W(hw))
    if detail:
        d.line([P(h0[0] + px * 4, h0[1] + py * 4), P(h1[0] + px * 4, h1[1] + py * 4)],
               fill=(255, 205, 140, 255), width=W(5))
    d.ellipse([*P(h0[0] - (hw + ol) / 2, h0[1] - (hw + ol) / 2), *P(h0[0] + (hw + ol) / 2, h0[1] + (hw + ol) / 2)], fill=INK)
    d.ellipse([*P(h0[0] - hw / 2, h0[1] - hw / 2), *P(h0[0] + hw / 2, h0[1] + hw / 2)], fill=(232, 160, 88, 255))

    # bristles: a fan, slightly swept to the side (motion!)
    bw0, bw1, blen, sweep = 30, 60, 78, 14
    b0 = (h1[0] + ux * 10, h1[1] + uy * 10)
    tip = (b0[0] + ux * blen + px * sweep, b0[1] + uy * blen + py * sweep)
    fan = [
        (b0[0] + px * bw0 / 2, b0[1] + py * bw0 / 2),
        (tip[0] + px * bw1 / 2, tip[1] + py * bw1 / 2),
        (tip[0] - px * bw1 / 2, tip[1] - py * bw1 / 2),
        (b0[0] - px * bw0 / 2, b0[1] - py * bw0 / 2),
    ]
    d.polygon([P(*q) for q in fan], fill=(250, 204, 60, 255))
    if detail:  # bristle strands
        n = 7 if detail == 2 else 4
        for i in range(1, n):
            t = i / n - 0.5
            a = (b0[0] + px * bw0 * t, b0[1] + py * bw0 * t)
            b = (tip[0] + px * bw1 * t, tip[1] + py * bw1 * t)
            d.line([P(*a), P(*b)], fill=(214, 150, 30, 255), width=W(3.5))
    d.line([P(*q) for q in fan + [fan[0]]], fill=INK, width=W(ol), joint='curve')

    # ferrule (metal band between handle and bristles)
    fw, fl = 40, 22
    fc = (h1[0] + ux * 2, h1[1] + uy * 2)
    band = [
        (fc[0] + px * fw / 2 - ux * fl / 2, fc[1] + py * fw / 2 - uy * fl / 2),
        (fc[0] + px * fw / 2 + ux * fl / 2, fc[1] + py * fw / 2 + uy * fl / 2),
        (fc[0] - px * fw / 2 + ux * fl / 2, fc[1] - py * fw / 2 + uy * fl / 2),
        (fc[0] - px * fw / 2 - ux * fl / 2, fc[1] - py * fw / 2 - uy * fl / 2),
    ]
    d.polygon([P(*q) for q in band], fill=(70, 110, 200, 255))
    d.line([P(*q) for q in band + [band[0]]], fill=INK, width=W(ol * 0.8), joint='curve')

    # --- dust puffs being swept away (lower right)
    if detail >= 1:
        for cx, cy, r in ((176, 214, 17), (200, 196, 12), (214, 222, 9))[: 3 if detail == 2 else 2]:
            d.ellipse([*P(cx - r, cy - r), *P(cx + r, cy + r)], fill=(225, 232, 236, 235), outline=INK, width=W(4))
        if detail == 2:
            for cx, cy in ((226, 180), (236, 202), (156, 238)):
                d.ellipse([*P(cx - 3.5, cy - 3.5), *P(cx + 3.5, cy + 3.5)], fill=(225, 232, 236, 255))

    # --- sparkles (it's clean now!)
    if detail == 0:
        star(d, *P(62, 64), 50 * f, (255, 255, 255, 255), k=0.3)
    else:
        star(d, *P(64, 62), 40 * f, (255, 255, 255, 255))
        star(d, *P(106, 34), 18 * f, (255, 255, 255, 235))
        if detail == 2:
            star(d, *P(38, 120), 14 * f, (255, 255, 255, 210))

    # tile outline
    if detail:
        ImageDraw.Draw(img).rounded_rectangle([*P(pad, pad), *P(256 - pad, 256 - pad)], radius=W(54),
                                              outline=(0, 70, 96, 255), width=W(5))

    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(ICON_DIR, exist_ok=True)
    frames = {s: render(s) for s in sorted(set(ICO_SIZES + PNG_SIZES))}
    ico = os.path.join(ICON_DIR, 'cleanx.ico')
    big = frames[256]
    big.save(ico, format='ICO', sizes=[(s, s) for s in ICO_SIZES],
             append_images=[frames[s] for s in ICO_SIZES if s != 256])
    for s in PNG_SIZES:
        frames[s].save(os.path.join(ICON_DIR, f'clean_{s}.png'))
    print('wrote', os.path.abspath(ico))


if __name__ == '__main__':
    main()
