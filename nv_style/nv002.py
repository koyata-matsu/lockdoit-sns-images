"""NeuronVisuals風 v2「モンキートラップ」— 立体感・質感・カメラワーク・効果音つき
python3 nv002.py <wavフォルダ> <出力mp4> [--frames]
"""
import math
import subprocess
import sys
import wave
from pathlib import Path

import cairo
import numpy as np

W, H, FPS = 1080, 1920, 30
SR = 48000
LEAD, GAP = 0.35, 0.40
RED = (0.93, 0.30, 0.30)
YEL = (0.98, 0.80, 0.30)
BLUE = (0.42, 0.68, 1.0)

# (字幕, 赤くする言葉)
LINES = [
    ("猿を捕まえる、昔ながらの罠がある。", "罠"),
    ("小さな穴の空いた壺に、\nバナナを一本入れておくだけ。", "バナナ"),
    ("猿は手を入れて、バナナをつかむ。", "つかむ"),
    ("でも、握ったままだと、手が抜けない。", "抜けない"),
    ("放せば、逃げられる。\nなのに、放さない。", "放さない"),
    ("そして、捕まる。", "捕まる"),
    ("僕らも毎日、スマホで\n同じことをしてる。", "スマホ"),
    ("あと一本だけ。あと五分だけ。", "五分だけ"),
    ("握っているのは、ほんの小さな楽しみ。", "小さな楽しみ"),
    ("失っているのは、今日という一日。", "今日という一日"),
    ("手を放そう。\nやることが終わるまで。", "手を放そう"),
    ("だから、ToDoリストオタクの僕は、\nアプリを作った。", "アプリを作った"),
    ("今日のToDoが全部終わるまで、\nSNSが開かない。", "SNSが開かない"),
    ("終わったら、ロック解除。\n好きなだけ見ていい。", "ロック解除"),
    ("スマホに奪われた一日を、\n取り戻そう。", "取り戻そう"),
]

from PIL import Image as _PILImage
_SHOTS = {}


def shot(name):
    if name not in _SHOTS:
        im = _PILImage.open(Path(__file__).parent.parent / "assets" / "app_screens" / f"{name}.png").convert("RGBA")
        im = im.resize((603, 1311))
        arr = np.array(im)[:, :, [2, 1, 0, 3]].copy()
        surf = cairo.ImageSurface.create_for_data(memoryview(arr), cairo.FORMAT_ARGB32, im.width, im.height, im.width * 4)
        _SHOTS[name] = (surf, arr)
    return _SHOTS[name][0]


def draw_shot_phone(c, name, x, y, s, a, rot=0.0):
    sw, sh = 603, 1311
    c.save(); c.translate(x, y); c.rotate(rot); c.scale(s, s)
    # 影と光
    c.set_source(rg(c, 0, 0, 50, 900, [(0, (*YEL, 0.18 * a)), (1, (*YEL, 0))])); c.paint()
    for k in range(6):
        c.new_path(); c.rectangle(-sw / 2 - 20 - k * 6 + 30, -sh / 2 - 20 - k * 6 + 40, sw + 40 + k * 12, sh + 40 + k * 12)
        c.set_source_rgba(0, 0, 0, 0.08 * a); c.fill()
    bw = 22
    def rr(x0, y0, w0, h0, r):
        c.new_path()
        c.arc(x0 + r, y0 + r, r, math.pi, 1.5 * math.pi); c.arc(x0 + w0 - r, y0 + r, r, 1.5 * math.pi, 2 * math.pi)
        c.arc(x0 + w0 - r, y0 + h0 - r, r, 0, 0.5 * math.pi); c.arc(x0 + r, y0 + h0 - r, r, 0.5 * math.pi, math.pi); c.close_path()
    rr(-sw / 2 - bw, -sh / 2 - bw, sw + 2 * bw, sh + 2 * bw, 90)
    c.set_source(lg(c, -sw / 2, 0, sw / 2, 0, [(0, (0.22, 0.23, 0.26, a)), (0.5, (0.50, 0.52, 0.56, a)), (1, (0.18, 0.19, 0.22, a))])); c.fill()
    rr(-sw / 2, -sh / 2, sw, sh, 70); c.clip()
    c.set_source_surface(shot(name), -sw / 2, -sh / 2); c.paint_with_alpha(a)
    c.restore()


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def back(x):  # 少し行きすぎて戻る
    x = max(0.0, min(1.0, x))
    s = 1.70158
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def lerp(a, b, x):
    return a + (b - a) * x


