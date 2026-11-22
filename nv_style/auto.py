"""Lock Do it 自動動画エンジン（NeuronVisuals風・部品セット式）

台本 JSON（videos/auto/<id>.json）から、日本語版・英語版の縦動画を作る。
  python3 nv_style/auto.py <台本.json> <ja|en> <wavフォルダ> <出力.mp4> [--frames]
音声は nv_style/voice.py で先に作る（l01.wav, l02.wav ...）。

台本の形:
{
  "id": "a001", "theme": "先延ばし", "ending": "A",
  "hud": {"ja": "PROCRASTINATION", "en": "PROCRASTINATION"},
  "lines": [
    {"scene": "clock", "args": {...},
     "ja": {"text": "字幕\\n2行目", "hl": "赤くする言葉", "say": "読み（なければtext）"},
     "en": {"text": "...", "hl": "..."}},
    ...
  ]
}
args の中で "items_en" のように _en を付けた項目は英語版だけで使う。
最後の4行（作った人・アプリ紹介・締め）は自動で足す。
使える scene: title person phone clock checklist stairs curve bars boulder chain
              book battery split door bulb target
"""
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import cairo
import numpy as np

W, H, FPS = 1080, 1920, 30
SR = 48000
LEAD, GAP = 0.25, 0.28
RED = (0.93, 0.30, 0.30)
YEL = (0.98, 0.80, 0.30)
BLUE = (0.42, 0.68, 1.0)
GRN = (0.45, 0.90, 0.60)
CX, CY = 540, 980
FLOOR = 1238
ROOT = Path(__file__).resolve().parent.parent

# ---------- 締めの4行 ----------
ENDING_JA = {
    "A": "毎日の行動が変わるアプリ",
    "B": "スマホが味方に変わるアプリ",
    "C": "やることが明確になるアプリ",
}
ENDING_EN = {
    "A": "Lock it till you do it.",
    "B": "Make your phone work for you.",
    "C": "Know exactly what to do today.",
}


def ending_lines(lang, variant):
    if lang == "ja":
        v = ENDING_JA.get(variant, ENDING_JA["A"])
        return [
            {"scene": "shot_todo", "text": "だから、スマホ依存の僕が、\nアプリを作った。", "hl": "スマホ依存の僕"},
            {"scene": "shot_lock", "text": "今日のToDoが全部終わるまで、\nSNSが開かない。", "hl": "SNSが開かない",
             "say": "今日のトゥドゥーが全部終わるまで、SNSが開かない。"},
            {"scene": "shot_done", "text": "終わったら、ロック解除。\n好きなだけ見ていい。", "hl": "ロック解除"},
            {"scene": "endcard", "text": f"{v}、\nLock Do it", "hl": v, "say": f"{v}、ロックドゥーイット。", "sub": v},
        ]
    v = ENDING_EN.get(variant, ENDING_EN["A"])
    return [
        {"scene": "shot_todo", "text": "So I, a phone addict,\nbuilt an app.", "hl": "a phone addict"},
        {"scene": "shot_lock", "text": "Social apps stay locked\nuntil today's to-dos are done.", "hl": "locked"},
        {"scene": "shot_done", "text": "Finish them, and it unlocks.\nScroll all you want.", "hl": "unlocks"},
        {"scene": "endcard", "text": f"Lock Do it.\n{v}", "hl": v, "say": f"Lock Do it. {v}", "sub": v},
    ]


def build_lines(script, lang):
    out = []
    for ln in script["lines"]:
        t = ln[lang]
        args = {k: v for k, v in ln.get("args", {}).items() if not k.endswith("_en")}
        if lang == "en":
            for k, v in ln.get("args", {}).items():
                if k.endswith("_en"):
                    args[k[:-3]] = v
        out.append({"scene": ln["scene"], "args": args, "text": t["text"], "hl": t.get("hl", ""),
                    "say": t.get("say", t["text"].replace("\n", ""))})
    for e in ending_lines(lang, script.get("ending", "A")):
        e.setdefault("say", e["text"].replace("\n", " " if lang == "en" else ""))
        e.setdefault("args", {})
        out.append(e)
    return out


# ---------- 小道具 ----------
def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def back(x):
    x = max(0.0, min(1.0, x))
    s = 1.70158
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def lerp(a, b, x):
    return a + (b - a) * x


def seg(p, a, b):
    return ease((p - a) / (b - a)) if b > a else float(p >= a)


def lg(x0, y0, x1, y1, stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for o, col in stops:
        g.add_color_stop_rgba(o, *col)
    return g


def rg(cx, cy, r0, r1, stops):
    g = cairo.RadialGradient(cx, cy, r0, cx, cy, r1)
    for o, col in stops:
        g.add_color_stop_rgba(o, *col)
    return g


def rr(c, x0, y0, w0, h0, r):
    r = min(r, w0 / 2, h0 / 2)
    c.new_path()
    c.arc(x0 + r, y0 + r, r, math.pi, 1.5 * math.pi)
    c.arc(x0 + w0 - r, y0 + r, r, 1.5 * math.pi, 2 * math.pi)
    c.arc(x0 + w0 - r, y0 + h0 - r, r, 0, 0.5 * math.pi)
    c.arc(x0 + r, y0 + h0 - r, r, 0.5 * math.pi, math.pi)
    c.close_path()


def glow(c, x, y, r, col, a):
    if a <= 0:
        return
    c.set_source(rg(x, y, 4, r, [(0, (*col, a)), (1, (*col, 0))]))
    c.paint()


def soft_shadow(c, x, y, rx, ry, a):
    for k in range(6):
        f = 1 + k * 0.22
        c.save(); c.translate(x, y); c.scale(rx * f, ry * f)
        c.new_path(); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
        c.set_source_rgba(0, 0, 0, 0.10 * a); c.fill()


def metal(x0, x1, a, dark=0.0):
    k = 1 - dark
    return lg(x0, 0, x1, 0, [(0, (0.22 * k, 0.23 * k, 0.26 * k, a)), (0.45, (0.62 * k, 0.64 * k, 0.68 * k, a)), (1, (0.18 * k, 0.19 * k, 0.22 * k, a))])


def font(c, size, bold=True, mono=False):
    fam = "Noto Sans Mono CJK JP" if mono else "Noto Sans CJK JP"
    c.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)


def text_c(c, s, x, y, size, col, a, bold=True, mono=False, shadow=True):
    font(c, size, bold, mono)
    e = c.text_extents(s)
    if e.x_advance > 980:
        font(c, size * 980 / e.x_advance, bold, mono); e = c.text_extents(s)
    xx = x - e.x_advance / 2
    if shadow:
        c.move_to(xx + 3, y + 4); c.set_source_rgba(0, 0, 0, 0.6 * a); c.show_text(s)
    c.move_to(xx, y); c.set_source_rgba(*col, a); c.show_text(s)


# ---------- 背景・HUD・字幕 ----------
_DUST = np.random.default_rng(3).uniform(0, 1, (28, 4))


