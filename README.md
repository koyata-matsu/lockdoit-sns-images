# lockdoit-sns-images

Lock Do it（iPhoneアプリ）の TikTok / Instagram 投稿用の画像置き場。
毎晩の予約タスクが、ここで画像を作って Publer に渡す（Canva は使わない）。

- `make_post.py` … 投稿1本分のスライド画像（1080×1920）を `posts/NoXXX/` に作る
- `render.py` … スライドの見た目（白背景・上に文字・下に写真/アプリ画面・最後にアイコン）
- `assets/` … 写真（Pixabay、`photos/credits_pixabay.csv`）とアプリ画面
- `data/posts_extra.json` … No.101以降の投稿の文字（No.1〜100 は「投稿100本リスト」シートが元）

ここに置くのは公開する投稿用の画像だけ。パスワードや個人情報は置かない。
