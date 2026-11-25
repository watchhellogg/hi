#!/usr/bin/env python3
"""学会動画からスライドが切り替わった瞬間だけを静止画として抜き出す。

仕組み:
  1. ffmpeg で一定間隔(既定 2 秒)ごとにフレームを書き出す
  2. 各フレームを 320x180 のグレースケールに縮小
  3. 直前に採用したスライドと比べ「明確に変化した画素」の割合が --min-change % を超えたら新スライドとして採用
     (圧縮ノイズはほぼ 0%、箇条書きが 1 行増えると約 0.4% → 既定 0.2%)
  4. 採用スライドを slide_001_00m12s.jpg のように保存し、Obsidian 用 index.md を出力

必要なもの: ffmpeg(PATH 上), Python 3.9+, Pillow (pip install pillow)

例:
  python extract_slides.py 演題03.mp4 out/演題03
  # 演者カメラが右下に小窓で出る動画 → スライド部分だけでハッシュを取る
  python extract_slides.py 演題03.mp4 out/演題03 --crop 0,0,0.75,1
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


def dhash(img: Image.Image, size: int = 16) -> int:
    """差分ハッシュ。size=16 → 256bit。
    ぼかし + margin で、白背景などの平坦部が圧縮ノイズでビット反転しないようにしている。"""
    g = img.convert("L").filter(ImageFilter.GaussianBlur(2)).resize((size + 1, size), Image.BOX)
    px = g.tobytes()
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (left > right + 3)
    return bits


def thumb(img: Image.Image) -> Image.Image:
    return img.convert("L").resize((320, 180), Image.BOX)


def changed_pct(a: Image.Image, b: Image.Image, level: int = 40) -> float:
    """2 枚のサムネイルで、輝度差が level を超えた画素の割合(%)。"""
    d = ImageChops.difference(a, b).point(lambda v: 255 if v > level else 0).tobytes()
    return 100.0 * sum(1 for v in d if v) / len(d)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def crop_frac(img: Image.Image, crop: tuple[float, float, float, float] | None) -> Image.Image:
    if not crop:
        return img
    x, y, w, h = crop
    W, H = img.size
    return img.crop((int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)))


def fmt_ts(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--interval", type=float, default=2.0, help="フレーム抽出間隔(秒) 既定 2")
    ap.add_argument("--min-change", type=float, default=0.2,
                    help="新スライドと判定する変化画素の割合(%%) 既定 0.2。拾いすぎ→上げる / 取りこぼし→下げる")
    ap.add_argument("--crop", type=str, default=None,
                    help="ハッシュ計算に使う領域 x,y,w,h (0-1 の割合)。保存画像はクロップしない")
    ap.add_argument("--width", type=int, default=1600, help="保存画像の横幅 px 既定 1600")
    args = ap.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ffmpeg が見つかりません。インストールして PATH を通してください。", file=sys.stderr)
        return 1
    if not args.video.exists():
        print(f"動画がありません: {args.video}", file=sys.stderr)
        return 1
    crop = tuple(float(v) for v in args.crop.split(",")) if args.crop else None
    args.outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(args.video),
            "-vf", f"fps=1/{args.interval},scale={args.width}:-2",
            "-q:v", "3", str(Path(tmp) / "f_%06d.jpg"),
        ]
        subprocess.run(cmd, check=True)
        frames = sorted(Path(tmp).glob("f_*.jpg"))
        if not frames:
            print("フレームを取り出せませんでした。", file=sys.stderr)
            return 1

        kept: list[tuple[Path, float]] = []
        last: Image.Image | None = None
        for i, f in enumerate(frames):
            with Image.open(f) as im:
                t = thumb(crop_frac(im, crop))
            if last is None or changed_pct(t, last) > args.min_change:
                ts = i * args.interval
                name = f"slide_{len(kept) + 1:03d}_{fmt_ts(ts)}.jpg"
                shutil.copy(f, args.outdir / name)
                kept.append((args.outdir / name, ts))
                last = t

    stem = args.video.stem
    lines = [
        "---",
        "type: slide-index",
        f"source_video: \"{args.video.name}\"",
        f"slides: {len(kept)}",
        "---",
        f"# {stem} スライド一覧",
        "",
        f"抽出条件: interval={args.interval}s / min-change={args.min_change}%" + (f" / crop={args.crop}" if args.crop else ""),
        "",
    ]
    for p, ts in kept:
        lines += [f"## {p.stem.split('_')[1]} — {fmt_ts(ts)}", f"![[{p.name}]]", ""]
    (args.outdir / "index.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"{len(frames)} フレーム中 {len(kept)} 枚をスライドとして保存 → {args.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