def lg(c, x0, y0, x1, y1, stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for o, col in stops:
        g.add_color_stop_rgba(o, *col)
    return g


def rg(c, cx, cy, r0, r1, stops, fx=None, fy=None):
    g = cairo.RadialGradient(fx if fx is not None else cx, fy if fy is not None else cy, r0, cx, cy, r1)
    for o, col in stops:
        g.add_color_stop_rgba(o, *col)
    return g


def soft_shadow(c, x, y, rx, ry, a):
    for k in range(6):
        f = 1 + k * 0.22
        c.save(); c.translate(x, y); c.scale(rx * f, ry * f)
        c.new_path(); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
        c.set_source_rgba(0, 0, 0, 0.10 * a)
        c.fill()


# ---------- 背景 ----------
def background(c, t, warm=0.0):
    c.set_source_rgb(0.035, 0.035, 0.045); c.paint()
    # 上からのスポットライト
    c.set_source(rg(c, W / 2, 700, 50, 1150, [(0, (0.30 + 0.08 * warm, 0.30, 0.33 - 0.05 * warm, 0.55)), (1, (0, 0, 0, 0))]))
    c.paint()
    # 床
    c.set_source(lg(c, 0, 1240, 0, 1920, [(0, (0.10, 0.10, 0.12, 1)), (1, (0.02, 0.02, 0.03, 1))]))
    c.rectangle(0, 1240, W, 680); c.fill()
    c.set_source(lg(c, 0, 1236, W, 1236, [(0, (1, 1, 1, 0)), (0.5, (1, 1, 1, 0.10)), (1, (1, 1, 1, 0))]))
    c.rectangle(0, 1236, W, 3); c.fill()
    # ほこり
    rng = np.random.default_rng(3)
    for k in range(28):
        x0, y0, sp = rng.uniform(0, W), rng.uniform(300, 1300), rng.uniform(8, 25)
        x = (x0 + math.sin(t * 0.3 + k) * 30) % W
        y = (y0 - t * sp) % 1100 + 250
        c.set_source_rgba(1, 1, 1, 0.10 + 0.08 * math.sin(t + k))
        c.new_path(); c.arc(x, y, rng.uniform(1.5, 3.5), 0, 2 * math.pi); c.fill()


# ---------- 部品 ----------
CX, CY = 540, 980
FLOOR = 1238


def jar_path(c):
    c.new_path()
    c.move_to(CX - 72, CY - 262)
    c.line_to(CX - 72, CY - 205)
    c.curve_to(CX - 255, CY - 170, CX - 262, CY + 225, CX - 150, CY + 252)
    c.line_to(CX + 150, CY + 252)
    c.curve_to(CX + 262, CY + 225, CX + 255, CY - 170, CX + 72, CY - 205)
    c.line_to(CX + 72, CY - 262)
    c.close_path()


def draw_jar_back(c, a):
    soft_shadow(c, CX, FLOOR + 6, 210, 26, a)
    jar_path(c)
    c.set_source(lg(c, CX - 260, 0, CX + 260, 0, [
        (0, (0.55, 0.36, 0.22, 0.95 * a)), (0.35, (0.78, 0.55, 0.35, 0.95 * a)),
        (0.7, (0.50, 0.32, 0.20, 0.95 * a)), (1, (0.25, 0.15, 0.10, 0.95 * a))]))
    c.fill()
    # 胴の帯模様
    c.save(); jar_path(c); c.clip()
    for yy, h in ((CY - 60, 16), (CY + 120, 10)):
        c.set_source_rgba(0.20, 0.12, 0.08, 0.6 * a); c.rectangle(0, yy, W, h); c.fill()
    # ハイライト
    c.set_source(lg(c, CX - 200, 0, CX - 120, 0, [(0, (1, 1, 1, 0)), (0.5, (1, 1, 1, 0.22 * a)), (1, (1, 1, 1, 0))]))
    c.rectangle(CX - 200, CY - 150, 80, 360); c.fill()
    c.restore()
    # 口（穴の中は暗い）
    c.save(); c.translate(CX, CY - 262); c.scale(96, 22)
    c.new_path(); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
    c.set_source_rgba(0.62, 0.42, 0.26, a); c.fill()
    c.save(); c.translate(CX, CY - 260); c.scale(70, 14)
    c.new_path(); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
    c.set_source_rgba(0.04, 0.03, 0.03, a); c.fill()


def draw_banana(c, x, y, a, rot=0.0, scale=1.0):
    c.save(); c.translate(x, y); c.rotate(rot); c.scale(scale, scale)
    c.new_path()
    c.move_to(-85, -12)
    c.curve_to(-45, 55, 45, 55, 85, -12)
    c.curve_to(45, 22, -45, 22, -85, -12)
    c.set_source(lg(c, 0, -10, 0, 45, [(0, (1.0, 0.92, 0.45, a)), (1, (0.85, 0.60, 0.10, a))]))
    c.fill_preserve()
    c.set_source_rgba(0.45, 0.30, 0.05, a); c.set_line_width(3); c.stroke()
    c.set_source_rgba(0.30, 0.20, 0.05, a)
    c.new_path(); c.arc(85, -12, 7, 0, 2 * math.pi); c.fill()
    c.restore()


def draw_monkey(c, x, y, a, tilt=0.0, scared=0.0):
    soft_shadow(c, x + 10, FLOOR + 4, 120, 18, a * 0.8)
    c.save(); c.translate(x, y); c.rotate(tilt)
    fur = [(0, (0.62, 0.45, 0.32, a)), (1, (0.30, 0.20, 0.13, a))]
    # 体
    c.save(); c.translate(0, 210); c.scale(95, 120)
    c.new_path(); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
    c.set_source(rg(c, -30, 150, 10, 170, fur)); c.fill()
    for ex in (-82, 82):  # 耳
        c.new_path(); c.arc(ex, -8, 30, 0, 2 * math.pi)
        c.set_source(rg(c, ex - 8, -16, 4, 34, fur)); c.fill()
        c.new_path(); c.arc(ex, -8, 16, 0, 2 * math.pi)
        c.set_source_rgba(0.86, 0.68, 0.55, a); c.fill()
    c.new_path(); c.arc(0, 0, 78, 0, 2 * math.pi)
    c.set_source(rg(c, -25, -30, 8, 95, fur)); c.fill()
    c.save(); c.translate(0, 20); c.scale(52, 48)  # 顔
    c.new_path(); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
    c.set_source(rg(c, -10, 5, 4, 60, [(0, (0.95, 0.80, 0.68, a)), (1, (0.78, 0.60, 0.48, a))])); c.fill()
    for ex in (-20, 20):
        c.new_path(); c.arc(ex, 8, 7 + 3 * scared, 0, 2 * math.pi)
        c.set_source_rgba(0.08, 0.05, 0.04, a); c.fill()
        c.new_path(); c.arc(ex + 2, 5, 2.2, 0, 2 * math.pi)
        c.set_source_rgba(1, 1, 1, 0.9 * a); c.fill()
    c.set_source_rgba(0.25, 0.15, 0.10, a); c.set_line_width(4)
    c.new_path()
    if scared > 0.5:
        c.arc(0, 48, 10, 0, 2 * math.pi)
    else:
        c.arc(0, 32, 14, 0.15 * math.pi, 0.85 * math.pi)
    c.stroke()
    c.restore()


def draw_arm(c, x0, y0, x1, y1, a, fist=False, fist_r=34, human=False):
    mx, my = (x0 + x1) / 2, min(y0, y1) - 70
    path = lambda: (c.new_path(), c.move_to(x0, y0), c.curve_to(mx, my, mx, my, x1, y1))
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    if human:
        base, light = (0.20, 0.24, 0.32), (0.36, 0.42, 0.55)
        skin = [(0, (0.98, 0.84, 0.72, a)), (1, (0.78, 0.58, 0.46, a))]
    else:
        base, light = (0.30, 0.20, 0.13), (0.58, 0.42, 0.30)
        skin = [(0, (0.92, 0.76, 0.62, a)), (1, (0.70, 0.52, 0.40, a))]
    path(); c.set_line_width(36); c.set_source_rgba(*base, a); c.stroke()
    path(); c.set_line_width(14); c.set_source_rgba(*light, 0.7 * a); c.stroke()
    r = fist_r if fist else 28
    c.new_path(); c.arc(x1, y1, r, 0, 2 * math.pi)
    c.set_source(rg(c, x1, y1, 2, r, skin, fx=x1 - r * 0.35, fy=y1 - r * 0.35)); c.fill()


def draw_phone(c, x, y, a, glow=0.0, scroll=0.0):
    w, h = 126, 230
    if glow > 0:
        c.set_source(rg(c, x, y, 10, 340, [(0, (*BLUE, 0.45 * glow * a)), (1, (*BLUE, 0))])); c.paint()

    def rr(x0, y0, w0, h0, r):
        c.new_path()
        c.arc(x0 + r, y0 + r, r, math.pi, 1.5 * math.pi)
        c.arc(x0 + w0 - r, y0 + r, r, 1.5 * math.pi, 2 * math.pi)
        c.arc(x0 + w0 - r, y0 + h0 - r, r, 0, 0.5 * math.pi)
        c.arc(x0 + r, y0 + h0 - r, r, 0.5 * math.pi, math.pi)
        c.close_path()
    rr(x - w / 2, y - h / 2, w, h, 24)
    c.set_source(lg(c, x - w / 2, 0, x + w / 2, 0, [(0, (0.25, 0.27, 0.30, a)), (0.5, (0.55, 0.57, 0.62, a)), (1, (0.20, 0.21, 0.24, a))]))
    c.fill()
    rr(x - w / 2 + 9, y - h / 2 + 12, w - 18, h - 24, 16)
    c.set_source(lg(c, 0, y - h / 2, 0, y + h / 2, [(0, (0.10, 0.18, 0.32, a)), (1, (0.05, 0.08, 0.16, a))]))
    c.fill_preserve()
    c.save(); c.clip()
    for i in range(-2, 10):
        yy = y - h / 2 + 30 + ((i * 38 - scroll) % 340) - 50
        c.set_source_rgba(0.85, 0.90, 1.0, 0.55 * a); c.rectangle(x - w / 2 + 22, yy, 26, 26); c.fill()
        c.set_source_rgba(*BLUE, 0.6 * a); c.rectangle(x - w / 2 + 54, yy + 3, w - 80, 8); c.fill()
        c.set_source_rgba(*BLUE, 0.35 * a); c.rectangle(x - w / 2 + 54, yy + 15, w - 100, 7); c.fill()
    c.restore()


def draw_heart(c, x, y, s, a):
    c.save(); c.translate(x, y); c.scale(s, s)
    c.new_path(); c.move_to(0, 12)
    c.curve_to(-26, -6, -14, -28, 0, -12); c.curve_to(14, -28, 26, -6, 0, 12)
    c.set_source(rg(c, -6, -10, 1, 26, [(0, (1, 0.55, 0.55, a)), (1, (*RED, a))])); c.fill(); c.restore()


def draw_check(c, x, y, a, p):
    c.new_path(); c.rectangle(x - 36, y - 36, 72, 72)
    c.set_source(lg(c, 0, y - 36, 0, y + 36, [(0, (0.22, 0.22, 0.26, a)), (1, (0.12, 0.12, 0.15, a))]))
    c.fill_preserve(); c.set_source_rgba(0.6, 0.6, 0.65, a); c.set_line_width(3); c.stroke()
    if p > 0:
        c.set_line_width(11); c.set_line_cap(cairo.LINE_CAP_ROUND)
        pts = [(x - 20, y), (x - 4, y + 18), (x + 26, y - 22)]
        c.new_path(); c.move_to(*pts[0])
        if p < 0.5:
            q = p / 0.5; c.line_to(lerp(pts[0][0], pts[1][0], q), lerp(pts[0][1], pts[1][1], q))
        else:
            q = (p - 0.5) / 0.5; c.line_to(*pts[1]); c.line_to(lerp(pts[1][0], pts[2][0], q), lerp(pts[1][1], pts[2][1], q))
        c.set_source_rgba(*YEL, a); c.stroke()


def draw_lock(c, x, y, s, a):
    c.save(); c.translate(x, y); c.scale(s, s)
    c.set_source(rg(c, 0, 20, 5, 200, [(0, (*YEL, 0.35 * a)), (1, (*YEL, 0))])); c.paint()
    c.set_line_width(16); c.set_source_rgba(0.75, 0.75, 0.80, a)
    c.new_path(); c.arc(0, -30, 38, math.pi, 2 * math.pi); c.stroke()
    c.move_to(-38, -30); c.line_to(-38, -6); c.stroke(); c.move_to(38, -30); c.line_to(38, -6); c.stroke()
    c.new_path(); c.rectangle(-62, -8, 124, 92)
    c.set_source(lg(c, 0, -8, 0, 84, [(0, (1.0, 0.86, 0.40, a)), (1, (0.85, 0.58, 0.12, a))])); c.fill()
    c.new_path(); c.arc(0, 30, 10, 0, 2 * math.pi); c.set_source_rgba(0.3, 0.2, 0.05, a); c.fill()
    c.restore()


def draw_bars(c, q, a):
    for i in range(10):
        x = 120 + i * 93
        c.new_path(); c.rectangle(x - 9, 360, 18, lerp(0, FLOOR - 360, q))
        c.set_source(lg(c, x - 9, 0, x + 9, 0, [(0, (0.25, 0.26, 0.28, a)), (0.4, (0.80, 0.82, 0.86, a)), (1, (0.20, 0.21, 0.23, a))]))
        c.fill()
    c.new_path(); c.rectangle(100, 340, 880, 30)
    c.set_source(lg(c, 0, 340, 0, 370, [(0, (0.85, 0.86, 0.90, a)), (1, (0.30, 0.31, 0.34, a))])); c.fill()


def font(c, size, bold=True, mono=False):
    fam = "Noto Sans Mono CJK JP" if mono else "Noto Sans CJK JP"
    c.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)