def background(c, t):
    c.set_source_rgb(0.035, 0.035, 0.045); c.paint()
    c.set_source(rg(W / 2, 700, 50, 1150, [(0, (0.30, 0.30, 0.33, 0.55)), (1, (0, 0, 0, 0))])); c.paint()
    c.set_source(lg(0, 1240, 0, 1920, [(0, (0.10, 0.10, 0.12, 1)), (1, (0.02, 0.02, 0.03, 1))]))
    c.rectangle(0, 1240, W, 680); c.fill()
    c.set_source(lg(0, 1236, W, 1236, [(0, (1, 1, 1, 0)), (0.5, (1, 1, 1, 0.10)), (1, (1, 1, 1, 0))]))
    c.rectangle(0, 1236, W, 3); c.fill()
    for k, (u0, v0, s0, r0) in enumerate(_DUST):
        x = (u0 * W + math.sin(t * 0.3 + k) * 30) % W
        y = (v0 * 1100 - t * (8 + 17 * s0)) % 1100 + 250
        c.set_source_rgba(1, 1, 1, 0.10 + 0.08 * math.sin(t + k))
        c.new_path(); c.arc(x, y, 1.5 + 2 * r0, 0, 2 * math.pi); c.fill()


def hud(c, label, t, a, alarm=False, bpm=72):
    if a <= 0:
        return
    font(c, 30, mono=True)
    w = max(400, c.text_extents(label).x_advance + 40)
    x0, y0, h = (W - w) / 2, 250, 120
    c.new_path(); c.rectangle(x0, y0, w, h)
    c.set_source_rgba(0.06, 0.06, 0.08, 0.85 * a); c.fill_preserve()
    c.set_source_rgba(*(RED if alarm else (0.5, 0.5, 0.55)), 0.9 * a); c.set_line_width(3); c.stroke()
    c.save(); c.rectangle(x0 + 4, y0 + 4, w - 8, h - 8); c.clip()
    c.new_path()
    period = 60 / bpm * 160
    for k in range(0, int(w), 3):
        ph = ((k + t * 160) % period) / period
        v = -38 if 0.40 < ph < 0.44 else (28 if 0.44 < ph < 0.48 else (-8 if 0.36 < ph < 0.40 else 0))
        (c.line_to if k else c.move_to)(x0 + k, y0 + h * 0.62 + v)
    c.set_source_rgba(*(RED if alarm else (0.55, 1.0, 0.65)), a); c.set_line_width(4); c.stroke()
    c.restore()
    font(c, 30, mono=True)
    c.move_to(x0 + 14, y0 + 38); c.set_source_rgba(1, 1, 1, 0.85 * a); c.show_text(label)


def caption(c, s, hl, y, a):
    lines = s.split("\n")
    size = 56
    font(c, size)
    widest = max(c.text_extents(ln).x_advance for ln in lines)
    if widest > 960:
        size = size * 960 / widest
    for i, ln in enumerate(lines):
        font(c, size)
        parts = [(ln, (1, 1, 1))]
        if hl and hl in ln:
            p0, p1 = ln.split(hl, 1); parts = [(p0, (1, 1, 1)), (hl, RED), (p1, (1, 1, 1))]
        tw = sum(c.text_extents(p).x_advance for p, _ in parts)
        x = (W - tw) / 2; yy = y + i * size * 1.46
        for p, col in parts:
            c.move_to(x + 3, yy + 4); c.set_source_rgba(0, 0, 0, 0.7 * a); c.show_text(p)
            c.move_to(x, yy); c.set_source_rgba(*col, a); c.show_text(p)
            x += c.text_extents(p).x_advance


# ---------- 人（マネキン） ----------
POSES = {
    #        lean head  Lsh  Lel  Rsh  Rel  Lhip Lkn  Rhip Rkn
    "stand": (0, 0, -8, -4, 8, 4, -5, -3, 5, 3),
    "slump": (16, 28, 12, 22, 24, 34, -4, -4, 4, 4),
    "phone": (8, 30, 14, 140, 24, 150, -4, -3, 4, 3),
    "think": (2, 10, -8, -4, 26, 168, -5, -3, 5, 3),
    "cheer": (-3, -8, -150, -165, 150, 165, -12, -10, 12, 10),
    "walk": (6, 2, -8, -4, 8, 4, -5, -3, 5, 3),
    "sit": (6, 12, 18, 70, 26, 80, 80, 0, 85, 5),
}


def person(c, x, y, a, pose="stand", t=0.0, s=1.0, col=(0.62, 0.64, 0.70), glow_phone=False):
    """x, y = 腰の位置。pose は名前か数値タプル"""
    P = list(POSES[pose] if isinstance(pose, str) else pose)
    if pose == "walk":
        sw = math.sin(t * 6) * 24
        P[6], P[7], P[8], P[9] = -sw, -sw - 8, sw, sw - 8
        P[2], P[3], P[4], P[5] = sw * 0.8, sw * 0.8 + 10, -sw * 0.8, -sw * 0.8 + 10
    lean, head, lsh, lel, rsh, rel, lhp, lkn, rhp, rkn = [math.radians(v) for v in P]
    c.save(); c.translate(x, y); c.scale(s, s)
    soft_shadow(c, 0, FLOOR - y + 8 if s == 1 else 330, 120, 22, a)
    d = lambda ang: (math.sin(ang), math.cos(ang))
    neck = (220 * math.sin(lean), -220 * math.cos(lean))
    sh = (neck[0] - 18 * math.sin(lean), neck[1] + 18 * math.cos(lean))

    def limb(p0, a1, a2, l1, l2, w, shade):
        u = d(a1); p1 = (p0[0] + u[0] * l1, p0[1] + u[1] * l1)
        v = d(a2); p2 = (p1[0] + v[0] * l2, p1[1] + v[1] * l2)
        c.set_line_cap(cairo.LINE_CAP_ROUND); c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.set_line_width(w); c.set_source_rgba(*(k * shade for k in col), a)
        c.new_path(); c.move_to(*p0); c.line_to(*p1); c.line_to(*p2); c.stroke()
        return p2

    limb((-12, 0), lhp, lkn, 150, 150, 46, 0.55)
    limb((-6, -6) if False else sh, lsh, lel, 118, 110, 34, 0.55)
    # 胴
    c.save(); c.rotate(lean)
    rr(c, -52, -232, 104, 250, 46)
    c.set_source(lg(-52, 0, 52, 0, [(0, (*(k * 0.45 for k in col), a)), (0.45, (*col, a)), (1, (*(k * 0.35 for k in col), a))]))
    c.fill(); c.restore()
    limb((12, 0), rhp, rkn, 150, 150, 46, 0.9)
    hand = limb(sh, rsh, rel, 118, 110, 34, 0.95)
    # 頭
    hx = neck[0] + 62 * math.sin(lean + head * 0.6)
    hy = neck[1] - 62 * math.cos(lean + head * 0.6)
    c.new_path(); c.arc(hx, hy, 56, 0, 2 * math.pi)
    c.set_source(rg(hx - 18, hy - 20, 4, 70, [(0, (*(min(1, k * 1.35) for k in col), a)), (1, (*(k * 0.4 for k in col), a))]))
    c.fill()
    if pose == "phone" or glow_phone:
        px, py = hand[0] + 10, hand[1] - 20
        glow(c, px, py, 220, BLUE, 0.45 * a)
        rr(c, px - 24, py - 40, 48, 80, 10); c.set_source_rgba(0.15, 0.25, 0.45, a); c.fill()
        rr(c, px - 18, py - 33, 36, 66, 6); c.set_source_rgba(0.55, 0.75, 1.0, 0.9 * a); c.fill()
    c.restore()


