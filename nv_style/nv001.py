"""NeuronVisuals風ミニマルアニメ 第1弾「猿の壺（モンキートラップ）」
暗い背景・白い線画・最小限の色。音声は videos の外で用意した行ごとのwav。
python3 nv001.py <wavフォルダ> <出力mp4>
"""
import math
import subprocess
import sys
import wave
from pathlib import Path

import cairo
import numpy as np

W, H, FPS = 1080, 1920, 30
BG = (0.05, 0.05, 0.06)
WHITE = (0.93, 0.93, 0.93)
GREY = (0.45, 0.45, 0.48)
RED = (0.90, 0.28, 0.30)
YEL = (0.96, 0.78, 0.29)
BLUE = (0.45, 0.70, 1.0)
LEAD, GAP = 0.35, 0.40

LINES = [
    "猿を捕まえる、昔ながらの罠がある。",
    "小さな穴の空いた壺に、\nバナナを一本入れておくだけ。",
    "猿は手を入れて、バナナをつかむ。",
    "でも、握ったままだと、手が抜けない。",
    "放せば、逃げられる。\nなのに、放さない。",
    "そして、捕まる。",
    "僕らも毎日、スマホで\n同じことをしてる。",
    "あと一本だけ。あと五分だけ。",
    "握っているのは、ほんの小さな楽しみ。",
    "失っているのは、今日という一日。",
    "手を放そう。\nやることが終わるまで。",
    "これ、必要な人に送ってあげて。",
]


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, x):
    return a + (b - a) * x


# ---------- 部品 ----------
CX, CY = 540, 980  # 壺の中心


def jar_path(c):
    # 細い口・丸い胴の壺
    c.new_path()
    c.move_to(CX - 70, CY - 260)
    c.line_to(CX - 70, CY - 200)
    c.curve_to(CX - 250, CY - 170, CX - 260, CY + 220, CX - 150, CY + 250)
    c.line_to(CX + 150, CY + 250)
    c.curve_to(CX + 260, CY + 220, CX + 250, CY - 170, CX + 70, CY - 200)
    c.line_to(CX + 70, CY - 260)


def draw_jar(c, a):
    jar_path(c)
    c.set_source_rgba(1, 1, 1, 0.04 * a)
    c.fill_preserve()
    c.set_source_rgba(*WHITE, a)
    c.set_line_width(7)
    c.stroke()
    # 口の縁
    c.set_line_width(7)
    c.move_to(CX - 95, CY - 262)
    c.line_to(CX + 95, CY - 262)
    c.stroke()


def draw_banana(c, x, y, a, rot=0.0, scale=1.0):
    c.save()
    c.translate(x, y)
    c.rotate(rot)
    c.scale(scale, scale)
    c.new_path()
    c.move_to(-80, -10)
    c.curve_to(-40, 50, 40, 50, 80, -10)
    c.curve_to(40, 20, -40, 20, -80, -10)
    c.set_source_rgba(*YEL, a)
    c.fill_preserve()
    c.set_line_width(4)
    c.stroke()
    c.restore()


def draw_monkey(c, x, y, a, tilt=0.0):
    c.save()
    c.translate(x, y)
    c.rotate(tilt)
    c.set_line_width(7)
    c.set_source_rgba(*WHITE, a)
    for ex in (-78, 78):  # 耳
        c.new_path(); c.arc(ex, -10, 28, 0, 2 * math.pi); c.stroke()
    c.new_path(); c.arc(0, 0, 75, 0, 2 * math.pi); c.stroke()
    # 顔のふち
    c.new_path(); c.arc(0, 18, 46, 0.1 * math.pi, 0.9 * math.pi); c.stroke()
    for ex in (-24, 24):
        c.new_path(); c.arc(ex, -10, 7, 0, 2 * math.pi); c.fill()
    c.restore()


def draw_arm(c, x0, y0, x1, y1, a, fist=False, fist_r=34):
    c.set_source_rgba(*WHITE, a)
    c.set_line_width(14)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.new_path()
    mx, my = (x0 + x1) / 2, min(y0, y1) - 60
    c.move_to(x0, y0)
    c.curve_to(mx, my, mx, my, x1, y1)
    c.stroke()
    c.new_path()
    c.arc(x1, y1, fist_r if fist else 26, 0, 2 * math.pi)
    c.set_line_width(7)
    if fist:
        c.fill_preserve()
    c.stroke()


