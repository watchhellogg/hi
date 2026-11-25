#!/usr/bin/env python3
"""学会動画 → 「スライド画像 + その間に話された内容」を時系列に並べた timeline.md を作る(メインの入口)。

1 本の動画でも、フォルダ(中の動画をまとめて処理)でも可。動画ごとに次を出力する:

  out/<動画名>/
    slide_001_00m00s.jpg ...   スライドが切り替わった瞬間の静止画
    index.md                   スライド一覧
    transcript.json            文字起こしキャッシュ(再実行時は再利用)
    timeline.md                ★ スライド 1 枚ごとに、その間の発言をぶら下げたノート
                                 → これを Claude に渡して演題ノートを下書きさせる

セッション丸ごとの長い動画(複数演題)でも、timeline.md の流れ(座長の紹介・質疑)から
演題の区切りが読み取れるので、そのまま Claude に「演題ごとに分けて」と頼めばよい。

例:
  python process_video.py 動画/第XX回 out/第XX回                # フォルダ内の全動画
  python process_video.py 動画/演題03.mp4 out/第XX回 --crop 0,0,0.75,1
  python process_video.py 動画/演題03.mp4 out/第XX回 --no-transcribe  # スライドだけ
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_slides import extract, fmt_ts, write_index  # noqa: E402
from transcribe import transcribe_segments  # noqa: E402

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}


def build_timeline(video: Path, slides: list[tuple[Path, float]],
                   segs: list[tuple[float, float, str]] | None) -> str:
    lines = ["---", "type: video-timeline", f"source_video: \"{video.name}\"", f"slides: {len(slides)}",
             f"transcript: {'yes' if segs else 'no'}", "---", f"# {video.stem} タイムライン", ""]
    if segs:
        lines += ["> [!warning] 自動文字起こし。薬剤名・数値・固有名詞は必ずスライド画像で確認すること。", ""]
        # スライドより前の発言(座長の紹介など)
        first = slides[0][1] if slides else float("inf")
        pre = [s for s in segs if s[0] < first]
        if pre:
            lines += ["## 冒頭", *[f"- [{fmt_ts(a)}] {t}" for a, _, t in pre], ""]
    for i, (p, start) in enumerate(slides):
        end = slides[i + 1][1] if i + 1 < len(slides) else float("inf")
        lines += [f"## {i + 1:03d} — {fmt_ts(start)}", f"![[{p.name}]]", ""]
        if segs:
            said = [f"- [{fmt_ts(a)}] {t}" for a, _, t in segs if start <= a < end]
            lines += (said or ["- (発言なし)"]) + [""]
    return "\n".join(lines)


def process(video: Path, outroot: Path, args) -> None:
    outdir = outroot / video.stem
    print(f"\n=== {video.name} ===")
    crop = tuple(float(v) for v in args.crop.split(",")) if args.crop else None
    slides, n = extract(video, outdir, args.interval, args.min_change, crop)
    write_index(video, outdir, slides, f"interval={args.interval}s / min-change={args.min_change}%")
    print(f"スライド: {n} フレーム中 {len(slides)} 枚")

    segs = None
    cache = outdir / "transcript.json"
    if not args.no_transcribe:
        if cache.exists():
            segs = [tuple(s) for s in json.loads(cache.read_text(encoding="utf-8"))]
            print(f"文字起こし: キャッシュを使用 ({len(segs)} 区間)")
        else:
            try:
                segs = transcribe_segments(video, args.model, args.device)
                cache.write_text(json.dumps(segs, ensure_ascii=False, indent=0), encoding="utf-8")
            except ImportError:
                print("faster-whisper 未インストールのため文字起こしは省略 (pip install faster-whisper)")

    (outdir / "timeline.md").write_text(build_timeline(video, slides, segs), encoding="utf-8")
    print(f"→ {outdir / 'timeline.md'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="動画ファイル または 動画フォルダ")
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--interval", type=float, default=2.0, help="フレーム抽出間隔(秒) 既定 2")
    ap.add_argument("--min-change", type=float, default=0.2, help="新スライド判定の変化画素割合(%%) 既定 0.2")
    ap.add_argument("--crop", default=None, help="スライド判定に使う領域 x,y,w,h (0-1)。演者カメラの小窓を除く")
    ap.add_argument("--model", default="medium", help="Whisper モデル 既定 medium")
    ap.add_argument("--device", default="auto", help="auto/cpu/cuda")
    ap.add_argument("--no-transcribe", action="store_true", help="文字起こしをしない")
    args = ap.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ffmpeg が見つかりません。", file=sys.stderr)
        return 1
    videos = ([args.src] if args.src.is_file()
              else sorted(p for p in args.src.rglob("*") if p.suffix.lower() in VIDEO_EXTS))
    if not videos:
        print(f"動画が見つかりません: {args.src}", file=sys.stderr)
        return 1
    for v in videos:
        process(v, args.outdir, args)
    print(f"\n完了: {len(videos)} 本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