# ---------- 部品 ----------
def draw_phone(c, x, y, a, glowv=0.0, scroll=0.0, s=1.0):
    c.save(); c.translate(x, y); c.scale(s, s)
    w, h = 126, 230
    glow(c, 0, 0, 340, BLUE, 0.45 * glowv * a)
    rr(c, -w / 2, -h / 2, w, h, 24); c.set_source(metal(-w / 2, w / 2, a)); c.fill()
    rr(c, -w / 2 + 9, -h / 2 + 12, w - 18, h - 24, 16)
    c.set_source(lg(0, -h / 2, 0, h / 2, [(0, (0.10, 0.18, 0.32, a)), (1, (0.05, 0.08, 0.16, a))])); c.fill_preserve()
    c.save(); c.clip()
    for i in range(-2, 10):
        yy = -h / 2 + 30 + ((i * 38 - scroll) % 340) - 50
        c.set_source_rgba(0.85, 0.90, 1.0, 0.55 * a); c.rectangle(-w / 2 + 22, yy, 26, 26); c.fill()
        c.set_source_rgba(*BLUE, 0.6 * a); c.rectangle(-w / 2 + 54, yy + 3, w - 80, 8); c.fill()
        c.set_source_rgba(*BLUE, 0.35 * a); c.rectangle(-w / 2 + 54, yy + 15, w - 100, 7); c.fill()
    c.restore(); c.restore()


def draw_check(c, x, y, a, p, s=1.0):
    c.save(); c.translate(x, y); c.scale(s, s)
    c.new_path(); c.rectangle(-36, -36, 72, 72)
    c.set_source(lg(0, -36, 0, 36, [(0, (0.22, 0.22, 0.26, a)), (1, (0.12, 0.12, 0.15, a))]))
    c.fill_preserve(); c.set_source_rgba(0.6, 0.6, 0.65, a); c.set_line_width(3); c.stroke()
    if p > 0:
        c.set_line_width(11); c.set_line_cap(cairo.LINE_CAP_ROUND)
        pts = [(-20, 0), (-4, 18), (26, -22)]
        c.new_path(); c.move_to(*pts[0])
        if p < 0.5:
            q = p / 0.5; c.line_to(lerp(pts[0][0], pts[1][0], q), lerp(pts[0][1], pts[1][1], q))
        else:
            q = (p - 0.5) / 0.5; c.line_to(*pts[1]); c.line_to(lerp(pts[1][0], pts[2][0], q), lerp(pts[1][1], pts[2][1], q))
        c.set_source_rgba(*YEL, a); c.stroke()
    c.restore()


def draw_lock(c, x, y, s, a, open_=0.0):
    c.save(); c.translate(x, y); c.scale(s, s)
    glow(c, 0, 20, 200, YEL, 0.35 * a)
    c.set_line_width(16); c.set_source_rgba(0.75, 0.75, 0.80, a)
    c.save(); c.translate(38, -30); c.rotate(-0.9 * open_); c.translate(-38, 30 - 30 * open_)
    c.new_path(); c.arc(0, -30, 38, math.pi, 2 * math.pi); c.stroke()
    c.move_to(-38, -30); c.line_to(-38, -6); c.stroke(); c.move_to(38, -30); c.line_to(38, -6); c.stroke()
    c.restore()
    c.new_path(); c.rectangle(-62, -8, 124, 92)
    c.set_source(lg(0, -8, 0, 84, [(0, (1.0, 0.86, 0.40, a)), (1, (0.85, 0.58, 0.12, a))])); c.fill()
    c.new_path(); c.arc(0, 30, 10, 0, 2 * math.pi); c.set_source_rgba(0.3, 0.2, 0.05, a); c.fill()
    c.restore()


_SHOTS = {}


def shot(name):
    if name not in _SHOTS:
        from PIL import Image
        im = Image.open(ROOT / "assets" / "app_screens" / f"{name}.png").convert("RGBA").resize((603, 1311))
        arr = np.array(im)[:, :, [2, 1, 0, 3]].copy()
        surf = cairo.ImageSurface.create_for_data(memoryview(arr), cairo.FORMAT_ARGB32, im.width, im.height, im.width * 4)
        _SHOTS[name] = (surf, arr)
    return _SHOTS[name][0]


def draw_shot_phone(c, name, x, y, s, a, rot=0.0):
    sw, sh = 603, 1311
    c.save(); c.translate(x, y); c.rotate(rot); c.scale(s, s)
    c.set_source(rg(0, 0, 50, 900, [(0, (*YEL, 0.18 * a)), (1, (*YEL, 0))])); c.paint()
    for k in range(6):
        c.new_path(); c.rectangle(-sw / 2 - 20 - k * 6 + 30, -sh / 2 - 20 - k * 6 + 40, sw + 40 + k * 12, sh + 40 + k * 12)
        c.set_source_rgba(0, 0, 0, 0.08 * a); c.fill()
    bw = 22
    rr(c, -sw / 2 - bw, -sh / 2 - bw, sw + 2 * bw, sh + 2 * bw, 90)
    c.set_source(lg(-sw / 2, 0, sw / 2, 0, [(0, (0.22, 0.23, 0.26, a)), (0.5, (0.50, 0.52, 0.56, a)), (1, (0.18, 0.19, 0.22, a))])); c.fill()
    rr(c, -sw / 2, -sh / 2, sw, sh, 70); c.clip()
    c.set_source_surface(shot(name), -sw / 2, -sh / 2); c.paint_with_alpha(a)
    c.restore()


def rock_path(c, x, y, r, seed):
    rng = np.random.default_rng(seed)
    n = 11
    c.new_path()
    for k in range(n):
        ang = 2 * math.pi * k / n
        rr_ = r * rng.uniform(0.82, 1.08)
        px, py = x + math.cos(ang) * rr_, y + math.sin(ang) * rr_ * 0.82
        (c.line_to if k else c.move_to)(px, py)
    c.close_path()


def fill_rock(c, x, y, r, a, seed=1):
    rock_path(c, x, y, r, seed)
    c.set_source(rg(x - r * 0.35, y - r * 0.4, 4, r * 1.3, [(0, (0.58, 0.57, 0.55, a)), (1, (0.16, 0.16, 0.17, a))]))
    c.fill()


