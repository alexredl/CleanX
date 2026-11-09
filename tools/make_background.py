"""
Procedurally draws the "messy laser lab" background for CleanX.

    python tools/make_background.py            -> writes res/messy_lab.jpg

Requires Pillow (pip install pillow). Everything is drawn from code, so the
picture is free of any third-party copyright. Change SEED for a different mess.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080          # logical canvas
SS = 2                     # supersampling factor (anti-aliasing)
SEED = 7
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'res', 'messy_lab.jpg')

INK = (38, 36, 52)         # outline colour
OW = 3                     # default outline width

rnd = random.Random(SEED)


# --------------------------------------------------------------------------- helpers
def s(v):
    return int(round(v * SS))


def pts(seq):
    return [(s(x), s(y)) for x, y in seq]


class Canvas:
    def __init__(self, img):
        self.img = img
        self.d = ImageDraw.Draw(img, 'RGBA')

    def poly(self, p, fill=None, outline=INK, width=OW):
        self.d.polygon(pts(p), fill=fill)
        if outline and width:
            q = pts(p)
            self.d.line(q + [q[0]], fill=outline, width=s(width), joint='curve')

    def rect(self, x0, y0, x1, y1, fill=None, outline=INK, width=OW, r=0):
        box = [s(min(x0, x1)), s(min(y0, y1)), s(max(x0, x1)), s(max(y0, y1))]
        if r:
            self.d.rounded_rectangle(box, s(r), fill=fill, outline=outline if width else None,
                                     width=s(width) if width else 0)
        else:
            self.d.rectangle(box, fill=fill, outline=outline if width else None,
                             width=s(width) if width else 0)

    def ell(self, cx, cy, rx, ry, fill=None, outline=INK, width=OW):
        self.d.ellipse([s(cx - rx), s(cy - ry), s(cx + rx), s(cy + ry)], fill=fill,
                       outline=outline if width else None, width=s(width) if width else 0)

    def line(self, p, fill=INK, width=OW):
        self.d.line(pts(p), fill=fill, width=s(width), joint='curve')

    def text(self, x, y, txt, size, fill=INK, font='arialbd.ttf', anchor='mm'):
        f = ImageFont.truetype(font, s(size))
        self.d.text((s(x), s(y)), txt, font=f, fill=fill, anchor=anchor)


def bezier(p0, p1, p2, p3, n=40):
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t * t
        d = t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def rot(cx, cy, w, h, ang):
    """corners of a rectangle centred at cx,cy rotated by ang degrees"""
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        out.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return out


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def cable(cv, p0, p1, sag=80, color=(30, 30, 30), width=5, wobble=40):
    c1 = (p0[0] + rnd.uniform(-wobble, wobble), p0[1] + sag + rnd.uniform(-20, 20))
    c2 = (p1[0] + rnd.uniform(-wobble, wobble), p1[1] + sag * 0.6 + rnd.uniform(-20, 20))
    path = bezier(p0, c1, c2, p1)
    cv.line(path, fill=INK, width=width + 2.5)
    cv.line(path, fill=color, width=width)
    hl = shade(color, 1.6) if sum(color) > 90 else (90, 90, 100)
    cv.line([(x - width * 0.18, y - width * 0.18) for x, y in path], fill=hl + (110,), width=max(1, width * 0.3))


CABLE_COLORS = [(25, 25, 30), (25, 25, 30), (40, 40, 48), (230, 190, 40), (60, 110, 200), (200, 60, 50),
                (240, 140, 40), (90, 170, 90), (150, 150, 160), (120, 70, 160)]


# --------------------------------------------------------------------------- room
def draw_room(cv):
    # back wall
    cv.rect(0, 0, W, 660, fill=(122, 158, 168), width=0)
    # wall tiles (lower half) and stains
    for y in range(400, 660, 44):
        cv.line([(0, y), (W, y)], fill=(104, 138, 150), width=2)
        off = 0 if (y // 44) % 2 else 40
        for x in range(off, W, 80):
            cv.line([(x, y), (x, y + 44)], fill=(104, 138, 150), width=2)
    cv.rect(0, 392, W, 404, fill=(92, 120, 134), width=0)
    for _ in range(14):
        x, y = rnd.uniform(0, W), rnd.uniform(120, 620)
        for _ in range(5):
            cv.ell(x + rnd.uniform(-25, 25), y + rnd.uniform(-15, 15), rnd.uniform(10, 30), rnd.uniform(8, 20),
                   fill=(120, 110, 80, 22), width=0)
    for _ in range(6):  # drips
        x, y = rnd.uniform(0, W), rnd.uniform(60, 300)
        cv.line([(x, y), (x + rnd.uniform(-3, 3), y + rnd.uniform(60, 160))], fill=(95, 105, 95, 50), width=5)

    # ceiling band
    cv.rect(0, 0, W, 58, fill=(70, 82, 98), width=0)
    cv.line([(0, 58), (W, 58)], width=4)
    # fluorescent lights (one hanging crooked, one broken/flickering)
    cv.rect(300, 40, 620, 62, fill=(225, 240, 235), r=6)
    cv.poly([(1180, 58), (1500, 74), (1498, 96), (1178, 80)], fill=(150, 160, 160))
    cv.line([(1180, 40), (1182, 60)], width=3)
    cv.line([(1500, 40), (1499, 75)], width=3)

    # cable tray along the ceiling with drooping cables
    cv.rect(0, 74, W, 96, fill=(150, 156, 160))
    for x in range(0, W, 30):
        cv.line([(x, 76), (x, 94)], fill=(110, 116, 122), width=2)
    anchors = [rnd.uniform(40, W - 40) for _ in range(16)]
    for i, x in enumerate(anchors):
        x2 = x + rnd.uniform(-180, 180)
        cable(cv, (x, 92), (x2, 96 + rnd.uniform(0, 10)), sag=rnd.uniform(60, 190),
              color=rnd.choice(CABLE_COLORS), width=rnd.uniform(3, 6))
    for x in (520, 910, 1460):  # cables hanging straight down to the table
        col = rnd.choice(CABLE_COLORS)
        path = bezier((x, 94), (x + 30, 300), (x - 40, 420), (x + 10, 610), 50)
        cv.line(path, width=7.5)
        cv.line(path, fill=col, width=5)

    # floor
    cv.rect(0, 660, W, H, fill=(150, 150, 146), width=0)
    vx, vy = W / 2, 250
    for i in range(-14, 15):
        x = W / 2 + i * 150
        t = (660 - vy) / (H + 400 - vy)
        x_top = vx + (x * 3 - vx) * t
        cv.line([(x_top, 660), (vx + (x * 3 - vx), H + 400)], fill=(130, 130, 128), width=2)
    for y in (700, 750, 815, 900, 1010):
        cv.line([(0, y), (W, y)], fill=(130, 130, 128), width=2)
    for _ in range(40):  # scuffs and grime
        x, y = rnd.uniform(0, W), rnd.uniform(670, H)
        cv.ell(x, y, rnd.uniform(15, 70), rnd.uniform(4, 14), fill=(110, 108, 100, 45), width=0)
    cv.rect(0, 652, W, 666, fill=(70, 80, 90))  # skirting

    # laser warning sign, clock, whiteboard
    cv.rect(840, 118, 1080, 226, fill=(250, 250, 245), r=6)
    cv.poly([(880, 210), (920, 136), (960, 210)], fill=(250, 205, 30), width=4)
    cv.ell(920, 186, 8, 8, fill=INK, width=0)
    for a in range(0, 360, 45):
        r = math.radians(a)
        cv.line([(920 + 11 * math.cos(r), 186 + 11 * math.sin(r)), (920 + 17 * math.cos(r), 186 + 17 * math.sin(r))], width=2)
    cv.line([(920, 186), (950, 186)], width=3)
    cv.text(1020, 152, 'DANGER', 22, fill=(200, 30, 30))
    cv.text(1020, 180, 'LASER', 20)
    cv.text(1020, 204, 'CLASS 4', 14)

    cv.ell(1240, 170, 46, 46, fill=(245, 245, 240), width=5)
    cv.line([(1240, 170), (1240, 140)], width=4)
    cv.line([(1240, 170), (1262, 182)], width=3)

    # whiteboard covered in scribbles
    cv.rect(560, 120, 800, 300, fill=(240, 244, 242), width=5)
    for i in range(8):
        y = 140 + i * 18
        x0 = 575 + rnd.uniform(0, 20)
        path = [(x0 + k * 6, y + math.sin(k * 1.3 + i) * 3) for k in range(int(rnd.uniform(14, 34)))]
        cv.line(path, fill=rnd.choice([(40, 60, 160), (180, 40, 40), (30, 120, 60)]), width=2)
    cv.line([(700, 280), (720, 230), (740, 270), (760, 210), (780, 260)], fill=(180, 40, 40), width=2)
    cv.text(630, 286, 'E = h*nu ?!', 13, fill=(40, 60, 160), font='arial.ttf')
    # post-its
    for _ in range(9):
        x, y = rnd.uniform(560, 1120), rnd.uniform(110, 330)
        cv.poly(rot(x, y, 26, 26, rnd.uniform(-20, 20)), fill=rnd.choice([(250, 235, 90), (250, 150, 190), (130, 220, 160)]), width=1.5)

    # cobwebs in the corners
    for cx, cy, sx in ((0, 58, 1), (W, 58, -1)):
        for a in range(0, 91, 15):
            r = math.radians(a)
            cv.line([(cx, cy), (cx + sx * 170 * math.cos(r), cy + 170 * math.sin(r))], fill=(235, 235, 235, 150), width=1.5)
        for rad in (40, 75, 110, 150):
            arc = [(cx + sx * rad * math.cos(math.radians(a)) * (1 + 0.08 * math.sin(a)),
                    cy + rad * math.sin(math.radians(a))) for a in range(0, 91, 15)]
            cv.line(arc, fill=(235, 235, 235, 150), width=1.5)


# --------------------------------------------------------------------------- shelves
def draw_shelves(cv):
    x0, x1 = 30, 420
    cv.rect(x0, 130, x0 + 12, 650, fill=(110, 116, 124))
    cv.rect(x1 - 12, 130, x1, 650, fill=(110, 116, 124))
    levels = [210, 330, 450, 570]
    for lv in levels:
        cv.rect(x0, lv, x1, lv + 12, fill=(160, 166, 172))
    cv.poly([(x0 + 12, 330), (x0 + 12, 342), (x1 - 12, 352), (x1 - 12, 340)], fill=(160, 166, 172))  # bent shelf

    # top: boxes piled to the ceiling, one about to fall
    cv.rect(50, 150, 160, 210, fill=(200, 160, 110))
    cv.rect(70, 110, 150, 150, fill=(210, 170, 120))
    cv.poly(rot(270, 175, 110, 70, -8), fill=(190, 150, 100))
    cv.text(270, 175, 'SPARE', 16, fill=(90, 60, 30))
    cv.poly(rot(390, 160, 80, 60, 24), fill=(205, 165, 112))
    cv.text(390, 160, '?!', 18, fill=(90, 60, 30))

    # shelf 2: binders and flanges
    cols = [(200, 50, 50), (40, 90, 170), (230, 190, 40), (50, 140, 80), (120, 60, 140), (230, 120, 40)]
    x = 50
    for i in range(9):
        w = rnd.uniform(18, 28)
        ang = 0 if i < 5 else rnd.uniform(15, 35)
        cv.poly(rot(x + w / 2 + (8 if ang else 0), 272 + (6 if ang else 0), w, 110, ang), fill=rnd.choice(cols))
        x += w + (6 if ang else 1)
    for i, cx in enumerate((310, 350, 390)):
        cv.ell(cx, 300, 24, 24, fill=(190, 195, 200))
        cv.ell(cx, 300, 11, 11, fill=(110, 115, 120))

    # shelf 3: optics boxes, a laser head and a bundle of cables hanging down
    for i in range(5):
        cv.rect(50 + i * 52, 395 + rnd.uniform(-6, 6), 96 + i * 52, 450 if i != 2 else 440, fill=(60, 70, 90))
        cv.rect(56 + i * 52, 410, 90 + i * 52, 420, fill=(230, 230, 230), width=1)
    cv.rect(320, 400, 410, 450, fill=(40, 120, 70))
    cv.text(365, 425, 'HeNe', 14, fill=(240, 240, 240))
    for k in range(5):
        col = rnd.choice(CABLE_COLORS)
        path = bezier((330 + k * 10, 452), (300 + k * 20, 520), (370 - k * 8, 560), (340 + k * 12, 640), 40)
        cv.line(path, width=6.5)
        cv.line(path, fill=col, width=4)

    # shelf 4: vacuum parts, bellows, gloves
    for i in range(3):
        cx = 80 + i * 70
        cv.rect(cx - 25, 520, cx + 25, 570, fill=(185, 190, 196))
        cv.ell(cx, 520, 25, 9, fill=(210, 214, 220))
        cv.ell(cx, 520, 14, 5, fill=(90, 95, 100))
    for k in range(7):  # bellows
        cv.rect(270 + k * 12, 520, 282 + k * 12, 570, fill=(200, 205, 210) if k % 2 else (165, 170, 176), width=1.5)
    cv.ell(380, 560, 26, 12, fill=(80, 150, 220))  # glove box

    # sheets sticking out everywhere
    for _ in range(7):
        lv = rnd.choice(levels)
        cv.poly(rot(rnd.uniform(60, 400), lv + 10, 50, 36, rnd.uniform(-35, 35)), fill=(245, 245, 238), width=1.5)


# --------------------------------------------------------------------------- PC desk
def draw_desk(cv):
    # tower PCs under the desk
    cv.rect(60, 690, 150, 880, fill=(45, 48, 58))
    cv.ell(105, 715, 6, 6, fill=(80, 220, 120), width=1)
    for i in range(6):
        cv.line([(75, 760 + i * 12), (135, 760 + i * 12)], fill=(30, 30, 38), width=2)
    cv.rect(300, 720, 380, 880, fill=(200, 200, 205))
    cv.ell(340, 742, 5, 5, fill=(220, 60, 60), width=1)

    # desk
    cv.poly([(0, 640), (470, 640), (500, 680), (0, 680)], fill=(160, 120, 80))
    cv.rect(0, 680, 500, 700, fill=(120, 88, 58))
    cv.rect(20, 700, 40, 900, fill=(90, 90, 98))
    cv.rect(460, 700, 480, 890, fill=(90, 90, 98))

    # monitors
    cv.rect(110, 610, 130, 650, fill=(60, 60, 70))
    cv.rect(30, 470, 220, 612, fill=(30, 32, 40), r=6)
    cv.rect(40, 480, 210, 600, fill=(20, 30, 50), width=0)
    sp = [(45 + k * 4, 560 - 50 * math.exp(-((k - 20) / 6) ** 2) - rnd.uniform(0, 6)) for k in range(41)]
    cv.line(sp, fill=(80, 230, 250), width=2)
    cv.text(125, 495, 'fluorescence', 11, fill=(200, 220, 240), font='arial.ttf')

    cv.poly([(280, 612), (300, 612), (304, 652), (276, 652)], fill=(60, 60, 70))
    cv.poly(rot(290, 545, 200, 140, 4), fill=(30, 32, 40))
    cv.poly(rot(290, 545, 182, 122, 4), fill=(18, 40, 30), width=0)
    for k in range(5):
        y0 = 500 + k * 22
        cv.line([(210 + k * 2, y0), (300 + rnd.uniform(0, 60), y0 + 6)], fill=(110, 240, 140), width=2)
    # post-it covered monitor edge
    cv.poly(rot(380, 485, 30, 30, 12), fill=(250, 235, 90), width=1.5)
    cv.poly(rot(385, 520, 30, 30, -10), fill=(250, 150, 190), width=1.5)

    # keyboard, mouse, mugs, pizza box, papers
    cv.poly([(120, 655), (300, 655), (310, 672), (110, 672)], fill=(70, 72, 80))
    cv.ell(345, 664, 12, 7, fill=(70, 72, 80))
    for cx, col in ((420, (230, 230, 230)), (450, (200, 70, 60))):
        cv.rect(cx - 13, 615, cx + 13, 652, fill=col, r=4)
        cv.ell(cx, 615, 13, 4, fill=(80, 50, 30))
    cv.ell(398, 668, 30, 6, fill=(110, 70, 40, 160), width=0)  # coffee ring/spill
    for _ in range(9):
        cv.poly(rot(rnd.uniform(20, 480), rnd.uniform(640, 676), 60, 40, rnd.uniform(-40, 40)),
                fill=(248, 248, 240), width=1.5)
    # drawer hanging open
    cv.rect(320, 700, 450, 740, fill=(140, 104, 70))
    cv.poly(rot(380, 700, 70, 30, -15), fill=(245, 245, 238), width=1.5)
    cable(cv, (150, 700), (290, 760), sag=120, color=(25, 25, 30), width=5)
    cable(cv, (200, 650), (90, 880), sag=40, color=(25, 25, 30), width=5)


# --------------------------------------------------------------------------- optical table
TB = [(560, 560), (1440, 560)]   # back edge
TF = [(440, 760), (1560, 760)]   # front edge


def tp(u, v):
    """point on the optical table surface: u across (0..1), v back->front (0..1)"""
    xb = TB[0][0] + (TB[1][0] - TB[0][0]) * u
    xf = TF[0][0] + (TF[1][0] - TF[0][0]) * u
    return xb + (xf - xb) * v, TB[0][1] + (TF[0][1] - TB[0][1]) * v


def draw_table_base(cv):
    # legs with pneumatic isolators
    for lx in (490, 1510, 640, 1360):
        front = lx in (490, 1510)
        top = 800 if front else 770
        bottom = 990 if front else 900
        cv.rect(lx - 40, top, lx + 40, bottom, fill=(55, 60, 70) if front else (45, 48, 58))
        cv.rect(lx - 46, top + 20, lx + 46, top + 50, fill=(75, 80, 92))
    # turbo pump and roughing hose under the table
    cv.rect(960, 800, 1060, 900, fill=(190, 195, 200))
    cv.ell(1010, 800, 50, 14, fill=(215, 220, 225))
    cv.rect(980, 900, 1040, 920, fill=(120, 125, 130))
    hose = bezier((1040, 880), (1180, 1000), (1300, 900), (1420, 1000), 50)
    cv.line(hose, width=26)
    cv.line(hose, fill=(160, 166, 172), width=22)
    for i in range(0, len(hose), 2):
        x, y = hose[i]
        cv.line([(x - 6, y - 8), (x + 6, y + 8)], fill=(120, 126, 132), width=2)

    # top surface
    cv.poly([TB[0], TB[1], TF[1], TF[0]], fill=(70, 74, 84), width=4)
    for i in range(0, 41):
        for j in range(0, 15):
            x, y = tp(i / 40, j / 14)
            r = 1.4 + j * 0.1
            cv.ell(x, y, r, r * 0.7, fill=(40, 42, 50), width=0)
    # front face
    cv.poly([TF[0], TF[1], (1560, 800), (440, 800)], fill=(50, 54, 62), width=4)
    cv.text(1000, 780, 'ISOLATED OPTICAL TABLE  -  DO NOT LEAN', 13, fill=(140, 145, 155), font='arial.ttf')


def beam(cv, path, color):
    cv.line(path, fill=color + (55,), width=12)
    cv.line(path, fill=color + (130,), width=5.5)
    cv.line(path, fill=color, width=2.8)
    cv.line(path, fill=(255, 255, 255, 160), width=0.8)


def mpos(u, v):
    x, y = tp(u, v)
    return x, y - 50


def mirror(cv, u, v, ang=30, col=(170, 210, 240)):
    x, y = tp(u, v)
    cv.rect(x - 5, y - 40, x + 5, y, fill=(150, 156, 164), width=2)
    cv.rect(x - 9, y - 4, x + 9, y + 3, fill=(90, 95, 104), width=2)
    cv.poly(rot(x, y - 50, 26, 26, 0), fill=(40, 44, 54), width=2)
    cv.poly(rot(x, y - 50, 8, 22, ang), fill=col, width=2)
    return x, y - 50


def lens(cv, u, v):
    x, y = tp(u, v)
    cv.rect(x - 4, y - 34, x + 4, y, fill=(150, 156, 164), width=2)
    cv.ell(x, y - 46, 6, 15, fill=(200, 230, 250, 200), width=2)
    return x, y - 46


def laser_box(cv, u, v, w, h, col, label):
    x, y = tp(u, v)
    cv.rect(x, y - h, x + w, y, fill=col)
    cv.poly([(x, y - h), (x + 14, y - h - 10), (x + w + 14, y - h - 10), (x + w, y - h)], fill=shade(col, 1.25))
    cv.poly([(x + w, y - h), (x + w + 14, y - h - 10), (x + w + 14, y - 10), (x + w, y)], fill=shade(col, 0.75))
    cv.text(x + w / 2, y - h / 2, label, 14, fill=(250, 250, 250))
    cv.poly([(x + 8, y - 8), (x + 22, y - 8), (x + 15, y - 20)], fill=(250, 205, 30), width=1.5)
    return x + w, y - h / 2


def draw_table_top(cv):
    # back row: lasers
    out_r = laser_box(cv, 0.04, 0.12, 150, 50, (40, 110, 70), 'LASER 866')
    out_b = laser_box(cv, 0.06, 0.55, 130, 44, (60, 60, 150), 'LASER 397')
    out_g = laser_box(cv, 0.35, 0.05, 110, 40, (150, 50, 50), 'Ti:Sa')

    # vacuum chamber parts that sit behind beams
    cx, cy = tp(0.70, 0.38)
    cy -= 85
    # ion pump box behind chamber
    cv.rect(cx + 60, cy - 120, cx + 170, cy - 20, fill=(70, 110, 160))
    cv.text(cx + 115, cy - 70, 'ION PUMP', 12, fill=(240, 240, 240))
    cv.rect(cx + 40, cy - 80, cx + 70, cy - 50, fill=(185, 190, 196))

    m1, m2, m3, m4 = mpos(0.28, 0.12), mpos(0.30, 0.55), mpos(0.50, 0.30), mpos(0.46, 0.08)
    lx, ly = tp(0.42, 0.55)
    l1 = (lx, ly - 46)

    # beams (drawn before chamber front so they enter the viewport)
    beam(cv, [out_r, m1, (m1[0] + 10, m1[1] + 60)], (255, 60, 50))
    beam(cv, [(m1[0] + 10, m1[1] + 60), m3, (cx - 40, cy + 10)], (255, 60, 50))
    beam(cv, [out_b, m2, l1, (cx - 50, cy + 20)], (140, 80, 255))
    beam(cv, [out_g, (m4[0], out_g[1]), m4, (m4[0] + 140, m4[1] + 25), (cx - 30, cy - 10)], (60, 255, 120))
    # stray reflection off a dirty optic (bad!)
    beam(cv, [m3, (m3[0] - 120, m3[1] - 260)], (255, 60, 50))
    mirror(cv, 0.46, 0.08, -30)
    mirror(cv, 0.28, 0.12, 40)
    mirror(cv, 0.50, 0.30, 50, (200, 240, 200))
    mirror(cv, 0.30, 0.55, -40)
    lens(cv, 0.42, 0.55)

    # vacuum chamber: octagon with CF flanges and viewport with trapped ions
    R = 92
    oct_pts = [(cx + R * math.cos(math.radians(22.5 + 45 * k)), cy + R * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
    # pedestal
    cv.rect(cx - 30, cy + R - 10, cx + 30, cy + 95, fill=(160, 166, 172))
    # side ports
    for ang in (0, 45, 135, 180, 225, 315):
        r = math.radians(ang)
        px, py = cx + (R + 20) * math.cos(r), cy + (R + 20) * math.sin(r)
        cv.ell(px, py, 26, 26, fill=(190, 195, 202))
        for b in range(8):
            br = math.radians(b * 45)
            cv.ell(px + 20 * math.cos(br), py + 20 * math.sin(br), 2.5, 2.5, fill=(110, 115, 120), width=1)
        cv.ell(px, py, 13, 13, fill=(40, 60, 90, 230))
    # top tube with valve, gauge and a cable hanging off
    cv.rect(cx - 18, cy - R - 110, cx + 18, cy - R + 5, fill=(185, 190, 196))
    cv.rect(cx - 34, cy - R - 60, cx + 34, cy - R - 44, fill=(210, 214, 220))
    cv.rect(cx - 30, cy - R - 140, cx + 30, cy - R - 108, fill=(220, 70, 60))
    cv.text(cx, cy - R - 124, 'VALVE', 11, fill=(255, 255, 255))
    cv.rect(cx + 18, cy - R - 90, cx + 70, cy - R - 70, fill=(185, 190, 196))
    cv.ell(cx + 86, cy - R - 80, 18, 18, fill=(240, 240, 240))
    cv.line([(cx + 86, cy - R - 80), (cx + 94, cy - R - 92)], fill=(200, 30, 30), width=2)
    cv.poly(oct_pts, fill=(200, 205, 212), width=4)
    cv.poly([(x + (cx - x) * 0.18, y + (cy - y) * 0.18) for x, y in oct_pts], fill=(178, 184, 192), width=2)
    # bolt circle
    for b in range(16):
        br = math.radians(b * 22.5)
        cv.ell(cx + 66 * math.cos(br), cy + 66 * math.sin(br), 3.2, 3.2, fill=(120, 125, 130), width=1)
    # viewport: dark inside, ion trap electrodes, glowing ion chain
    cv.ell(cx, cy, 54, 54, fill=(18, 22, 40), width=4)
    glow = Image.new('RGBA', cv.img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([s(cx - 46), s(cy - 30), s(cx + 46), s(cy + 30)], fill=(90, 120, 255, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(s(14)))
    cv.img.paste(glow, (0, 0), glow)
    cv.d = ImageDraw.Draw(cv.img, 'RGBA')
    for dy in (-24, 24):
        cv.poly([(cx - 46, cy + dy - 6), (cx + 46, cy + dy - 6), (cx + 40, cy + dy * 0.55), (cx - 40, cy + dy * 0.55)],
                fill=(205, 170, 60), width=1.5)
    for k in range(-3, 4):
        x = cx + k * 9
        g = Image.new('RGBA', cv.img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse([s(x - 7), s(cy - 7), s(x + 7), s(cy + 7)], fill=(110, 170, 255, 255))
        g = g.filter(ImageFilter.GaussianBlur(s(3)))
        cv.img.paste(g, (0, 0), g)
        cv.d = ImageDraw.Draw(cv.img, 'RGBA')
        cv.ell(x, cy, 2.8, 2.8, fill=(235, 245, 255), width=0)
    cv.ell(cx - 20, cy - 36, 14, 5, fill=(255, 255, 255, 40), width=0)  # glass reflection
    # smudges/fingerprints on the viewport
    for _ in range(4):
        cv.ell(cx + rnd.uniform(-34, 34), cy + rnd.uniform(-40, -20), 7, 5, fill=(200, 200, 200, 18), width=0)

    # front clutter on the table: post holders, screws, allen keys, a coffee cup, papers, tape roll
    for u in (0.20, 0.55, 0.82, 0.92):
        x, y = tp(u, 0.85)
        cv.rect(x - 6, y - 26, x + 6, y, fill=(150, 156, 164), width=2)
    for _ in range(26):
        u, v = rnd.uniform(0.05, 0.97), rnd.uniform(0.62, 0.98)
        x, y = tp(u, v)
        if rnd.random() < 0.5:
            cv.ell(x, y, 4, 2.5, fill=(170, 175, 180), width=1.2)
        else:
            a = rnd.uniform(0, 180)
            cv.line([(x, y), (x + 12 * math.cos(math.radians(a)), y + 5 * math.sin(math.radians(a)))], fill=(170, 175, 180), width=3)
    for _ in range(3):
        x, y = tp(rnd.uniform(0.1, 0.9), rnd.uniform(0.7, 0.95))
        cv.line([(x, y), (x + 26, y + 2), (x + 26, y - 10)], fill=(40, 40, 48), width=3)
    x, y = tp(0.62, 0.86)
    cv.rect(x - 13, y - 30, x + 13, y, fill=(240, 240, 240), r=4)
    cv.ell(x, y - 30, 13, 4, fill=(80, 50, 30))
    cv.text(x, y - 15, 'I♥ions', 7, fill=(200, 40, 40))
    for _ in range(4):
        x, y = tp(rnd.uniform(0.2, 0.9), rnd.uniform(0.7, 0.95))
        cv.poly(rot(x, y, 54, 30, rnd.uniform(-30, 30)), fill=(248, 248, 240), width=1.5)
    x, y = tp(0.12, 0.88)
    cv.ell(x, y, 18, 8, fill=(230, 230, 220))
    cv.ell(x, y, 8, 3.5, fill=(60, 60, 60))

    # cables hanging off the table edges
    for _ in range(14):
        u = rnd.uniform(0.02, 0.98)
        p0 = tp(u, rnd.uniform(0.3, 0.9))
        p1 = (p0[0] + rnd.uniform(-200, 200), rnd.uniform(830, 1060))
        cable(cv, p0, p1, sag=rnd.uniform(40, 160), color=rnd.choice(CABLE_COLORS), width=rnd.uniform(3.5, 6))
    for _ in range(6):  # cables strung between items on the table
        p0 = tp(rnd.uniform(0.05, 0.9), rnd.uniform(0.1, 0.6))
        p1 = tp(rnd.uniform(0.05, 0.9), rnd.uniform(0.3, 0.9))
        cable(cv, p0, p1, sag=rnd.uniform(10, 60), color=rnd.choice(CABLE_COLORS), width=3.5)


# --------------------------------------------------------------------------- electronics rack
def draw_rack(cv):
    x0, x1, y0, y1 = 1600, 1880, 200, 930
    cv.rect(x0, y0, x1, y1, fill=(52, 56, 66), width=4)
    cv.rect(x0 + 12, y0 + 12, x1 - 12, y1 - 12, fill=(36, 38, 46), width=2)
    y = y0 + 20
    units = [
        ('scope', 130), ('psu', 60), ('wave', 70), ('blank', 30), ('psu', 60),
        ('lock', 80), ('psu', 60), ('blank', 40), ('wave', 70), ('ctrl', 90),
    ]
    for kind, h in units:
        if y + h > y1 - 20:
            break
        if kind == 'blank':
            y += h
            continue
        body = {'scope': (180, 184, 190), 'psu': (60, 64, 76), 'wave': (210, 210, 205),
                'lock': (40, 80, 130), 'ctrl': (80, 84, 96)}[kind]
        cv.rect(x0 + 16, y, x1 - 16, y + h - 4, fill=body, width=2.5)
        if kind == 'scope':
            cv.rect(x0 + 30, y + 12, x0 + 170, y + h - 16, fill=(15, 25, 20), width=2)
            tr = [(x0 + 34 + k * 3.4, y + 60 + 26 * math.sin(k * 0.45) * math.exp(-k / 30) + rnd.uniform(-3, 3)) for k in range(40)]
            cv.line(tr, fill=(90, 255, 120), width=2)
            tr = [(x0 + 34 + k * 3.4, y + 85 + (12 if (k // 6) % 2 else -12)) for k in range(40)]
            cv.line(tr, fill=(255, 220, 60), width=2)
            for k in range(6):
                cv.ell(x0 + 200 + (k % 2) * 30, y + 25 + (k // 2) * 30, 10, 10, fill=(70, 74, 84), width=2)
        else:
            cv.rect(x0 + 30, y + 10, x0 + 110, y + h - 16, fill=(20, 20, 24), width=2)
            cv.text(x0 + 70, y + (h - 6) / 2, f'{rnd.uniform(0, 99):05.2f}', 15,
                    fill=rnd.choice([(255, 80, 60), (80, 255, 120), (80, 200, 255)]), font='arial.ttf')
            for k in range(3):
                cv.ell(x0 + 140 + k * 32, y + h / 2 - 2, 9, 9, fill=(200, 200, 205) if kind != 'wave' else (60, 64, 76), width=2)
            cv.ell(x1 - 32, y + 14, 4, 4, fill=rnd.choice([(80, 255, 120), (255, 60, 60), (255, 200, 40)]), width=1)
        y += h
    # spaghetti of patch cables on the front
    for _ in range(18):
        p0 = (rnd.uniform(x0 + 30, x1 - 30), rnd.uniform(y0 + 40, y1 - 120))
        p1 = (rnd.uniform(x0 - 120, x1), rnd.uniform(p0[1], y1 + 120))
        cable(cv, p0, p1, sag=rnd.uniform(30, 120), color=rnd.choice(CABLE_COLORS), width=rnd.uniform(3, 5))
    # junk on top of the rack
    cv.rect(1630, 140, 1740, 200, fill=(200, 160, 110))
    cv.poly(rot(1800, 175, 90, 50, -10), fill=(60, 64, 76))
    cv.rect(1660, 110, 1700, 140, fill=(80, 150, 220), r=4)


# --------------------------------------------------------------------------- floor clutter
def flange(cv, x, y, r):
    cv.ell(x, y, r, r * 0.45, fill=(196, 200, 206))
    cv.ell(x, y, r * 0.5, r * 0.22, fill=(110, 115, 120))
    for b in range(8):
        a = math.radians(b * 45)
        cv.ell(x + r * 0.76 * math.cos(a), y + r * 0.34 * math.sin(a), 2.5, 1.5, fill=(100, 105, 110), width=0)


def sheet(cv, x, y, ang, w=70, h=50):
    cv.poly(rot(x, y, w, h, ang), fill=(248, 248, 240), width=1.5)
    for k in range(3):
        a = math.radians(ang)
        oy = -h / 4 + k * h / 5
        cx, cy = x - oy * math.sin(a), y + oy * math.cos(a)
        cv.line([(cx - w * 0.35 * math.cos(a), cy - w * 0.35 * math.sin(a)),
                 (cx + w * 0.3 * math.cos(a), cy + w * 0.3 * math.sin(a))], fill=(150, 160, 190), width=1.5)


def screw(cv, x, y):
    a = rnd.uniform(0, 180)
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    cv.line([(x, y), (x + 14 * ca, y + 6 * sa)], fill=(160, 165, 170), width=3.5)
    cv.ell(x, y, 4.5, 3, fill=(175, 180, 186), width=1.2)


def nut(cv, x, y):
    hexp = [(x + 5 * math.cos(math.radians(60 * k)), y + 3 * math.sin(math.radians(60 * k))) for k in range(6)]
    cv.poly(hexp, fill=(180, 184, 190), width=1.2)
    cv.ell(x, y, 2, 1.2, fill=(90, 90, 96), width=0)


def dust_bunny(cv, x, y, r):
    for _ in range(14):
        cv.ell(x + rnd.uniform(-r, r), y + rnd.uniform(-r * 0.4, r * 0.4), r * 0.5, r * 0.3, fill=(120, 118, 112, 90), width=0)
    for _ in range(8):
        a = rnd.uniform(0, 6.28)
        cv.line([(x, y), (x + r * 1.3 * math.cos(a), y + r * 0.6 * math.sin(a))], fill=(110, 108, 104, 120), width=1)


def draw_floor_clutter(cv):
    # stuff partly behind (y < 960)
    flange(cv, 700, 1000, 46)
    flange(cv, 760, 1040, 30)
    flange(cv, 1240, 940, 36)
    # vacuum nipple / tee lying around
    cv.poly(rot(860, 940, 140, 40, -12), fill=(190, 195, 202))
    cv.ell(*rot(860, 940, 140, 40, -12)[1], 6, 6, fill=None, width=0)
    cv.ell(928, 926, 12, 22, fill=(210, 214, 220))
    cv.ell(928, 926, 6, 12, fill=(100, 105, 110))
    # open toolbox
    cv.poly([(1280, 1000), (1440, 1000), (1430, 1070), (1290, 1070)], fill=(200, 40, 40))
    cv.poly([(1280, 1000), (1440, 1000), (1460, 960), (1300, 960)], fill=(160, 30, 30))
    cv.line([(1320, 990), (1340, 950)], fill=(240, 200, 40), width=5)
    cv.line([(1370, 995), (1400, 945)], fill=(60, 120, 220), width=6)
    # cardboard box spilling packing peanuts and foam
    cv.poly([(80, 930), (260, 930), (250, 1040), (90, 1040)], fill=(200, 160, 110))
    cv.poly([(80, 930), (40, 890), (200, 890), (260, 930)], fill=(220, 180, 125))
    cv.poly([(260, 930), (300, 900), (290, 1010), (250, 1040)], fill=(170, 130, 85))
    cv.text(170, 990, 'FRAGILE', 16, fill=(160, 40, 40))
    for _ in range(26):
        cv.ell(rnd.uniform(30, 420), rnd.uniform(1000, 1070), 7, 4, fill=(245, 240, 225), width=1)
    # gas bottle leaning, chained badly
    cv.rect(1500, 760, 1570, 990, fill=(60, 130, 80), r=30)
    cv.rect(1520, 726, 1550, 762, fill=(170, 175, 180))
    cv.rect(1510, 712, 1560, 726, fill=(120, 125, 130), r=4)
    cv.rect(1500, 800, 1570, 820, fill=(240, 240, 240), width=1.5)
    cv.text(1535, 810, 'He', 13)
    cv.line([(1480, 850), (1530, 870), (1590, 840)], fill=(150, 150, 150), width=3)
    # coffee cup knocked over with a spill
    cv.ell(1150, 1035, 70, 18, fill=(120, 80, 45, 170), width=0)
    cv.poly(rot(1100, 1025, 44, 30, -70), fill=(240, 240, 240))
    # pizza box
    cv.poly([(540, 1030), (700, 1010), (740, 1070), (560, 1080)], fill=(210, 170, 120))
    cv.text(640, 1048, 'PIZZA', 13, fill=(170, 40, 40))
    # cable reel and coiled cables
    cv.ell(1820, 1010, 50, 50, fill=(220, 120, 40))
    cv.ell(1820, 1010, 18, 18, fill=(90, 60, 30))
    for k in range(4):
        cv.ell(980 + k * 4, 1035, 50 - k * 8, 18 - k * 3, fill=None, width=4)

    # sheets, screws, nuts, crumpled paper, allen keys, gaskets and dust everywhere
    for _ in range(15):
        sz = rnd.uniform(0.7, 1.2)
        sheet(cv, rnd.uniform(0, W), rnd.uniform(860, 1075), rnd.uniform(-60, 60), 70 * sz, 50 * sz)
    for _ in range(14):
        x, y, r = rnd.uniform(0, W), rnd.uniform(880, 1075), rnd.uniform(8, 14)
        cv.ell(x, y, r, r * 0.8, fill=(235, 235, 228))
        for _ in range(3):
            cv.line([(x - r * 0.6, y + rnd.uniform(-r * 0.4, r * 0.4)), (x + r * 0.5, y + rnd.uniform(-r * 0.4, r * 0.4))],
                    fill=(170, 170, 165), width=1.2)
    for _ in range(90):
        screw(cv, rnd.uniform(0, W), rnd.uniform(860, 1078))
    for _ in range(70):
        nut(cv, rnd.uniform(0, W), rnd.uniform(860, 1078))
    for _ in range(10):
        x, y = rnd.uniform(0, W), rnd.uniform(880, 1075)
        a = rnd.uniform(0, 180)
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        cv.line([(x, y), (x + 36 * ca, y + 14 * sa), (x + 36 * ca - 10 * sa, y + 14 * sa + 8 * ca)], fill=(40, 40, 48), width=3.5)
    for _ in range(8):
        x, y = rnd.uniform(0, W), rnd.uniform(880, 1075)
        cv.ell(x, y, 16, 7, fill=None, outline=(200, 140, 60), width=3)
    for _ in range(14):
        dust_bunny(cv, rnd.uniform(0, W), rnd.uniform(850, 1070), rnd.uniform(10, 22))


# --------------------------------------------------------------------------- atmosphere
def atmosphere(img):
    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    # dusty haze in the air
    for _ in range(700):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.uniform(0.5, 1.8)
        d.ellipse([s(x - r), s(y - r), s(x + r), s(y + r)], fill=(255, 250, 230, rnd.randint(25, 80)))
    # grey dust film on the floor and table
    for _ in range(2500):
        x, y = rnd.uniform(0, W), rnd.uniform(560, H)
        r = rnd.uniform(0.6, 1.6)
        d.ellipse([s(x - r), s(y - r), s(x + r), s(y + r)], fill=(190, 185, 170, rnd.randint(30, 90)))
    # light shafts from the ceiling lamp
    shaft = Image.new('RGBA', img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shaft)
    sd.polygon(pts([(300, 62), (620, 62), (900, 1080), (0, 1080)]), fill=(255, 250, 220, 26))
    shaft = shaft.filter(ImageFilter.GaussianBlur(s(30)))
    img.paste(shaft, (0, 0), shaft)
    img.paste(over, (0, 0), over)
    # vignette
    vig = Image.new('L', (W // 8, H // 8), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-W // 16, -H // 16, W // 8 + W // 16, H // 8 + H // 16], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(14)).resize(img.size)
    dark = Image.new('RGBA', img.size, (25, 20, 35, 255))
    mask = vig.point(lambda v: int((255 - v) * 0.55))
    img.paste(dark, (0, 0), mask)


def main():
    img = Image.new('RGB', (s(W), s(H)), (0, 0, 0))
    cv = Canvas(img)
    draw_room(cv)
    draw_shelves(cv)
    draw_rack(cv)
    draw_table_base(cv)
    draw_table_top(cv)
    draw_desk(cv)
    draw_floor_clutter(cv)
    atmosphere(img)
    out = img.convert('RGB').resize((W, H), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, quality=88, optimize=True, progressive=False)
    print('wrote', os.path.abspath(OUT), os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
