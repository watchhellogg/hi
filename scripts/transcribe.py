#!/usr/bin/env python3
"""学会動画の音声を文字起こしし、タイムスタンプ付き Markdown にする(任意ステップ)。

スライドだけでは分からない「演者の口頭説明」「質疑応答」がコンテキストとして一番価値が高いことが多い。
タイムスタンプは extract_slides.py のファイル名(slide_005_03m20s)と対応づけられる。

必要なもの: pip install faster-whisper  (GPU なしでも動くが medium で動画長の 1〜2 倍程度かかる)

例:
  python transcribe.py 演題03.mp4 out/演題03/transcript.md --model medium
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 専門用語の誤変換を減らすためのヒント。よく出る語を足していくと精度が上がる。
NEURO_PROMPT = (
    "脳神経外科学会 北海道支部会。くも膜下出血、破裂脳動脈瘤、未破裂脳動脈瘤、クリッピング、コイル塞栓術、"
    "フローダイバーター、脳動静脈奇形、硬膜動静脈瘻、もやもや病、STA-MCAバイパス、頸動脈内膜剥離術、CEA、CAS、"
    "血栓回収療法、主幹動脈閉塞、膠芽腫、髄膜腫、神経鞘腫、下垂体腺腫、経蝶形骨洞手術、慢性硬膜下血腫、"
    "中硬膜動脈塞栓術、水頭症、シャント、脊髄、頚椎症、てんかん、DBS、MMA、ICA、MCA、ACA、PCA、BA。"
)


def ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def transcribe_segments(video: Path, model_name: str = "medium", device: str = "auto") -> list[tuple[float, float, str]]:
    """[(開始秒, 終了秒, テキスト)] を返す。faster-whisper が無ければ ImportError。"""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device=device, compute_type="auto")
    segments, _ = model.transcribe(str(video), language="ja", initial_prompt=NEURO_PROMPT,
                                   vad_filter=True, beam_size=5)
    out = []
    for seg in segments:
        out.append((seg.start, seg.end, seg.text.strip()))
        print(f"[{ts(seg.start)}] {seg.text.strip()}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--model", default="medium", help="tiny/base/small/medium/large-v3 既定 medium")
    ap.add_argument("--device", default="auto", help="auto/cpu/cuda")
    args = ap.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("pip install faster-whisper を実行してください。", file=sys.stderr)
        return 1

    model = WhisperModel(args.model, device=args.device, compute_type="auto")
    segments, info = model.transcribe(str(args.video), language="ja", initial_prompt=NEURO_PROMPT,
                                      vad_filter=True, beam_size=5)
    lines = ["---", "type: transcript", f"source_video: \"{args.video.name}\"", f"model: {args.model}", "---",
             f"# {args.video.stem} 文字起こし", "", "> [!warning] 自動文字起こし。薬剤名・数値・用語は必ずスライドで確認すること。", ""]
    for seg in segments:
        lines.append(f"**[{ts(seg.start)}]** {seg.text.strip()}")
        print(f"[{ts(seg.start)}] {seg.text.strip()}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