# ---------- シーン ----------
# 各シーン: fn(c, t, p, a, args, info) 。p=その行の進み(0-1)、info={"dur":秒}
def sc_title(c, t, p, a, A, info):
    q = back(seg(p, 0.0, 0.35))
    big = str(A.get("big", ""))
    glow(c, W / 2, 860, 520, YEL, 0.22 * a * min(1, q))
    c.save(); c.translate(W / 2, 900); s = 0.6 + 0.4 * min(1.2, q) + 0.03 * p; c.scale(s, s)
    font(c, int(A.get("size", 230)))
    e = c.text_extents(big)
    if e.x_advance > 900:
        font(c, int(A.get("size", 230)) * 900 / e.x_advance); e = c.text_extents(big)
    c.move_to(-e.x_advance / 2 + 6, 8); c.set_source_rgba(0, 0, 0, 0.6 * a); c.show_text(big)
    c.move_to(-e.x_advance / 2, 0)
    c.set_source(lg(0, -e.height, 0, 0, [(0, (1.0, 0.92, 0.6, a)), (1, (*YEL, a))])); c.show_text(big)
    c.restore()
    if A.get("sub"):
        text_c(c, A["sub"], W / 2, 1080, 40, (0.75, 0.75, 0.80), a * seg(p, 0.25, 0.5), mono=True)


def sc_person(c, t, p, a, A, info):
    p0, p1 = A.get("pose", "stand"), A.get("to")
    if p1 and p1 in POSES and p0 in POSES and p0 != "walk" and p1 != "walk":
        q = seg(p, 0.25, 0.7)
        pose = tuple(lerp(u, v, q) for u, v in zip(POSES[p0], POSES[p1]))
        label = p1 if q > 0.5 else p0
    else:
        pose, label = p0, p0
    x = CX + (math.sin(t * 0.8) * 6) + (lerp(-160, 160, p) if p0 == "walk" else 0)
    col = YEL if A.get("hero") else (0.62, 0.64, 0.70)
    if A.get("hero"):
        glow(c, x, 820, 420, YEL, 0.15 * a)
    person(c, x, 935, a, pose, t, col=col if not A.get("hero") else (0.78, 0.72, 0.55), glow_phone=(label == "phone"))
    if A.get("cloud"):  # 頭の上の言葉
        q = back(seg(p, 0.1, 0.4))
        c.save(); c.translate(x + 150, 470); c.scale(max(0.01, q), max(0.01, q))
        for dx, dy, r in ((-90, 10, 70), (0, -20, 90), (95, 12, 72), (0, 40, 80)):
            c.new_path(); c.arc(dx, dy, r, 0, 2 * math.pi); c.set_source_rgba(0.9, 0.9, 0.95, 0.92 * a); c.fill()
        c.restore()
        if q > 0.6:
            font(c, 40); s = A["cloud"]; e = c.text_extents(s)
            if e.x_advance > 300:
                font(c, 40 * 300 / e.x_advance); e = c.text_extents(s)
            c.move_to(x + 150 - e.x_advance / 2, 500); c.set_source_rgba(0.1, 0.1, 0.12, a); c.show_text(s)


def sc_phone(c, t, p, a, A, info):
    draw_phone(c, CX, CY - 40, a, glowv=0.6 + 0.4 * math.sin(t * 5), scroll=t * 260, s=1.5)
    for k in range(6):
        ph = (t * 0.9 + k / 6) % 1
        c.set_source_rgba(*RED, (1 - ph) * a * 0.8)
        font(c, 44); c.move_to(CX + math.sin(k * 2.1) * 220 - 20, CY - 260 - ph * 300); c.show_text("♥")


def sc_clock(c, t, p, a, A, info):
    r = 250
    x, y = CX, CY - 40
    glow(c, x, y, 450, RED if A.get("red") else YEL, 0.14 * a)
    c.new_path(); c.arc(x, y, r + 22, 0, 2 * math.pi); c.set_source(metal(x - r, x + r, a)); c.fill()
    c.new_path(); c.arc(x, y, r, 0, 2 * math.pi)
    c.set_source(rg(x - 60, y - 80, 10, r * 1.2, [(0, (0.20, 0.20, 0.24, a)), (1, (0.07, 0.07, 0.09, a))])); c.fill()
    for k in range(60):
        ang = k / 60 * 2 * math.pi
        l = 34 if k % 5 == 0 else 12
        c.set_line_width(7 if k % 5 == 0 else 3); c.set_source_rgba(0.85, 0.85, 0.9, a * (1 if k % 5 == 0 else 0.5))
        c.new_path(); c.move_to(x + math.sin(ang) * (r - 14), y - math.cos(ang) * (r - 14))
        c.line_to(x + math.sin(ang) * (r - 14 - l), y - math.cos(ang) * (r - 14 - l)); c.stroke()
    spin = float(A.get("spin", 3))
    hrs = 10 + spin * ease(p)
    for ang, l, w, col in ((hrs / 12 * 2 * math.pi, r * 0.5, 16, (0.95, 0.95, 1)), (hrs * 2 * math.pi, r * 0.78, 9, RED)):
        c.set_line_cap(cairo.LINE_CAP_ROUND); c.set_line_width(w); c.set_source_rgba(*col, a)
        c.new_path(); c.move_to(x, y); c.line_to(x + math.sin(ang) * l, y - math.cos(ang) * l); c.stroke()
    c.new_path(); c.arc(x, y, 18, 0, 2 * math.pi); c.set_source_rgba(*YEL, a); c.fill()
    if A.get("label"):
        text_c(c, A["label"], x, y + r + 110, 46, (0.85, 0.85, 0.9), a * seg(p, 0.2, 0.4), mono=True)


def sc_checklist(c, t, p, a, A, info):
    items = A.get("items", ["", "", ""])[:5]
    n = len(items)
    y0 = CY - 40 - (n - 1) * 70
    rr(c, 170, y0 - 110, 740, n * 140 + 80, 30)
    c.set_source(lg(0, y0 - 110, 0, y0 + n * 140, [(0, (0.16, 0.16, 0.19, 0.95 * a)), (1, (0.09, 0.09, 0.11, 0.95 * a))])); c.fill()
    for i, s in enumerate(items):
        y = y0 + i * 140
        q = seg(p, 0.15 + i * 0.6 / n, 0.15 + (i + 1) * 0.6 / n) if A.get("tick", True) else 0
        draw_check(c, 270, y, a, q)
        font(c, 46); e = c.text_extents(s)
        if e.x_advance > 540:
            font(c, 46 * 540 / e.x_advance)
        c.move_to(340, y + 16); c.set_source_rgba(*(YEL if q >= 1 else (0.9, 0.9, 0.95)), a); c.show_text(s)
        if q >= 1:
            c.set_source_rgba(1, 1, 1, 0.35 * a); c.set_line_width(4)
            c.new_path(); c.move_to(340, y + 2); c.line_to(340 + min(540, c.text_extents(s).x_advance), y + 2); c.stroke()


