---
description: セッション起動検証 — 正本照合・fetch/FF pull・鉄の掟自己申告を1コマンドで実行
allowed-tools: Bash(git fetch:*), Bash(git pull --ff-only:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git log:*), Bash(shasum:*), Bash(pwd), Bash(ls:*)
---

# /pj — 起動検証コマンド

引数: $ARGUMENTS（PJラベル。例: `/pj オムロンNextWebUI` `/pj aiwp`。省略可）

以下を上から順に実行し、最後に結果を1つのチェックリストで報告せよ。

## 0. PJ特定（引数がある場合のみ）
- $ARGUMENTS が指定されたら、PJレジストリDB（Notion dd705d5de8fe4252a4c8036fb6a8a19a）で該当PJを引き、正位置・指示ファイル・状態を把握する。
- 以下を**自己宣言**する:
  「このセッションは **[PJ:$ARGUMENTS]**。#taro-jiroでは自PJ宛＋[PJ:ソロプレナーOS]（共通基盤）宛のみ読み、他PJ宛の指示は読み飛ばす」
- 以後このセッションのSlack投稿には必ず `[PJ:$ARGUMENTS]` 接頭辞を付ける。
- 引数なしの場合は本節をスキップし、従来どおり起動検証のみ行う（読み分け宣言はしない）。

## 1. 起動ディレクトリ検証
- `pwd` を実行。PJレジストリ（Notion「PJレジストリ」DB / CLAUDE.mdの最小参照一覧）に登録された正位置チェックアウト配下かを判定する。
- claudecode-dev の正位置は `~/Desktop/claudecode-dev/`。それ以外の場所で起動している場合は**警告を出し、正位置への移動を促す**（未登録の場所での作業は禁止）。

## 2. CLAUDE.md読込確認（鉄の掟の自己申告）
- 鉄の掟5カ条（①JIROセッション常に1つ ②サブエージェント無名 ③モデルはギア ④次セッション指示文はTAROが書く ⑤承認ルール不変）を**読めているか自己申告**する。
- 読めていない（コンテキストに正本CLAUDE.mdがない）場合は、`~/Desktop/claudecode-dev/CLAUDE.md` をReadしてから続行する。
- 起動ディレクトリが `~/Desktop/claudecode-dev/` 以外なら「憲法層 ~/.claude/CLAUDE.md のみ読込の可能性が高い」旨を明示する。

## 3. 正本ハッシュ照合
- `git -C ~/Desktop/claudecode-dev fetch origin` を実行。
- ローカルとリモートの CLAUDE.md を照合:
  - `git -C ~/Desktop/claudecode-dev rev-parse HEAD` と `git -C ~/Desktop/claudecode-dev rev-parse origin/main`
  - 差分があれば `git -C ~/Desktop/claudecode-dev log --oneline HEAD..origin/main` で遅れコミットを表示
- **ワーキングツリーのCLAUDE.mdがHEADと違う場合**（未コミット編集）はその旨も報告する: `git -C ~/Desktop/claudecode-dev status --short CLAUDE.md`

## 4. fast-forward pull
- 遅れがある場合のみ `git -C ~/Desktop/claudecode-dev pull --ff-only origin main` を実行。
- FF不可（ローカルに未pushコミットがあり分岐している）場合は**pullせず状況を報告して指示を待つ**。

## 5. 作業対象リポの同期（claudecode-dev以外で作業する場合）
- 作業対象がPJレジストリの他リポ（jgi-brain / jgi-sites 等）の場合、そのリポでも同様に fetch → FF pull を行う。
- ⚠️ jgi-sites は push=本番デプロイ発火。pullは安全だがpush時は必ず承認を取ること。

## 6. 完了報告（チェックリスト形式）
```
✅/❌ 起動ディレクトリ: <pwd> （正位置/未登録）
✅/❌ 鉄の掟: 読込済み・自己申告OK
✅/❌ 正本同期: HEAD=origin/main（または N コミット遅れ→FF pull実施）
✅/❌ CLAUDE.md未コミット差分: なし/あり
次アクション: <ハンドオフDB確認 → 作業開始 等>
```
