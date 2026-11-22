"""Lock Do it 縦動画メーカー（AI読み上げ＋写真をゆっくり動かす＋字幕）

使い方:  python3 make_video.py videos/v001.json
出力:    videos/out/<name>.mp4

台本JSONの形:
{
  "name": "v001",
  "scenes": [
    {"kind": "photo", "img": "assets/photos/phone/xxx.jpg", "text": "画面に出す字幕", "say": "読み上げ（省略時はtext）", "hl": "黄色にする語"},
    {"kind": "screen", "img": "assets/app_screens/todo.png", "text": "...", "say": "..."},
    {"kind": "cta", "text": "...", "say": "..."}
  ]
}
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pyopenjtalk
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
ROOT = Path(__file__).parent
FONT = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", 86, index=0)
FONT_S = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", 54, index=0)
NAVY, YELLOW, WHITE = (22, 32, 46), (245, 184, 74), (255, 255, 255)
SR = 48000
PAD = 0.45  # 1シーンの読み上げ後の間（秒）


# ---------- 声 ----------
def voice(text):
    x, sr = pyopenjtalk.tts(text, speed=1.12, half_tone=1.0)
    x = x.astype(np.float64)
    x = x / (np.abs(x).max() + 1e-9) * 0.85
    return x  # float, sr=48000


def bgm(seconds):
    """やさしいピアノ風のコード（Am-F-C-G）を自前で合成"""
    t_total = int(seconds * SR)
    out = np.zeros(t_total)
    chords = [[57, 60, 64], [53, 57, 60], [48, 55, 64], [55, 59, 62]]
    beat = 0.5
    n = 0
    t = 0.0
    while t < seconds:
        ch = chords[int(t // 2.0) % 4]
        note = ch[n % 3] + (12 if n % 4 == 3 else 0)
        f = 440 * 2 ** ((note - 69) / 12)
        L = int(1.6 * SR)
        tt = np.arange(L) / SR
        env = np.exp(-tt * 2.6) * (1 - np.exp(-tt * 200))
        w = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(4 * np.pi * f * tt) + 0.12 * np.sin(6 * np.pi * f * tt)) * env
        s = int(t * SR)
        e = min(t_total, s + L)
        out[s:e] += w[: e - s] * 0.18
        # 低音
        if n % 4 == 0:
            fb = 440 * 2 ** ((ch[0] - 12 - 69) / 12)
            Lb = int(2.0 * SR)
            tb = np.arange(Lb) / SR
            wb = np.sin(2 * np.pi * fb * tb) * np.exp(-tb * 1.2) * (1 - np.exp(-tb * 80)) * 0.22
            eb = min(t_total, s + Lb)
            out[s:eb] += wb[: eb - s]
        n += 1
        t += beat
    fade = int(1.5 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


# ---------- 絵 ----------
def wrap(text):
    return [l for l in text.split("\n") if l]


def caption_layer(text, hl="", y_center=None, font=FONT, box=True):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    lines = wrap(text)
    lh = int(font.size * 1.38)
    total = lh * len(lines)
    y0 = (y_center if y_center else H // 2) - total // 2
    for i, line in enumerate(lines):
        y = y0 + i * lh
        # 黄色にする語を分けて描く
        parts = [(line, WHITE)]
        if hl and hl in line:
            a, b = line.split(hl, 1)
            parts = [(a, WHITE), (hl, YELLOW), (b, WHITE)]
        tw = sum(d.textlength(p, font=font) for p, _ in parts)
        x = (W - tw) / 2
        if box:
            d.rounded_rectangle([x - 34, y - 10, x + tw + 34, y + lh - 14], 22, fill=(0, 0, 0, 150))
        for p, col in parts:
            d.text((x, y), p, font=font, fill=col, stroke_width=3, stroke_fill=(0, 0, 0))
            x += d.textlength(p, font=font)
    return lay


def lock_icon(size):
    s = size / 512
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size, size], int(110 * s), fill=NAVY + (255,))
    d.arc([176 * s, 104 * s, 336 * s, 264 * s], 180, 360, fill=YELLOW, width=int(44 * s))
    d.line([176 * s, 184 * s, 176 * s, 236 * s], fill=YELLOW, width=int(44 * s))
    d.line([336 * s, 184 * s, 336 * s, 236 * s], fill=YELLOW, width=int(44 * s))
    d.rounded_rectangle([120 * s, 222 * s, 392 * s, 418 * s], int(40 * s), fill=YELLOW)
    d.line([(190 * s, 318 * s), (236 * s, 362 * s), (324 * s, 270 * s)], fill=NAVY, width=int(34 * s), joint="curve")
    return im


def cover(img, w, h):
    r = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * r + 1), int(img.height * r + 1)), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def scene_frames(sc, dur, idx):
    n = int(round(dur * FPS))
    kind = sc["kind"]
    if kind == "photo":
        base = Image.open(ROOT / sc["img"]).convert("RGB")
        big = cover(base, int(W * 1.18), int(H * 1.18))
        big = ImageEnhance.Brightness(big).enhance(0.62)
        cap = caption_layer(sc["text"], sc.get("hl", ""), y_center=int(H * 0.5))
        zoom_in = idx % 2 == 0
        for i in range(n):
            p = i / max(1, n - 1)
            z = 1.0 + 0.10 * (p if zoom_in else 1 - p)  # 1.0〜1.10
            cw, ch = big.width / z / 1.18 * 1.0, big.height / z / 1.18 * 1.0
            cx, cy = big.width / 2 + (p - 0.5) * 30, big.height / 2
            box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
            fr = big.resize((W, H), Image.BILINEAR, box=box).convert("RGBA")
            a = min(1.0, i / 7)
            c = cap if a >= 1 else Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 0)), cap, a)
            fr.alpha_composite(c)
            yield fr.convert("RGB")
    elif kind == "screen":
        bg = Image.new("RGB", (W, H), NAVY)
        shot = Image.open(ROOT / sc["img"]).convert("RGB")
        ph_h = 1240
        shot = shot.resize((int(shot.width * ph_h / shot.height), ph_h), Image.LANCZOS)
        mask = Image.new("L", shot.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, shot.width, shot.height], 56, fill=255)
        cap = caption_layer(sc["text"], sc.get("hl", ""), y_center=250, box=False)
        for i in range(n):
            p = i / max(1, n - 1)
            z = 1.0 + 0.05 * p
            s2 = shot.resize((int(shot.width * z), int(shot.height * z)), Image.BILINEAR)
            m2 = mask.resize(s2.size)
            fr = bg.copy()
            rise = int(40 * (1 - min(1, i / 9)) ** 2)
            fr.paste(s2, ((W - s2.width) // 2, 470 + rise), m2)
            fr = fr.convert("RGBA")
            fr.alpha_composite(cap)
            yield fr.convert("RGB")
    elif kind == "cta":
        bg = Image.new("RGBA", (W, H), NAVY + (255,))
        icon = lock_icon(380)
        cap = caption_layer(sc["text"], sc.get("hl", ""), y_center=1180, box=False)
        sub = caption_layer(sc.get("sub", ""), "", y_center=1480, font=FONT_S, box=False) if sc.get("sub") else None
        for i in range(n):
            p = min(1, i / 10)
            sz = int(380 * (0.85 + 0.15 * p))
            ic = icon.resize((sz, sz), Image.LANCZOS)
            fr = bg.copy()
            fr.alpha_composite(ic, ((W - sz) // 2, 560 - sz // 2))
            fr.alpha_composite(cap)
            if sub:
                fr.alpha_composite(sub)
            yield fr.convert("RGB")


def encode(frames, path):
    tmp = path.with_suffix(".tmp.mp4")
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(tmp)],
        stdin=subprocess.PIPE)
    for fr in frames:
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    if p.wait() == 0:
        tmp.rename(path)
    else:
        raise SystemExit("ffmpeg failed")


def main(spec_path, preview=False):
    spec = json.loads(Path(spec_path).read_text())
    out_dir = ROOT / "videos" / "out"
    work = out_dir / f"_{spec['name']}"
    work.mkdir(parents=True, exist_ok=True)
    # 1) 声とシーンの長さ
    voices, durs = [], []
    for sc in spec["scenes"]:
        v = voice(sc.get("say", sc["text"].replace("\n", "")))
        voices.append(v)
        durs.append(round((len(v) / SR + PAD) * FPS) / FPS)
    total = sum(durs)
    # 2) 音（声＋BGM）
    track = bgm(total)
    t = 0.0
    for v, d in zip(voices, durs):
        s = int((t + 0.12) * SR)
        e = min(len(track), s + len(v))
        track[s:e] += v[: e - s]
        t += d
    track = np.clip(track / (np.abs(track).max() + 1e-9) * 0.92, -1, 1)
    wav = work / "audio.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((track * 32767).astype(np.int16).tobytes())
    if preview:  # 字幕が一番多い瞬間の静止画だけ
        for i, (sc, d) in enumerate(zip(spec["scenes"], durs)):
            frs = list(scene_frames(sc, 0.5, i))
            frs[-1].save(work / f"preview_{i:02d}.jpg", quality=88)
        print("preview ok", total)
        return
    # 3) シーンごとに動画
    files = []
    for i, (sc, d) in enumerate(zip(spec["scenes"], durs)):
        f = work / f"s{i:02d}.mp4"
        encode(scene_frames(sc, d, i), f)
        files.append(f)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{f.name}'\n" for f in files))
    final = out_dir / f"{spec['name']}.mp4"
    tmp = out_dir / f"{spec['name']}.tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.rename(final)
    print(final, round(total, 2), "sec")


if __name__ == "__main__":
    main(sys.argv[1], preview="--preview" in sys.argv)