def sc_stairs(c, t, p, a, A, info):
    n = int(A.get("steps", 6))
    sw, shh = 130, 85
    x0 = CX - n * sw / 2
    for i in range(n):
        x, y = x0 + i * sw, FLOOR - (i + 1) * shh
        c.new_path(); c.rectangle(x, y, sw, (i + 1) * shh)
        c.set_source(lg(x, y, x, FLOOR, [(0, (0.42, 0.42, 0.46, a)), (1, (0.12, 0.12, 0.14, a))])); c.fill()
        c.new_path(); c.rectangle(x, y, sw, 6); c.set_source_rgba(1, 1, 1, 0.25 * a); c.fill()
    pos = ease(p) * (n - 1) * 1.0
    k = int(pos); f = pos - k
    bx = x0 + (k + f) * sw + sw / 2
    by = FLOOR - (k + 1) * shh - 50 - math.sin(f * math.pi) * 110 - f * shh * (1 if k < n - 1 else 0)
    if A.get("figure", True):
        person(c, bx, by - 300 * 0.45 + 30, a, "walk" if p < 0.97 else "cheer", t, s=0.45, col=(0.78, 0.72, 0.55))
    else:
        glow(c, bx, by, 120, YEL, 0.5 * a)
        c.new_path(); c.arc(bx, by, 30, 0, 2 * math.pi); c.set_source_rgba(*YEL, a); c.fill()
    if p > 0.9:
        glow(c, x0 + (n - 0.5) * sw, FLOOR - n * shh - 200, 260, YEL, 0.4 * a * seg(p, 0.9, 1))
    if A.get("label"):
        text_c(c, A["label"], CX, 500, 44, (0.85, 0.85, 0.9), a * seg(p, 0.1, 0.3), mono=True)


def sc_curve(c, t, p, a, A, info):
    x0, y0, x1, y1 = 170, 1180, 920, 460
    c.set_source_rgba(0.6, 0.6, 0.65, a); c.set_line_width(4)
    c.new_path(); c.move_to(x0, y1 - 40); c.line_to(x0, y0); c.line_to(x1 + 30, y0); c.stroke()
    q = ease(p * 1.15)
    for f, col, lab in ((lambda u: 1.01 ** (u * 365) / 37.8, YEL, A.get("up", "37.8")),
                         (lambda u: 0.99 ** (u * 365) * 0.25, RED, A.get("down", "0.03"))):
        c.set_line_width(9); c.set_line_cap(cairo.LINE_CAP_ROUND); c.set_source_rgba(*col, a)
        c.new_path()
        N = 80
        for k in range(int(N * q) + 1):
            u = k / N
            xx, yy = lerp(x0, x1, u), lerp(y0, y1, f(u))
            (c.line_to if k else c.move_to)(xx, yy)
        c.stroke()
        if q >= 0.99 and lab:
            text_c(c, str(lab), x1 - 20, lerp(y0, y1, f(1)) - 30, 54, col, a)
    if A.get("label"):
        text_c(c, A["label"], CX, 400, 42, (0.85, 0.85, 0.9), a, mono=True)


def sc_bars(c, t, p, a, A, info):
    vals = A.get("values", [3, 5, 8, 13]); labs = A.get("labels", [""] * len(vals)); hl = A.get("hl", len(vals) - 1)
    n = len(vals); mx = max(vals) or 1
    bw = min(150, 700 / n)
    for i, v in enumerate(vals):
        q = back(seg(p, 0.1 + i * 0.12, 0.45 + i * 0.12))
        x = CX - (n * bw * 1.5) / 2 + i * bw * 1.5 + bw * 0.25
        h = 620 * v / mx * q
        col = YEL if i == hl else (0.55, 0.56, 0.62)
        c.new_path(); c.rectangle(x, FLOOR - 40 - h, bw, h)
        c.set_source(lg(x, 0, x + bw, 0, [(0, (*(k * 0.5 for k in col), a)), (0.45, (*col, a)), (1, (*(k * 0.4 for k in col), a))])); c.fill()
        if labs[i]:
            text_c(c, str(labs[i]), x + bw / 2, FLOOR + 30, 34, (0.8, 0.8, 0.85), a, mono=True)
    if A.get("label"):
        text_c(c, A["label"], CX, 440, 42, (0.85, 0.85, 0.9), a, mono=True)


def sc_boulder(c, t, p, a, A, info):
    split = seg(p, 0.45, 0.7) if A.get("split", True) else 0.0
    n = int(A.get("pieces", 5))
    if split < 1:
        shake = math.sin(t * 60) * 8 * (seg(p, 0.3, 0.45) if A.get("split", True) else 0.6) * (1 - split)
        soft_shadow(c, CX, FLOOR + 10, 280, 40, a * (1 - split))
        fill_rock(c, CX + shake, CY - 20, 300, a * (1 - split), seed=4)
        if p > 0.3 and A.get("split", True):
            c.set_source_rgba(0, 0, 0, 0.8 * a * (1 - split)); c.set_line_width(6)
            c.new_path(); c.move_to(CX - 20, CY - 290); c.line_to(CX + 30, CY - 120); c.line_to(CX - 40, CY + 40); c.line_to(CX + 20, CY + 210); c.stroke()
    if split > 0:
        for i in range(n):
            tx = CX - (n - 1) * 95 + i * 190
            x = lerp(CX, tx, split); y = lerp(CY, FLOOR - 70, split)
            fill_rock(c, x, y, 70, a * split, seed=10 + i)
            if A.get("tick", True):
                q = seg(p, 0.72 + i * 0.05, 0.8 + i * 0.05)
                if q > 0:
                    draw_check(c, x, y - 150, a * q, q, 0.8)
    if A.get("label"):
        text_c(c, A["label"], CX, 470, 46, (0.85, 0.85, 0.9), a, mono=True)


def sc_chain(c, t, p, a, A, info):
    cols, rows = 7, 4
    n = int(A.get("n", 21)); miss = A.get("miss")
    cw = 118; x0 = CX - cols * cw / 2; y0 = CY - 300
    rr(c, x0 - 30, y0 - 130, cols * cw + 60, rows * cw + 170, 26)
    c.set_source_rgba(0.14, 0.14, 0.17, 0.95 * a); c.fill()
    c.new_path(); c.rectangle(x0 - 30, y0 - 130, cols * cw + 60, 70); c.set_source_rgba(*RED, 0.85 * a); c.fill()
    for k in range(cols * rows):
        i, j = k % cols, k // cols
        x, y = x0 + i * cw, y0 + j * cw
        c.new_path(); c.rectangle(x + 6, y + 6, cw - 12, cw - 12); c.set_source_rgba(0.9, 0.9, 0.93, 0.12 * a); c.fill()
        q = seg(p, 0.1 + 0.7 * k / max(1, n), 0.1 + 0.7 * (k + 1) / max(1, n)) if k < n else 0
        if q > 0:
            c.set_line_cap(cairo.LINE_CAP_ROUND); c.set_line_width(10)
            if miss is not None and k == miss:
                c.set_source_rgba(0.4, 0.4, 0.45, a); c.new_path(); c.arc(x + cw / 2, y + cw / 2, 30 * q, 0, 2 * math.pi); c.stroke()
            else:
                c.set_source_rgba(*YEL, a)
                c.new_path(); c.move_to(x + 30, y + 30); c.line_to(lerp(x + 30, x + cw - 30, q), lerp(y + 30, y + cw - 30, q)); c.stroke()
                if q > 0.5:
                    q2 = (q - 0.5) * 2
                    c.new_path(); c.move_to(x + cw - 30, y + 30); c.line_to(lerp(x + cw - 30, x + 30, q2), lerp(y + 30, y + cw - 30, q2)); c.stroke()
    if A.get("label"):
        text_c(c, A["label"], CX, y0 + rows * cw + 130, 44, (0.85, 0.85, 0.9), a, mono=True)