def draw_phone(c, x, y, a, glow=0.0, scroll=0.0):
    w, h = 120, 220
    if glow > 0:
        g = cairo.RadialGradient(x, y, 10, x, y, 260)
        g.add_color_stop_rgba(0, *BLUE, 0.35 * glow * a)
        g.add_color_stop_rgba(1, *BLUE, 0)
        c.set_source(g)
        c.paint()
    c.new_path()
    r = 22
    c.arc(x - w / 2 + r, y - h / 2 + r, r, math.pi, 1.5 * math.pi)
    c.arc(x + w / 2 - r, y - h / 2 + r, r, 1.5 * math.pi, 2 * math.pi)
    c.arc(x + w / 2 - r, y + h / 2 - r, r, 0, 0.5 * math.pi)
    c.arc(x - w / 2 + r, y + h / 2 - r, r, 0.5 * math.pi, math.pi)
    c.close_path()
    c.set_source_rgba(0.08, 0.10, 0.14, a)
    c.fill_preserve()
    c.set_source_rgba(*WHITE, a)
    c.set_line_width(6)
    c.stroke()
    # 画面の中のフィード（流れる線）
    c.save()
    c.rectangle(x - w / 2 + 12, y - h / 2 + 16, w - 24, h - 32)
    c.clip()
    for i in range(-2, 9):
        yy = y - h / 2 + 30 + ((i * 34 - scroll) % 300) - 40
        c.set_source_rgba(*BLUE, 0.55 * a)
        c.rectangle(x - w / 2 + 22, yy, w - 44, 18)
        c.fill()
    c.restore()


def draw_heart(c, x, y, s, a):
    c.save(); c.translate(x, y); c.scale(s, s)
    c.new_path()
    c.move_to(0, 12)
    c.curve_to(-26, -6, -14, -28, 0, -12)
    c.curve_to(14, -28, 26, -6, 0, 12)
    c.set_source_rgba(*RED, a); c.fill(); c.restore()


def draw_check(c, x, y, a, p):
    c.set_source_rgba(*WHITE, a); c.set_line_width(6)
    c.rectangle(x - 34, y - 34, 68, 68); c.stroke()
    if p > 0:
        c.set_line_width(10); c.set_line_cap(cairo.LINE_CAP_ROUND)
        pts = [(x - 20, y), (x - 4, y + 18), (x + 26, y - 22)]
        c.move_to(*pts[0])
        if p < 0.5:
            q = p / 0.5
            c.line_to(lerp(pts[0][0], pts[1][0], q), lerp(pts[0][1], pts[1][1], q))
        else:
            q = (p - 0.5) / 0.5
            c.line_to(*pts[1]); c.line_to(lerp(pts[1][0], pts[2][0], q), lerp(pts[1][1], pts[2][1], q))
        c.set_source_rgba(*YEL, a); c.stroke()


def draw_lock(c, x, y, s, a):
    c.save(); c.translate(x, y); c.scale(s, s)
    c.set_source_rgba(*YEL, a)
    c.set_line_width(14)
    c.new_path(); c.arc(0, -30, 38, math.pi, 2 * math.pi); c.stroke()
    c.move_to(-38, -30); c.line_to(-38, -6); c.stroke()
    c.move_to(38, -30); c.line_to(38, -6); c.stroke()
    c.rectangle(-60, -8, 120, 90); c.fill()
    c.restore()


def text(c, s, y, size=50, a=1.0, col=WHITE, weight=cairo.FONT_WEIGHT_BOLD):
    c.select_font_face("Noto Sans CJK JP", cairo.FONT_SLANT_NORMAL, weight)
    c.set_font_size(size)
    lines = s.split("\n")
    for i, ln in enumerate(lines):
        ext = c.text_extents(ln)
        c.move_to((W - ext.x_advance) / 2, y + i * size * 1.45)
        c.set_source_rgba(*col, a)
        c.show_text(ln)


