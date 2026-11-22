#!/usr/bin/env python3
"""投稿1本分の画像を作る（毎晩の予約タスク用）

使い方:
  python3 make_post.py post.json
    post.json = {"no": 30, "type": "アプリ紹介" or "Tips",
                 "account": "Bスマホ断ち垢" など（任意）, "theme": "勉強" など（任意）,
                 "slides": ["1枚目 / 改行", ...], "caption": "説明文"}
  No.101以降は post.json のかわりに番号だけでもOK:
  python3 make_post.py 107      ← data/posts_extra.json から読む

できあがり: posts/No030/1.jpg 2.jpg ... と caption.txt
画像のURL: https://raw.githubusercontent.com/koyata-matsu/lockdoit-sns-images/main/posts/No030/1.jpg
"""
import json
import sys
from pathlib import Path

from render import render

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
USED = HERE / "data" / "used_photos.json"
REPO_RAW = "https://raw.githubusercontent.com/koyata-matsu/lockdoit-sns-images/main"


def photo_dir(post):
    text = " ".join(post.get("slides", [])[:1]) + " " + post.get("account", "") + " " + post.get("theme", "")
    if any(k in text for k in ("瞑想", "呼吸", "マインドフル")):
        return "meditation"
    if any(k in text for k in ("勉強", "受験", "テスト", "資格", "復習")):
        return "study"
    if any(k in text for k in ("スマホ断ち", "SNS", "スマホ", "TikTok", "インスタ")):
        return "phone"
    if any(k in text for k in ("ToDo", "仕事", "タスク")):
        return "work"
    if any(k in text for k in ("習慣", "続")):
        return "habit"
    if "メンタル" in text or "自己" in text or "自分" in text:
        return "cafe"
    return "habit"


def pick_photo(post):
    """同じ写真がなるべく続かないように選ぶ"""
    d = photo_dir(post)
    files = sorted(p.relative_to(ASSETS).as_posix() for p in (ASSETS / "photos" / d).glob("*.jpg"))
    used = json.loads(USED.read_text()) if USED.exists() else {}
    key = f"No{post['no']}"
    if key in used and used[key] in files:  # 作り直しのときは同じ写真
        return used[key]
    counts = {f: 0 for f in files}
    for v in used.values():
        if v in counts:
            counts[v] += 1
    choice = min(files, key=lambda f: (counts[f], (sum(f.encode()) * 31 + post["no"] * 7) % 997))
    used[key] = choice
    USED.parent.mkdir(exist_ok=True)
    USED.write_text(json.dumps(used, ensure_ascii=False, indent=1))
    return choice


def load(arg):
    if arg.isdigit():
        extra = json.loads((HERE / "data" / "posts_extra.json").read_text(encoding="utf-8"))
        for p in extra["posts"]:
            if p["no"] == int(arg):
                return p
        sys.exit(f"No.{arg} は posts_extra.json に無い")
    return json.loads(Path(arg).read_text(encoding="utf-8"))


def main():
    post = load(sys.argv[1])
    post["photo"] = pick_photo(post)
    out = HERE / "posts" / f"No{int(post['no']):03d}"
    for old in out.glob("*.jpg"):
        old.unlink()
    files = render(post, out, ASSETS)
    (out / "caption.txt").write_text(post.get("caption", ""), encoding="utf-8")
    print(json.dumps({"no": post["no"], "dir": str(out.relative_to(HERE)),
                      "urls": [f"{REPO_RAW}/{Path(f).relative_to(HERE).as_posix()}" for f in files],
                      "caption": post.get("caption", "")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