def sc_book(c, t, p, a, A, info):
    op = back(seg(p, 0.1, 0.45))
    x, y = CX, CY + 20
    glow(c, x, y - 120, 520, YEL, 0.25 * a * min(1, op))
    soft_shadow(c, x, FLOOR + 10, 360, 40, a)
    bw, bh = 330, 440
    for side in (-1, 1):
        w = bw * (0.15 + 0.85 * min(1, op)) if side == -1 else bw
        c.save(); c.translate(x, y)
        c.new_path(); c.move_to(0, -bh / 2); c.curve_to(side * w * 0.5, -bh / 2 - 30, side * w * 0.8, -bh / 2 - 10, side * w, -bh / 2 + 10)
        c.line_to(side * w, bh / 2 + 10); c.curve_to(side * w * 0.8, bh / 2 - 10, side * w * 0.5, bh / 2 - 30, 0, bh / 2); c.close_path()
        c.set_source(lg(0, 0, side * w, 0, [(0, (0.70, 0.68, 0.62, a)), (1, (0.93, 0.91, 0.85, a))])); c.fill()
        for k in range(7):
            yy = -bh / 2 + 70 + k * 50
            c.set_source_rgba(0.35, 0.34, 0.32, 0.5 * a * min(1, op)); c.set_line_width(5)
            c.new_path(); c.move_to(side * 40, yy); c.line_to(side * (w - 40) * (0.6 + 0.4 * ((k * 37) % 5) / 5), yy); c.stroke()
        c.restore()
    # 舞う光
    for k in range(10):
        ph = (t * 0.5 + k / 10) % 1
        c.set_source_rgba(*YEL, (1 - ph) * a * 0.8 * min(1, op))
        c.new_path(); c.arc(x + math.sin(k * 2.3) * 260 * ph, y - 240 - ph * 380, 6, 0, 2 * math.pi); c.fill()
    if A.get("title"):
        text_c(c, A["title"], x, 470, 52, (1, 1, 1), a * seg(p, 0.2, 0.4))
    if A.get("author"):
        text_c(c, A["author"], x, 540, 34, (0.7, 0.7, 0.75), a * seg(p, 0.3, 0.5), bold=False, mono=True)


def sc_battery(c, t, p, a, A, info):
    v = lerp(float(A.get("from", 0.9)), float(A.get("to", 0.1)), ease(p))
    x, y, w, h = CX - 300, CY - 170, 560, 280
    rr(c, x, y, w, h, 40); c.set_source(metal(x, x + w, a)); c.fill()
    rr(c, x + w, y + h / 2 - 45, 40, 90, 14); c.set_source(metal(x + w, x + w + 40, a)); c.fill()
    rr(c, x + 24, y + 24, w - 48, h - 48, 22); c.set_source_rgba(0.05, 0.05, 0.06, a); c.fill()
    col = RED if v < 0.25 else (YEL if v < 0.6 else GRN)
    glow(c, x + 24 + (w - 48) * v / 2, y + h / 2, 400, col, 0.18 * a)
    rr(c, x + 36, y + 36, max(8, (w - 72) * v), h - 72, 14)
    c.set_source(lg(0, y, 0, y + h, [(0, (*(min(1, k * 1.2) for k in col), a)), (1, (*(k * 0.6 for k in col), a))])); c.fill()
    text_c(c, f"{int(round(v * 100))}%", CX, y + h + 120, 70, col, a, mono=True)
    if A.get("label"):
        text_c(c, A["label"], CX, 460, 44, (0.85, 0.85, 0.9), a, mono=True)


def sc_split(c, t, p, a, A, info):
    for side, key, col in ((-1, "left", RED), (1, "right", YEL)):
        q = back(seg(p, 0.05 if side < 0 else 0.3, 0.35 if side < 0 else 0.6))
        x = CX + side * 245
        c.save(); c.translate(x, CY - 20); s = max(0.01, q); c.scale(s, s)
        rr(c, -215, -360, 430, 720, 34)
        c.set_source(lg(0, -360, 0, 360, [(0, (*(k * 0.35 for k in col), 0.9 * a)), (1, (0.06, 0.06, 0.08, 0.9 * a))])); c.fill()
        rr(c, -215, -360, 430, 720, 34); c.set_source_rgba(*col, 0.8 * a); c.set_line_width(4); c.stroke()
        c.restore()
        if q > 0.5:
            pose = A.get(key + "_pose", "slump" if side < 0 else "cheer")
            person(c, x, CY + 80, a * min(1, q), pose, t, s=0.62, col=(0.6, 0.6, 0.65) if side < 0 else (0.85, 0.78, 0.55))
            text_c(c, A.get(key, ""), x, CY - 250, 44, col, a * min(1, q))
    text_c(c, "VS", CX, CY + 380, 40, (0.8, 0.8, 0.85), a * seg(p, 0.5, 0.7), mono=True)


def sc_door(c, t, p, a, A, info):
    op = seg(p, 0.3, 0.8)
    x, y, w, h = CX - 170, CY - 420, 340, 650
    c.new_path(); c.rectangle(x - 26, y - 26, w + 52, h + 26); c.set_source(metal(x - 26, x + w + 26, a, 0.3)); c.fill()
    c.new_path(); c.rectangle(x, y, w, h); c.set_source_rgba(1.0, 0.92, 0.65, a * (0.15 + 0.85 * op)); c.fill()
    glow(c, CX, y + h / 2, 650, YEL, 0.45 * a * op)
    # 光の床
    c.new_path(); c.move_to(x, y + h); c.line_to(x + w, y + h); c.line_to(x + w + 260 * op, FLOOR + 400); c.line_to(x - 260 * op, FLOOR + 400); c.close_path()
    c.set_source(lg(0, y + h, 0, FLOOR + 400, [(0, (*YEL, 0.35 * a * op)), (1, (*YEL, 0))])); c.fill()
    dw = w * (1 - 0.82 * op)
    c.new_path(); c.move_to(x, y); c.line_to(x + dw, y + 30 * op); c.line_to(x + dw, y + h - 30 * op); c.line_to(x, y + h); c.close_path()
    c.set_source(lg(x, 0, x + dw, 0, [(0, (0.30, 0.22, 0.16, a)), (1, (0.18, 0.13, 0.10, a))])); c.fill()
    c.new_path(); c.arc(x + dw - 35, y + h / 2, 12, 0, 2 * math.pi); c.set_source_rgba(*YEL, a); c.fill()
    if A.get("figure", True):
        person(c, lerp(CX - 360, CX - 80, seg(p, 0.5, 1)), FLOOR - 300 * 0.55, a, "walk", t, s=0.55)
    if A.get("label"):
        text_c(c, A["label"], CX, 420, 44, (0.85, 0.85, 0.9), a, mono=True)


