#!/usr/bin/env python3
"""スマホで撮った発表スライド写真を、撮影時刻の間隔から「演題ごと」に自動で束ねる。

仕組み:
  1. 写真の EXIF 撮影日時(なければファイル更新日時)で並べる
  2. 前の写真から --gap 分以上空いたら別の演題グループとみなす
  3. 連写した同一スライド(知覚ハッシュがほぼ同じ)は 1 枚に間引く
  4. group_01_0915/ のようにコピー(元写真は動かさない)し、各 index.md を出力

※ 演題の切り替わりが短い学会では gap を小さく(3〜5 分)。
  プログラム(演題表)の写真を撮っておくと後で演題名と突き合わせやすい。

例:
  python organize_photos.py ~/Pictures/北海道支部会2026 out/photos --gap 6
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_slides import dhash, hamming  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
EXIF_DATETIME_ORIGINAL = 36867
EXIF_DATETIME = 306


def shot_time(p: Path) -> datetime:
    try:
        with Image.open(p) as im:
            exif = im.getexif()
            raw = exif.get_ifd(0x8769).get(EXIF_DATETIME_ORIGINAL) or exif.get(EXIF_DATETIME)
            if raw:
                return datetime.strptime(str(raw).strip("\x00"), "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.fromtimestamp(p.stat().st_mtime)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="写真フォルダ")
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--gap", type=float, default=6.0, help="別演題とみなす撮影間隔(分) 既定 6")
    ap.add_argument("--dup", type=int, default=12, help="同一スライドとみなすハミング距離 既定 12")
    args = ap.parse_args()

    photos = sorted((p for p in args.src.rglob("*") if p.suffix.lower() in EXTS), key=shot_time)
    if not photos:
        print("写真が見つかりません。(HEIC は pip install pillow-heif が必要な場合があります)", file=sys.stderr)
        return 1

    groups: list[list[tuple[Path, datetime]]] = []
    prev_t: datetime | None = None
    for p in photos:
        t = shot_time(p)
        if prev_t is None or (t - prev_t).total_seconds() > args.gap * 60:
            groups.append([])
        groups[-1].append((p, t))
        prev_t = t

    args.outdir.mkdir(parents=True, exist_ok=True)
    total_kept = 0
    for gi, g in enumerate(groups, 1):
        gdir = args.outdir / f"group_{gi:02d}_{g[0][1]:%m%d_%H%M}"
        gdir.mkdir(exist_ok=True)
        last_h = None
        kept = []
        for p, t in g:
            try:
                with Image.open(p) as im:
                    h = dhash(ImageOps.exif_transpose(im))
            except Exception:
                h = None
            if h is not None and last_h is not None and hamming(h, last_h) <= args.dup:
                continue
            last_h = h
            dst = gdir / f"{t:%H%M%S}_{p.name}"
            shutil.copy2(p, dst)
            kept.append((dst, t))
        total_kept += len(kept)
        md = ["---", "type: photo-group", f"start: {g[0][1]:%Y-%m-%d %H:%M}", f"end: {g[-1][1]:%H:%M}",
              f"photos: {len(kept)}", "演題: ", "---", f"# Group {gi:02d} ({g[0][1]:%H:%M}–{g[-1][1]:%H:%M})", ""]
        for dst, t in kept:
            md += [f"### {t:%H:%M:%S}", f"![[{dst.name}]]", ""]
        (gdir / "index.md").write_text("\n".join(md), encoding="utf-8")
        print(f"{gdir.name}: {len(g)} 枚 → {len(kept)} 枚")

    print(f"合計 {len(photos)} 枚 → {len(groups)} グループ / {total_kept} 枚 → {args.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
