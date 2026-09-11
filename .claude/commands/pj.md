---
description: セッション起動検証 — 正本照合・fetch/FF pull・鉄の掟自己申告を1コマンドで実行
allowed-tools: Bash(git fetch:*), Bash(git pull --ff-only:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git remote get-url:*), Bash(git log:*), Bash(shasum:*), Bash(pwd), Bash(ls:*)
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

## 1. 実行環境とリポジトリ同一性の検証
- `pwd` と `git remote get-url origin` を実行する。
- Mac等の常設環境では、PJレジストリに登録された正位置（claudecode-devは `~/Desktop/claudecode-dev/`）を使う。別の常設checkoutは未登録として止める。
- Claude Code on the web等、サービスが作る一時的なリモート実行環境ではパス一致を要求しない。代わりに次の全条件で同一性を確認する。
  1. `origin` がPJレジストリで指定されたGitHub repoと一致する。
  2. 対象commit/refをfetchし、`git rev-parse HEAD` で実際のSHAを記録する。
  3. 作業ツリーがcleanである。
- 開始カードへ `execution_environment: local_registered | remote_ephemeral`、実パス、origin、HEAD SHAを記録する。
- リポジトリ不一致・origin不明・意図しない常設checkoutの場合は作業を止める。

## 2. CLAUDE.md読込確認（鉄の掟の自己申告）
- 鉄の掟5カ条（①JIROセッション常に1つ ②サブエージェント無名 ③モデルはギア ④次セッション指示文はTAROが書く ⑤承認ルール不変）を**読めているか自己申告**する。
- 読めていない場合、常設環境では `~/Desktop/claudecode-dev/CLAUDE.md`、リモート一時環境では同一性を確認したcheckout内の `CLAUDE.md` をReadしてから続行する。
- パスの違いだけで未登録と断定せず、前節の `execution_environment` とorigin/HEADによる検証結果を明示する。

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

## 6. AIOS開始契約への接続
- 同期確認後、`.claude/commands/start-session.md` の手順を続けて実行する。
- PJレジストリで取得した行のpage IDを `project_id` とする。親ページIDやDB IDで代用しない。
- 採用済みAgent Briefのcommitが未指定の場合、Draftを現行ルールとして適用せず、既存CLAUDE.mdを維持する。
- 開始カードに `project_id` `session_id` `operation_id` `read_versions` `approval.scope` を表示してから作業へ入る。

## 7. 完了報告（チェックリスト形式）
```
✅/❌ 実行環境: <local_registered|remote_ephemeral> / <pwd>
✅/❌ リポジトリ同一性: origin=<URL> / HEAD=<SHA>
✅/❌ 鉄の掟: 読込済み・自己申告OK
✅/❌ 正本同期: HEAD=origin/main（または N コミット遅れ→FF pull実施）
✅/❌ CLAUDE.md未コミット差分: なし/あり
✅/❌ AIOS開始カード: project_id・operation_id・参照版・許可範囲を記録
次アクション: <最新handoffの具体的な再開地点 または HEYへの確認事項>
```
