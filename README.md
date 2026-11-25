# 北海道支部会 学会動画 → Obsidian

日本脳神経外科学会 北海道支部会の **学会動画** から、臨床と研究に使える「コンテキスト」を集めて
Obsidian（iCloud 上の保管庫）に蓄積するための道具一式。

> [!important] 取り扱い
> - 学会動画は演者の著作物で、患者画像を含む可能性がある → **個人学習用のみ**。
>   動画・画像・`out/` は `.gitignore` 済み。**このリポジトリは public なのでノート本体は入れない**（iCloud 側で管理）。
> - 学会発表は査読前の情報。論文・ガイドラインで裏取りしたものだけを臨床判断に使う。

---

## 全体の流れ（Step by step）

```
学会動画 ──process_video.py──▶ out/<動画名>/
                                 ├ slide_001_00m00s.jpg …  スライドが切り替わった瞬間の静止画
                                 ├ transcript.json         文字起こし（Whisper）
                                 └ timeline.md ★           スライド1枚ごとに、その間の発言をぶら下げたノート
                                        │
                                        ▼
                     Claude に渡して演題ノートを下書き → 自分で「解釈」「臨床 Pearl」を書く
                                        │
                                        ▼
                     iCloud の Obsidian 保管庫（neurosurgery-notes/）へ
```

### Step 0. 準備（初回のみ・自分の Mac で）
```bash
brew install ffmpeg
```
```bash
pip install pillow faster-whisper
```

### Step 1. 動画をまとめて処理
```bash
python scripts/process_video.py ~/Movies/北海道支部会/第XX回 out/第XX回
```
- フォルダを渡すと中の動画を全部処理する（1 本だけでも可）。
- **スライド抽出**：2 秒ごとに画面を見て、変化した画素が 0.2% 以上のときだけ保存（箇条書き 1 行の追加は拾い、圧縮ノイズは無視）。
- **文字起こし**：口頭説明と **質疑応答** はスライドに無い情報で、一番価値が高いコンテキスト。
  CPU の Mac だと medium モデルで動画の長さの 1〜2 倍の時間がかかる。急ぐときは `--model small`。
  一度起こした結果は `transcript.json` に保存され、再実行時は再利用される。
- 演者カメラの小窓が映る動画は `--crop 0,0,0.75,1`（左 75% だけでスライド判定）。
- スライドの拾いすぎ → `--min-change 0.5` / 取りこぼし → `--min-change 0.1`。
- セッション丸ごとの長い動画でも OK。timeline.md の座長紹介・質疑の流れから演題の区切りが分かるので、
  Claude に「演題ごとに分けて」と頼めばよい。

### Step 2. Claude に下書きさせる
`timeline.md`（と必要ならスライド画像数枚）を Claude に渡して：

> この timeline から演題ノートを作って。数値はスライドに書いてあるものだけ使い、
> 読めない・聞き取れない箇所は「要確認」と書くこと。質疑応答は必ず残して。
> 「自分の解釈」は関連ガイドライン・主要 RCT と一致/矛盾を指摘する形で下書きして。

**「自分の解釈」「臨床 Pearl」は必ず自分の言葉で書き直す** — ここが学習効果の本体。

### Step 3. iCloud の保管庫へ
Obsidian の iCloud 保管庫は Mac では次の場所にある：
```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<保管庫名>/
```
完成した演題ノートと、使うスライド画像だけをそこへ移す（全スライドを入れると iCloud 容量を圧迫する）。

---

## ファイル
```
scripts/
├── process_video.py   ★入口：動画（フォルダ）→ スライド + 文字起こし + timeline.md
├── extract_slides.py  スライド抽出だけ単独で使う場合
└── transcribe.py      文字起こしだけ単独で使う場合（専門用語ヒント NEURO_PROMPT を編集可）
vault/90_Templates/    演題ノート等のテンプレート（既存の neurosurgery-notes の形式に合わせて調整予定）
```