def sc_bulb(c, t, p, a, A, info):
    on = seg(p, 0.35, 0.5)
    x, y = CX, CY - 120
    glow(c, x, y, 600, YEL, 0.5 * a * on)
    for k in range(12):
        ang = k / 12 * 2 * math.pi
        l0, l1 = 260, 260 + 90 * on * (0.8 + 0.2 * math.sin(t * 6 + k))
        c.set_line_cap(cairo.LINE_CAP_ROUND); c.set_line_width(10); c.set_source_rgba(*YEL, a * on)
        c.new_path(); c.move_to(x + math.cos(ang) * l0, y + math.sin(ang) * l0); c.line_to(x + math.cos(ang) * l1, y + math.sin(ang) * l1); c.stroke()
    c.new_path(); c.arc(x, y, 190, math.radians(140), math.radians(40))
    c.line_to(x + 80, y + 260); c.line_to(x - 80, y + 260); c.close_path()
    c.set_source(rg(x - 50, y - 60, 10, 260, [(0, (*lerp3((0.5, 0.5, 0.55), (1, 0.97, 0.8), on), 0.95 * a)), (1, (*lerp3((0.2, 0.2, 0.24), YEL, on), 0.95 * a))])); c.fill()
    for k in range(3):
        c.new_path(); c.rectangle(x - 85, y + 270 + k * 34, 170, 24); c.set_source(metal(x - 85, x + 85, a)); c.fill()
    if A.get("label"):
        text_c(c, A["label"], CX, CY + 420, 44, (0.85, 0.85, 0.9), a * seg(p, 0.4, 0.6), mono=True)


def lerp3(u, v, q):
    return tuple(lerp(u[i], v[i], q) for i in range(3))


def sc_target(c, t, p, a, A, info):
    x, y = CX, CY - 60
    for k, r in enumerate((300, 230, 160, 90)):
        c.new_path(); c.arc(x, y, r, 0, 2 * math.pi)
        c.set_source_rgba(*((RED if k % 2 == 0 else (0.92, 0.92, 0.95))), a); c.fill()
    c.new_path(); c.arc(x, y, 300, 0, 2 * math.pi)
    c.set_source(rg(x - 100, y - 120, 10, 420, [(0, (1, 1, 1, 0.18 * a)), (1, (0, 0, 0, 0.45 * a))])); c.fill()
    q = seg(p, 0.2, 0.5)
    ax = lerp(W + 300, x, q); ay = lerp(y - 380, y, q)
    if q >= 1:
        glow(c, x, y, 200, YEL, 0.5 * a * (1 - seg(p, 0.5, 1)))
    c.set_line_cap(cairo.LINE_CAP_ROUND); c.set_line_width(14); c.set_source_rgba(0.9, 0.85, 0.7, a)
    c.new_path(); c.move_to(ax, ay); c.line_to(ax + 300, ay - 300); c.stroke()
    c.set_source_rgba(*YEL, a); c.new_path(); c.move_to(ax + 300, ay - 300); c.line_to(ax + 250, ay - 330); c.line_to(ax + 330, ay - 250); c.close_path(); c.fill()
    if A.get("label"):
        text_c(c, A["label"], CX, CY + 400, 44, (0.85, 0.85, 0.9), a, mono=True)


def sc_shot(name, lab, col):
    def fn(c, t, p, a, A, info):
        q = back(seg(p, 0.0, 0.35))
        sc = 0.62 * (0.85 + 0.15 * min(1, q)) + 0.02 * p
        draw_shot_phone(c, name, W / 2, 900 + (1 - min(1, q)) * 120, sc, a * min(1, q), rot=0.04 * (1 - min(1, q)))
        font(c, 30, mono=True); e = c.text_extents(lab)
        c.move_to((W - e.x_advance) / 2, 380); c.set_source_rgba(*col, a * min(1, q)); c.show_text(lab)
    return fn


def sc_endcard(c, t, p, a, A, info):
    q = back(seg(p, 0.05, 0.45))
    draw_lock(c, W / 2, 860, 1.6 * max(0.01, q), a * min(1, q))
    text_c(c, "Lock Do it", W / 2, 1120, 70, (1, 1, 1), a * min(1, q), shadow=False)
    text_c(c, A.get("sub", ""), W / 2, 1190, 38, (0.7, 0.7, 0.75), a * min(1, q), bold=False, shadow=False)


SCENES = {
    "title": sc_title, "person": sc_person, "phone": sc_phone, "clock": sc_clock, "checklist": sc_checklist,
    "stairs": sc_stairs, "curve": sc_curve, "bars": sc_bars, "boulder": sc_boulder, "chain": sc_chain,
    "book": sc_book, "battery": sc_battery, "split": sc_split, "door": sc_door, "bulb": sc_bulb, "target": sc_target,
    "shot_todo": sc_shot("todo", "TODAY'S TODO", YEL), "shot_lock": sc_shot("lock", "SNS LOCKED", RED),
    "shot_done": sc_shot("done", "UNLOCKED", YEL), "endcard": sc_endcard,
}
ENDING_SCENES = {"shot_todo", "shot_lock", "shot_done", "endcard"}

# シーンごとの効果音: (行の中の割合, 種類)
SFX = {
    "title": [(0.02, "whoosh"), (0.12, "pop_low")], "clock": [("ticks", 0)], "checklist": [("ticks_check", 0)],
    "stairs": [("steps", 0)], "boulder": [(0.45, "thud")], "chain": [("chain", 0)], "book": [(0.12, "whoosh")],
    "battery": [], "split": [(0.05, "pop_low"), (0.3, "pop")], "door": [(0.3, "whoosh")], "bulb": [(0.36, "pop_hi")],
    "target": [(0.42, "thud")], "endcard": [(0.08, "pop_low")], "curve": [(0.05, "whoosh")],
    "bars": [("bars", 0)], "phone": [("phone", 0)],
}


# ---------- タイムライン・1コマ ----------
def same_scene(a, b):
    return a["scene"] == b["scene"] and a.get("args", {}) == b.get("args", {})


def groups(lines):
    """続けて同じシーン＆同じ設定の行はつなげて1つのシーンにする"""
    gid, out = -1, []
    for i, ln in enumerate(lines):
        if i == 0 or not same_scene(lines[i - 1], ln):
            gid += 1
        out.append(gid)
    return out


def make_frame(lines, starts, durs, total, hud_label):
    G = groups(lines)
    gs = {}
    for i, g in enumerate(G):
        s, e = starts[i], starts[i] + durs[i] + GAP
        gs[g] = (min(gs[g][0], s), max(gs[g][1], e)) if g in gs else (s, e)
    first_end = min(i for i, ln in enumerate(lines) if ln["scene"] in ENDING_SCENES)
    FADE = 0.28

    def frame(c, t):
        background(c, t)
        cur = max([i for i in range(len(lines)) if starts[i] <= t] or [0])
        g = G[cur]
        for gg in (g - 1, g):
            if gg < 0:
                continue
            s, e = gs[gg]
            if gg == g - 1 and t > e + FADE:
                continue
            a = min(1.0, (t - s) / FADE) if gg == g else max(0.0, 1 - (t - e) / FADE)
            if gg == g - 1 and g in gs:
                a = max(0.0, 1 - (t - gs[g][0]) / FADE)
            if a <= 0:
                continue
            i0 = G.index(gg)
            ln = lines[i0]
            p = max(0.0, min(1.0, (t - s) / (e - s)))
            zoom = 1.0 + 0.05 * p
            c.save(); c.translate(W / 2, CY); c.scale(zoom, zoom); c.translate(-W / 2, -CY)
            args = dict(ln.get("args", {})); args.setdefault("sub", ln.get("sub", ""))
            SCENES[ln["scene"]](c, t, p, a, args, {"dur": e - s})
            c.restore()
        if hud_label and t < starts[first_end]:
            ha = min(1.0, (t - starts[0]) / 0.3) * max(0.0, min(1.0, (starts[first_end] - t) / 0.3))
            alarm = lines[cur]["scene"] in ("phone", "clock") or lines[cur].get("args", {}).get("alarm", False)
            hud(c, hud_label, t, ha, alarm, 140 if alarm else 72)
        for i, ln in enumerate(lines):
            if starts[i] <= t < starts[i] + durs[i] + GAP:
                caption(c, ln["text"], ln["hl"], 1560, min(1, (t - starts[i]) / 0.15))
        c.set_source(rg(W / 2, H / 2, 500, 1250, [(0, (0, 0, 0, 0)), (1, (0, 0, 0, 0.75))])); c.paint()
    return frame, G, gs