def top_pill(c, label, a, col=GREY):
    c.select_font_face("Noto Sans CJK JP", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(40)
    ext = c.text_extents(label)
    w = ext.x_advance + 70
    x0, y0 = (W - w) / 2, 330
    c.new_path()
    c.arc(x0 + 32, y0 + 32, 32, 0.5 * math.pi, 1.5 * math.pi)
    c.arc(x0 + w - 32, y0 + 32, 32, 1.5 * math.pi, 0.5 * math.pi)
    c.close_path()
    c.set_source_rgba(*col, 0.9 * a); c.set_line_width(4); c.stroke()
    c.move_to(x0 + 35, y0 + 46); c.set_source_rgba(*WHITE, a); c.show_text(label)


# ---------- タイムライン ----------
def build_timeline(durs):
    starts, t = [], LEAD
    for d in durs:
        starts.append(t)
        t += d + GAP
    return starts, t + 0.6


def frame(c, t, starts, durs, total):
    c.set_source_rgb(*BG); c.paint()

    def P(i, a=0.0, b=1.0):  # 行iの中での進み具合（a〜bの範囲を0〜1に）
        s, d = starts[i], durs[i] + GAP
        x = (t - s) / d
        return ease((x - a) / (b - a))

    def active(i):
        return t >= starts[i]

    part2 = t >= starts[6]
    MONKEY = (CX - 290, CY - 430)
    BANANA_IN = (CX, CY + 150)
    if not part2:
        fade_out = 1 - P(5, 0.75, 1.0) if active(5) else 1.0
        a = P(0, 0, 0.35) * fade_out
        draw_jar(c, a)
        tilt = 0.06 * math.sin(t * 2.0)
        # バナナが落ちる
        if active(1):
            q = P(1, 0.25, 0.75)
            by = lerp(CY - 520, BANANA_IN[1], q)
            if q < 1 and not active(2):
                draw_banana(c, CX, by, a, rot=q * 0.6)
            elif not active(2):
                draw_banana(c, *BANANA_IN, a)
        draw_monkey(c, *MONKEY, P(0, 0.2, 0.6) * fade_out, tilt)
        if active(2):
            reach = P(2, 0.0, 0.7)
            hx = CX
            hy = lerp(CY - 330, BANANA_IN[1] - 10, reach)
            grabbed = reach >= 1
            pull = 0.0
            if active(3):
                pull = math.sin((t - starts[3]) * 14) * 18 * (1 - P(5, 0.0, 0.5) if active(5) else 1)
                hy = lerp(BANANA_IN[1] - 10, CY - 205, P(3, 0.0, 0.25)) + pull
            if grabbed:
                draw_banana(c, hx, hy + 18, a, scale=0.75)
            draw_arm(c, MONKEY[0] + 60, MONKEY[1] + 60, hx, hy, a, fist=grabbed, fist_r=52 if grabbed else 26)
            if active(3) and int(t * 6) % 2 == 0 and not active(5):
                c.set_source_rgba(*RED, a)
                text(c, "！", CY - 300, 90, a, RED)
        if active(4):
            # 「放せば逃げられる」：一瞬だけ手が開く幻
            q = P(4, 0.05, 0.35) * (1 - P(4, 0.45, 0.7))
            if q > 0.01:
                c.set_dash([14, 14])
                draw_arm(c, MONKEY[0] + 60, MONKEY[1] + 60, CX + 220, CY - 520, q * 0.6 * a)
                c.set_dash([])
        if active(5):
            # 檻が落ちてくる
            q = P(5, 0.0, 0.35)
            c.set_source_rgba(*WHITE, fade_out)
            c.set_line_width(8)
            for i in range(9):
                x = 150 + i * 97.5
                c.move_to(x, 380)
                c.line_to(x, lerp(380, 1330, q))
                c.stroke()
            c.move_to(140, 380); c.line_to(940, 380); c.stroke()
        top_pill(c, "モンキートラップ", P(0, 0, 0.3) * fade_out)
    else:
        a = P(6, 0, 0.3)
        if active(11):
            a *= 1 - P(11, 0.0, 0.3)
        draw_jar(c, a)
        PH = (CX, CY + 80)
        release = P(10, 0.05, 0.4) if active(10) else 0.0
        scroll = (t - starts[6]) * 260 * (1 - release)
        glow = (0.6 + 0.4 * math.sin(t * 5)) * (1 - release)
        phone_y = PH[1] + release * 120
        draw_phone(c, PH[0], phone_y, a, glow=glow, scroll=scroll)
        # 人の腕（右から）
        hand_y = lerp(CY - 330, PH[1] - 60, P(6, 0.15, 0.6))
        if active(10):
            hand_y = lerp(PH[1] - 60, CY - 520, P(10, 0.2, 0.7))
        draw_arm(c, W + 40, CY - 560, CX, hand_y, a, fist=not active(10), fist_r=48)
        # 時間のピル
        if active(7):
            secs = 5 * 60 + (t - starts[7]) ** 2.3 * 160
            secs = min(secs, 3 * 3600 + 27 * 60)
            if active(10):
                secs = 3 * 3600 + 27 * 60
            hh, mm = int(secs // 3600), int(secs % 3600 // 60)
            label = f"スマホ {hh}時間{mm:02d}分" if hh else f"スマホ {mm}分"
            top_pill(c, label, a, RED if hh >= 1 else GREY)
        # 小さな楽しみ（ハート）
        if active(8) and not active(10):
            for k in range(6):
                ph = ((t - starts[8]) * 0.9 + k / 6) % 1
                draw_heart(c, PH[0] + math.sin(k * 2.1) * 120, PH[1] - 140 - ph * 260, 1.4, (1 - ph) * a)
        # 1日が終わる（太陽→月）
        if active(9):
            q = P(9, 0.0, 0.9)
            ang = math.pi * (1 - q)
            sx, sy = W / 2 + math.cos(ang) * 380, 560 - math.sin(ang) * 150
            c.new_path(); c.arc(sx, sy, 34, 0, 2 * math.pi)
            col = tuple(lerp(YEL[i], GREY[i], q) for i in range(3))
            c.set_source_rgba(*col, a * (1 - (P(10, 0, 0.3) if active(10) else 0)))
            c.fill()
        # 手を放す → チェックが付いていく
        if active(10):
            for k in range(3):
                draw_check(c, 330 + k * 210, 1420 - 120, a, P(10, 0.35 + k * 0.17, 0.5 + k * 0.17))
        if active(11):
            q = P(11, 0.0, 0.4)
            draw_lock(c, W / 2, 900, 1.6, q)
            text(c, "Lock Do it", 1130, 64, q, WHITE)
            text(c, "やることが終わるまで、SNSにロック", 1215, 40, q, GREY, cairo.FONT_WEIGHT_NORMAL)
    # 字幕
    for i in range(len(LINES)):
        if starts[i] <= t < starts[i] + durs[i] + GAP:
            q = min(1, (t - starts[i]) / 0.15)
            text(c, LINES[i], 1560, 54, q)


def main(wav_dir, out):
    wavs, durs = [], []
    for i in range(1, len(LINES) + 1):
        w = wave.open(str(Path(wav_dir) / f"l{i:02d}.wav"))
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32767
        x = np.interp(np.arange(0, len(x), sr / 48000), np.arange(len(x)), x)
        wavs.append(x)
        durs.append(len(x) / 48000)
    starts, total = build_timeline(durs)
    # 音：声＋低いドローン
    n = int(total * 48000)
    tt = np.arange(n) / 48000
    drone = (np.sin(2 * np.pi * 55 * tt) * 0.5 + np.sin(2 * np.pi * 82.4 * tt) * 0.3 + np.sin(2 * np.pi * 110 * tt) * 0.15)
    drone *= 0.05 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.1 * tt))
    fade = np.minimum(1, np.minimum(tt / 1.5, (total - tt) / 1.5))
    track = drone * fade
    for s, x in zip(starts, wavs):
        a = int(s * 48000)
        track[a:a + len(x)] += x[: max(0, min(len(x), n - a))] * 0.9
    track = np.clip(track / np.abs(track).max() * 0.92, -1, 1)
    wav = Path(out).with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
        w.writeframes((track * 32767).astype(np.int16).tobytes())
    if "--frames" in sys.argv:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        c = cairo.Context(surf)
        for k, tsec in enumerate([starts[1] + 1.8, starts[3] + 1.0, starts[5] + 1.0, starts[8] + 1.5, starts[10] + 2.2, starts[11] + 1.5]):
            frame(c, tsec, starts, durs, total)
            surf.write_to_png(f"/tmp/nvf_{k}.png")
        print("frames ok", total)
        return
    tmp = Path(out).with_suffix(".tmp.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(wav), "-map", "0:v", "-map", "1:a",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(tmp)],
                         stdin=subprocess.PIPE)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    for k in range(int(total * FPS)):
        frame(c, k / FPS, starts, durs, total)
        surf.flush()
        p.stdin.write(bytes(surf.get_data()))
    p.stdin.close()
    if p.wait() == 0:
        tmp.rename(out)
        print(out, round(total, 1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
