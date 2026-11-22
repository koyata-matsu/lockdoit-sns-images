#!/usr/bin/env python3
"""Lock Do it TikTok/Instagram スライド画像を作る（Canva不要）

使い方:
  python3 render.py post.json 出力フォルダ [素材フォルダ]

post.json の形:
  {"no": 30, "type": "アプリ紹介" or "Tips", "theme": "勉強|スマホ断ち|ToDo",
   "slides": ["1枚目の文字 / 改行は ' / '", ...], "photo": "素材フォルダ内の写真パス(任意)"}

できあがり: 出力フォルダ/1.jpg 2.jpg ...（1080x1920）
"""
import html
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

W, H = 1080, 1920

ICON_SVG = """
<svg viewBox="0 0 512 512" width="{s}" height="{s}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <rect width="512" height="512" rx="0" fill="#16202e"/>
  <path d="M176 230v-46a80 80 0 0 1 160 0v46" fill="none" stroke="#f5b84a" stroke-width="44" stroke-linecap="round"/>
  <rect x="120" y="222" width="272" height="196" rx="40" fill="#f5b84a"/>
  <path d="M190 318l46 44 88-92" fill="none" stroke="#16202e" stroke-width="34" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;background:#fff}
body{font-family:'Noto Sans CJK JP','Noto Color Emoji',sans-serif;color:#111;
  display:flex;flex-direction:column;align-items:center;justify-content:flex-start}
.text{margin-top:{top}px;width:920px;text-align:center;font-weight:700;
  font-size:{fs}px;line-height:1.45;letter-spacing:.02em;word-break:keep-all;overflow-wrap:anywhere}
.text .l{display:block;white-space:nowrap}
.media{margin-top:56px;display:flex;justify-content:center}
.photo{width:760px;height:760px;object-fit:cover}
.phone{height:1000px;width:auto;border-radius:36px;box-shadow:0 10px 40px rgba(0,0,0,.12)}
.icon{margin-top:72px}
.num{font-size:44px;color:#999;margin-top:0}
"""


def text_html(t):
    lines = [x.strip() for x in t.replace("\n", " / ").split(" / ") if x.strip()]
    return "".join(f'<span class="l">{html.escape(x)}</span>' for x in lines), lines


def text_width(s):
    """全角1文字=1、半角=0.55 として行の幅を数える"""
    return sum(0.55 if ord(c) < 0x2E80 and not (0x2460 <= ord(c) <= 0x24FF) else 1 for c in s)


def font_size(lines, base):
    longest = max((text_width(x) for x in lines), default=1)
    # 1行に収まるよう、長い行ほど小さく
    fs = min(base, int(900 / max(longest, 1)))
    return max(fs, 56)


def data_uri(path):
    import base64, mimetypes
    p = Path(path)
    mt = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    return f"data:{mt};base64," + base64.b64encode(p.read_bytes()).decode()


def build_page(kind, text, img=None, assets=None):
    inner, lines = text_html(text)
    if kind == "photo":
        fs, top, media = font_size(lines, 86), 330, f'<div class="media"><img class="photo" src="{img}"></div>'
    elif kind == "phone":
        fs, top, media = font_size(lines, 80), 200, f'<div class="media"><img class="phone" src="{img}"></div>'
    elif kind == "cta":
        fs, top, media = font_size(lines, 88), 380, f'<div class="icon">{ICON_SVG.format(s=520)}</div>'
    else:  # text only
        fs, top, media = font_size(lines, 104), max(760 - 80 * (len(lines) - 1), 300), ""
    css = CSS.replace("{top}", str(top)).replace("{fs}", str(fs))
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body><div class='text'>{inner}</div>{media}</body></html>"


def plan(post, assets):
    """各スライドの見た目を決める"""
    slides = [s for s in post["slides"] if s and str(s).strip()]
    photo = post.get("photo")
    photo_uri = data_uri(Path(assets) / photo) if photo else None
    out = []
    n = len(slides)
    for i, s in enumerate(slides):
        last = i == n - 1
        if last and ("Lock Do it" in s or "App Store" in s):
            out.append(("cta", s, None))
        elif i == 0 and photo_uri:
            out.append(("photo", s, photo_uri))
        elif post.get("type") == "アプリ紹介" and i in (1, 2, 3):
            screen = {1: "todo.png", 2: "lock.png", 3: "done.png"}[i]
            out.append(("phone", s, data_uri(Path(assets) / "app_screens" / screen)))
        else:
            out.append(("text", s, None))
    return out


def render(post, outdir, assets):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    files = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for i, (kind, s, img) in enumerate(plan(post, assets), 1):
            pg.set_content(build_page(kind, s, img), wait_until="load")
            pg.wait_for_timeout(150)
            f = outdir / f"{i}.jpg"
            pg.screenshot(path=str(f), type="jpeg", quality=88, full_page=False)
            files.append(str(f))
        b.close()
    return files


if __name__ == "__main__":
    post = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    assets = sys.argv[3] if len(sys.argv) > 3 else str(Path(__file__).parent)
    print("\n".join(render(post, sys.argv[2], assets)))