def caption(c, s, hl, y, a):
    font(c, 56)
    for i, ln in enumerate(s.split("\n")):
        parts = [(ln, (1, 1, 1))]
        if hl and hl in ln:
            p0, p1 = ln.split(hl, 1); parts = [(p0, (1, 1, 1)), (hl, RED), (p1, (1, 1, 1))]
        tw = sum(c.text_extents(p).x_advance for p, _ in parts)
        x = (W - tw) / 2; yy = y + i * 82
        for p, col in parts:
            c.move_to(x + 3, yy + 4); c.set_source_rgba(0, 0, 0, 0.7 * a); c.show_text(p)
            c.move_to(x, yy); c.set_source_rgba(*col, a); c.show_text(p)
            x += c.text_extents(p).x_advance


def hud(c, label, t, a, alarm=False, bpm=70):
    # 上の心電図パネル
    x0, y0, w, h = 340, 250, 400, 120
    c.new_path(); c.rectangle(x0, y0, w, h)
    c.set_source_rgba(0.06, 0.06, 0.08, 0.85 * a); c.fill_preserve()
    c.set_source_rgba(*(RED if alarm else (0.5, 0.5, 0.55)), 0.9 * a); c.set_line_width(3); c.stroke()
    c.save(); c.rectangle(x0 + 4, y0 + 4, w - 8, h - 8); c.clip()
    c.new_path()
    period = 60 / bpm * 160
    for k in range(0, w, 3):
        ph = ((k + t * 160) % period) / period
        v = 0
        if 0.40 < ph < 0.44: v = -38
        elif 0.44 < ph < 0.48: v = 28
        elif 0.36 < ph < 0.40: v = -8
        yy = y0 + h * 0.62 + v
        (c.line_to if k else c.move_to)(x0 + k, yy)
    c.set_source_rgba(*(RED if alarm else (0.55, 1.0, 0.65)), a); c.set_line_width(4); c.stroke()
    c.restore()
    font(c, 30, mono=True)
    c.move_to(x0 + 14, y0 + 38); c.set_source_rgba(1, 1, 1, 0.85 * a); c.show_text(label)