# ---------- 音 ----------
def sfx(kind, n):
    tt = np.arange(n) / SR
    rng = np.random.default_rng(len(kind))
    if kind == "thud":
        return (np.sin(2 * np.pi * (70 - 30 * tt) * tt) * np.exp(-tt * 9) + rng.normal(0, 0.3, n) * np.exp(-tt * 25)) * 0.9
    if kind == "tick":
        return np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 120) * 0.25
    if kind.startswith("pop"):
        f = {"pop": 880, "pop_low": 520, "pop_hi": 1250}[kind]
        return np.sin(2 * np.pi * f * tt * (1 + 0.5 * np.exp(-tt * 30))) * np.exp(-tt * 18) * 0.35
    if kind == "whoosh":
        noise = rng.normal(0, 1, n)
        env = np.sin(np.pi * np.clip(tt / (n / SR), 0, 1)) ** 2
        return np.convolve(noise, np.ones(40) / 40, mode="same") * env * 0.5
    return np.zeros(n)


def add(track, s, t):
    a = int(t * SR)
    e = min(len(track), a + len(s))
    if 0 <= a < len(track):
        track[a:e] += s[: e - a]


def build_audio(lines, wavs, starts, durs, total, G, gs, out_wav):
    n = int(total * SR); tt = np.arange(n) / SR
    pad = sum(np.sin(2 * np.pi * f * tt + k) * g for k, (f, g) in enumerate([(55, .5), (82.4, .3), (110, .2), (164.8, .08)]))
    pad *= 0.06 * (0.75 + 0.25 * np.sin(2 * np.pi * 0.08 * tt))
    pad *= np.minimum(1, np.minimum(tt / 1.5, (total - tt) / 1.5))
    track = pad
    for s, x in zip(starts, wavs):
        add(track, x * 0.95, s)
    done = set()
    for i, ln in enumerate(lines):
        g = G[i]
        if g in done:
            continue
        done.add(g)
        s, e = gs[g]; d = e - s
        if i > 0:
            add(track, sfx("whoosh", int(0.45 * SR)) * 0.35, s - 0.15)
        for ev in SFX.get(ln["scene"], []):
            if ev[0] == "ticks":
                for k in range(int(d / 0.17)):
                    add(track, sfx("tick", int(0.05 * SR)), s + k * 0.17)
            elif ev[0] == "ticks_check":
                m = len(ln.get("args", {}).get("items", [1, 2, 3]))
                for k in range(m):
                    add(track, sfx("pop", int(0.25 * SR)), s + (0.15 + (k + 0.9) * 0.6 / m) * d)
            elif ev[0] == "steps":
                m = int(ln.get("args", {}).get("steps", 6)) - 1
                for k in range(m):
                    add(track, sfx("pop_low", int(0.2 * SR)) * 0.8, s + d * ((k + 1) / m) ** 0.9 * 0.95)
            elif ev[0] == "chain":
                m = min(12, int(ln.get("args", {}).get("n", 21)))
                for k in range(m):
                    add(track, sfx("tick", int(0.05 * SR)) * 2, s + d * (0.1 + 0.7 * k / m))
            elif ev[0] == "bars":
                m = len(ln.get("args", {}).get("values", [1, 2, 3, 4]))
                for k in range(m):
                    add(track, sfx("pop", int(0.25 * SR)) * 0.8, s + d * (0.3 + k * 0.12))
            elif ev[0] == "phone":
                for k in range(int(d / 0.17)):
                    add(track, sfx("tick", int(0.05 * SR)) * 0.7, s + k * 0.17)
            else:
                add(track, sfx(ev[1], int(0.6 * SR)), s + ev[0] * d)
    track = np.clip(track / np.abs(track).max() * 0.92, -1, 1)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((track * 32767).astype(np.int16).tobytes())


def load_wav(p):
    w = wave.open(str(p))
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32767
    if w.getnchannels() == 2:
        x = x[::2]
    return np.interp(np.arange(0, len(x), sr / SR), np.arange(len(x)), x)


def main(script_path, lang, wav_dir, out):
    script = json.loads(Path(script_path).read_text())
    lines = build_lines(script, lang)
    for ln in lines:
        assert ln["scene"] in SCENES, f"知らないシーン: {ln['scene']}"
    wavs = [load_wav(Path(wav_dir) / f"l{i:02d}.wav") for i in range(1, len(lines) + 1)]
    durs = [len(x) / SR for x in wavs]
    starts, t = [], LEAD
    for d in durs:
        starts.append(t); t += d + GAP
    total = t + 0.8
    hud_label = script.get("hud", {}).get(lang, "")
    frame, G, gs = make_frame(lines, starts, durs, total, hud_label)
    wavp = Path(out).with_suffix(".wav")
    build_audio(lines, wavs, starts, durs, total, G, gs, wavp)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    grains = [np.random.default_rng(k).integers(-6, 7, (H, W, 1), dtype=np.int16) for k in range(6)]

    def render(tsec, k):
        frame(c, tsec); surf.flush()
        arr = np.ndarray((H, W, 4), np.uint8, surf.get_data()).astype(np.int16)
        arr[:, :, :3] += grains[k % 6]
        return np.clip(arr, 0, 255).astype(np.uint8)

    if "--frames" in sys.argv:
        from PIL import Image
        outdir = Path(out).with_suffix("")
        outdir.mkdir(parents=True, exist_ok=True)
        for i in range(len(lines)):
            arr = render(starts[i] + (durs[i] + GAP) * 0.75, i)
            Image.fromarray(arr[:, :, [2, 1, 0]]).resize((540, 960)).save(outdir / f"f{i + 1:02d}_{lines[i]['scene']}.jpg", quality=85)
        print("frames", outdir, round(total, 1)); return
    tmp = Path(out).with_suffix(".tmp.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(wavp), "-map", "0:v", "-map", "1:a",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "25", "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    for k in range(int(total * FPS)):
        p.stdin.write(render(k / FPS, k).tobytes())
    p.stdin.close()
    if p.wait() == 0:
        tmp.rename(out); wavp.unlink(missing_ok=True); print(out, round(total, 1))
    else:
        sys.exit("ffmpeg error")


if __name__ == "__main__":
    main(*sys.argv[1:5])