# ---------- タイムライン ----------
def build_timeline(durs):
    starts, t = [], LEAD
    for d in durs:
        starts.append(t); t += d + GAP
    return starts, t + 0.8


def frame(c, t, starts, durs, total):
    def P(i, a=0.0, b=1.0):
        s, d = starts[i], durs[i] + GAP
        return ease(((t - s) / d - a) / (b - a))

    def active(i):
        return t >= starts[i]

    part2 = t >= starts[6]
    background(c, t)
    # カメラ：ゆっくり寄る＋衝撃で揺れる
    zoom = 1.0 + 0.06 * ((t - (starts[6] if part2 else 0)) / 20.0)
    shake = 0.0
    if active(5) and not part2:
        dt = t - (starts[5] + 0.35 * (durs[5] + GAP))
        if 0 < dt < 0.5:
            shake = 14 * math.exp(-dt * 8) * math.sin(dt * 70)
    c.save()
    c.translate(W / 2, CY); c.scale(zoom, zoom); c.translate(-W / 2, -CY + shake)

    MONKEY = (CX - 300, CY - 40)
    BIN = (CX, CY + 150)
    if not part2:
        fade = 1 - P(5, 0.78, 1.0) if active(5) else 1.0
        a = P(0, 0, 0.35) * fade
        scared = 1.0 if active(5) else 0.0
        draw_monkey(c, *MONKEY, P(0, 0.15, 0.55) * fade, 0.05 * math.sin(t * 2.0), scared)
        draw_jar_back(c, a)
        if active(1) and not active(2):
            q = back(P(1, 0.25, 0.7))
            draw_banana(c, CX, lerp(CY - 560, BIN[1], min(1, q)), a, rot=(1 - q) * 0.8)
        if active(2):
            reach = P(2, 0.0, 0.7)
            hy = lerp(CY - 330, BIN[1] - 10, reach)
            grabbed = reach >= 1
            if active(3):
                stop = 1 - (P(5, 0.0, 0.4) if active(5) else 0)
                hy = lerp(BIN[1] - 10, CY - 215, P(3, 0.0, 0.25)) + math.sin((t - starts[3]) * 16) * 16 * stop
            # 壺の口から中は暗く見せる（腕は壺の上に描く）
            if grabbed:
                draw_banana(c, CX, hy + 20, a, scale=0.7)
            draw_arm(c, MONKEY[0] + 70, MONKEY[1] - 10, CX, hy, a, fist=grabbed, fist_r=55 if grabbed else 28)
            if active(3) and not active(5):
                for k, (dx, dy) in enumerate(((-110, -60), (110, -70))):
                    q = ((t - starts[3]) * 2 + k * 0.5) % 1
                    c.set_source_rgba(*RED, (1 - q) * a); c.set_line_width(6)
                    c.new_path(); c.move_to(CX + dx, CY - 230 + dy - q * 30); c.line_to(CX + dx * 1.25, CY - 250 + dy - q * 30); c.stroke()
        if active(4) and not active(5):
            q = P(4, 0.05, 0.35) * (1 - P(4, 0.5, 0.75))
            if q > 0.01:
                c.set_dash([16, 14])
                c.set_source_rgba(1, 1, 1, 0.5 * q); c.set_line_width(6)
                c.new_path(); c.move_to(CX, CY - 230); c.curve_to(CX + 80, CY - 420, CX + 230, CY - 470, CX + 320, CY - 440); c.stroke()
                c.set_dash([])
                font(c, 34, mono=True); c.move_to(CX + 210, CY - 480); c.set_source_rgba(1, 1, 1, 0.7 * q); c.show_text("EXIT")
        if active(5):
            draw_bars(c, back(P(5, 0.0, 0.35)), fade)
    else:
        a = P(6, 0, 0.3) * (1 - (P(11, 0.0, 0.3) if active(11) else 0))
        draw_jar_back(c, a)
        PH = (CX, CY + 90)
        release = P(10, 0.05, 0.4) if active(10) else 0.0
        glow = (0.6 + 0.4 * math.sin(t * 5)) * (1 - release)
        draw_phone(c, PH[0], PH[1] + release * 30, a, glow=glow, scroll=(t - starts[6]) * 260 * (1 - release))
        hy = lerp(CY - 330, PH[1] - 70, P(6, 0.15, 0.6))
        if active(10):
            hy = lerp(PH[1] - 70, CY - 560, P(10, 0.2, 0.7))
        draw_arm(c, W + 60, CY - 600, CX, hy, a, fist=not active(10), fist_r=50, human=True)
        if active(8) and not active(10):
            for k in range(7):
                ph = ((t - starts[8]) * 0.9 + k / 7) % 1
                draw_heart(c, PH[0] + math.sin(k * 2.1) * 140, PH[1] - 150 - ph * 280, 1.5, (1 - ph) * a)
        if active(9):
            q = P(9, 0.0, 0.9)
            ang = math.pi * (1 - q)
            sx, sy = W / 2 + math.cos(ang) * 400, 560 - math.sin(ang) * 140
            col = tuple(lerp(YEL[i], (0.75, 0.78, 0.85)[i], q) for i in range(3))
            fa = a * (1 - (P(10, 0, 0.3) if active(10) else 0))
            c.set_source(rg(c, sx, sy, 5, 110, [(0, (*col, 0.5 * fa)), (1, (*col, 0))])); c.paint()
            c.new_path(); c.arc(sx, sy, 36, 0, 2 * math.pi); c.set_source_rgba(*col, fa); c.fill()
        if active(10):
            for k in range(3):
                draw_check(c, 330 + k * 210, FLOOR + 110, a, P(10, 0.35 + k * 0.17, 0.5 + k * 0.17))
    c.restore()

    # 画面に固定のもの（HUD・字幕）
    if not part2:
        alarm = active(3)
        hud(c, "MONKEY TRAP", t, P(0, 0, 0.3) * (1 - (P(5, 0.78, 1.0) if active(5) else 0)), alarm, 140 if alarm else 72)
    elif active(7) and not active(11):
        secs = 5 * 60 + (t - starts[7]) ** 2.3 * 160
        secs = 3 * 3600 + 27 * 60 if active(10) else min(secs, 3 * 3600 + 27 * 60)
        hh, mm = int(secs // 3600), int(secs % 3600 // 60)
        hud(c, f"SCREEN {hh}:{mm:02d}", t, 1.0, hh >= 1 and not active(10), 140 if hh >= 1 and not active(10) else 72)
    if active(11) and not active(14):
        k = 0 if not active(12) else (1 if not active(13) else 2)
        name = ["todo", "lock", "done"][k]
        q = back(P(11 + k, 0.0, 0.35))
        sc = 0.62 * (0.85 + 0.15 * min(1, q)) + 0.02 * ((t - starts[11 + k]) / 4)
        draw_shot_phone(c, name, W / 2, 900 + (1 - min(1, q)) * 120, sc, min(1, q), rot=(-0.04 if k % 2 else 0.04) * (1 - min(1, q)))
        font(c, 30, mono=True); lab = ["TODAY'S TODO", "SNS LOCKED", "UNLOCKED"][k]; e = c.text_extents(lab)
        c.move_to((W - e.x_advance) / 2, 380); c.set_source_rgba(*(RED if k == 1 else YEL), min(1, q)); c.show_text(lab)
    if active(14):
        q = back(P(14, 0.05, 0.45))
        draw_lock(c, W / 2, 860, 1.6 * max(0.01, q), min(1, q))
        font(c, 70); s = "Lock Do it"; e = c.text_extents(s)
        c.move_to((W - e.x_advance) / 2, 1120); c.set_source_rgba(1, 1, 1, min(1, q)); c.show_text(s)
        font(c, 38, bold=False); s = "やることが終わるまで、SNSにロック"; e = c.text_extents(s)
        c.move_to((W - e.x_advance) / 2, 1190); c.set_source_rgba(0.7, 0.7, 0.75, min(1, q)); c.show_text(s)
    for i, (s, hl) in enumerate(LINES):
        if starts[i] <= t < starts[i] + durs[i] + GAP:
            caption(c, s, hl, 1560, min(1, (t - starts[i]) / 0.15))
    # 周辺減光
    c.set_source(rg(c, W / 2, H / 2, 500, 1250, [(0, (0, 0, 0, 0)), (1, (0, 0, 0, 0.75))])); c.paint()


# ---------- 音 ----------
def sfx_thud(n):
    tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * (70 - 30 * tt) * tt) * np.exp(-tt * 9) + np.random.default_rng(1).normal(0, 0.3, n) * np.exp(-tt * 25)) * 0.9


def sfx_tick(n):
    tt = np.arange(n) / SR
    return np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 120) * 0.25


def sfx_pop(n, f=880):
    tt = np.arange(n) / SR
    return np.sin(2 * np.pi * f * tt * (1 + 0.5 * np.exp(-tt * 30))) * np.exp(-tt * 18) * 0.35


def sfx_whoosh(n):
    tt = np.arange(n) / SR
    noise = np.random.default_rng(2).normal(0, 1, n)
    env = np.sin(np.pi * np.clip(tt / (n / SR), 0, 1)) ** 2
    out = np.convolve(noise, np.ones(40) / 40, mode="same") * env
    return out * 0.5


def add(track, s, t):
    a = int(t * SR)
    e = min(len(track), a + len(s))
    if a < len(track):
        track[a:e] += s[: e - a]


def main(wav_dir, out):
    wavs, durs = [], []
    for i in range(1, len(LINES) + 1):
        w = wave.open(str(Path(wav_dir) / f"l{i:02d}.wav"))
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32767
        x = np.interp(np.arange(0, len(x), sr / SR), np.arange(len(x)), x)
        wavs.append(x); durs.append(len(x) / SR)
    starts, total = build_timeline(durs)
    n = int(total * SR); tt = np.arange(n) / SR
    pad = sum(np.sin(2 * np.pi * f * tt + k) * g for k, (f, g) in enumerate([(55, .5), (82.4, .3), (110, .2), (164.8, .08)]))
    pad *= 0.06 * (0.75 + 0.25 * np.sin(2 * np.pi * 0.08 * tt))
    pad *= np.minimum(1, np.minimum(tt / 1.5, (total - tt) / 1.5))
    track = pad
    for s, x in zip(starts, wavs):
        add(track, x * 0.95, s)
    add(track, sfx_whoosh(int(0.5 * SR)) * 0.5, starts[1] + 0.2)
    add(track, sfx_thud(int(0.6 * SR)), starts[5] + 0.35 * (durs[5] + GAP) - 0.05)
    add(track, sfx_whoosh(int(0.7 * SR)), starts[6] - 0.3)
    for k in range(18):
        add(track, sfx_tick(int(0.05 * SR)), starts[7] + k * 0.17)
    for k in range(3):
        add(track, sfx_pop(int(0.25 * SR), 700 + k * 180), starts[10] + (0.35 + k * 0.17 + 0.12) * (durs[10] + GAP))
    add(track, sfx_pop(int(0.4 * SR), 520), starts[14] + 0.2)
    for k in (11, 12, 13):
        add(track, sfx_whoosh(int(0.45 * SR)) * 0.6, starts[k])
    track = np.clip(track / np.abs(track).max() * 0.92, -1, 1)
    wavp = Path(out).with_suffix(".wav")
    with wave.open(str(wavp), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((track * 32767).astype(np.int16).tobytes())

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    grains = [np.random.default_rng(k).integers(-10, 11, (H, W, 1), dtype=np.int16) for k in range(6)]

    def render(tsec, k):
        frame(c, tsec, starts, durs, total); surf.flush()
        arr = np.ndarray((H, W, 4), np.uint8, surf.get_data()).astype(np.int16)
        arr[:, :, :3] += grains[k % 6]
        return np.clip(arr, 0, 255).astype(np.uint8)

    if "--frames" in sys.argv:
        from PIL import Image
        for k, ts in enumerate([starts[3] + 1.0, starts[8] + 1.5, starts[10] + 2.2, starts[12] + 1.5, starts[14] + 1.5]):
            arr = render(ts, k)
            Image.fromarray(arr[:, :, [2, 1, 0]]).save(f"/tmp/nv2_{k}.png")
        print("frames ok", total); return
    tmp = Path(out).with_suffix(".tmp.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(wavp), "-map", "0:v", "-map", "1:a",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "10M", "-bufsize", "20M", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    for k in range(int(total * FPS)):
        p.stdin.write(render(k / FPS, k).tobytes())
    p.stdin.close()
    if p.wait() == 0:
        tmp.rename(out); print(out, round(total, 1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
