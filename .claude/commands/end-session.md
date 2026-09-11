# /end-session

JIRO（Claude Code）の終了手順。成果物・実行状態・handoff・通知を別々に検証し、途中失敗を「完了」に見せない。
共通契約は `jgi2019/jgi-brain/foundation/WORKFLOW.md`、本文テンプレートは `.claude/templates/aios-handoff-v0.2.yaml` を使う。

## 0. 終了前の境界確認

- 開始カードの `project_id` `session_id` `operation_id` `approval.scope` `read_versions` を引き継ぐ。
- 開始カードがない場合は、実績から勝手に補完せず、不明値を `unknown` として明示する。
- 新しい外部書込みが許可範囲外なら実行せず、未完ステップとして残す。
- 共通基盤Draftの存在だけを根拠に、既存ルールの採用・切替を宣言しない。

## 1. 成果物を保存・検証

1. 成果物を、その情報種別で指定された正本へ保存する。
2. 保存後に再取得し、URL・版・本文の要点が一致したものだけを `outputs[].verified: true` とする。
3. 保存失敗・成否不明・未実行を区別する。成否不明なら同じ `operation_id` で既存結果を照合してから再試行する。
4. commit、push、デプロイ、Notion、Slackは別ステップとして記録する。前段成功を後段成功とみなさない。

## 2. Notion handoff

- 保存先: 既存ハンドオフDB `collection://27e1a509-0fb5-4a07-824e-799985d70a3f`
- 1トピック1エントリ。DBプロパティの既存select値は変更・追加しない。
- 本文冒頭に `.claude/templates/aios-handoff-v0.2.yaml` の全フィールドを置く。
- `project_id` はPJレジストリ行のpage ID、`handoff_id` は作成したhandoffページIDを記録する。
- `execution.status` は次のいずれか:
  - `succeeded`: 許可範囲内の全ステップを検証済み
  - `partial`: 一部成功し、未完・失敗・成否不明が残る
  - `failed`: 目的を達成できず、成功成果物もない
  - `unknown`: 外部結果を照合できず、再実行すべきでない
- `failed_steps` は現在の未完だけ、`attempt_log` は過去の全試行を残す。
- 模擬出力は必ず `execution.simulation: true`。実行事実や承認事実と混ぜない。

### 既存DBプロパティ

- タイトル: トピック要約
- v: 同トピックの連番
- ステータス: 🟡着手待ち / 🔵進行中 / 🟢引き継ぎ済み
- トラック: 🔧インフラ / 🛠️アプリ開発 / 📣ブランディング / 🎯流入・案件 / 📝コンテンツ / 🤝パートナー
- プロジェクト: 既存選択肢から選ぶ。新設が必要なら本文に候補を残し、DB構造は変えない。
- 作成日、次アクション

### 本文（YAMLの後）

```markdown
# [トピック名] - [日付]
## 決まったこと
## 議論の経緯
## 未解決・保留事項
## 関連する正本URL
```

保存後、handoffページを再取得し、必須キー・値・URLを照合する。

## 3. 記事ドラフト（該当時のみ）

- JIRO担当: Base44・実装・デバッグ・インフラ・MCP構築など、手を動かしたセッション。
- TARO担当: 壁打ち・事業設計・市場整理など、考えたセッション。
- 作成前にnote記事DB `collection://5d35e889-018e-4405-99bb-1549059dea61` を同トピックで検索し、既存なら追記またはスキップする。
- 純粋な確認・接続試験・軽微な保守は、記事価値がなければ作らない。
- 作る場合もステータスは必ず 📝下書き。公開はHEYの判断。
- 記事作成の成功・失敗はhandoffの `execution` に独立したステップとして記録する。

## 4. 次セッション用の再開情報

次のAgentが会話履歴なしで再開できるよう、以下をhandoffへ残す。

- 具体的な次アクションとowner
- 未完ステップ
- 再試行前に照合すべき `operation_id`
- 参照すべき正本URLと版
- 必要な環境情報。ただし秘密情報は書かない

JIROの次セッション指示文そのものは、既存の鉄の掟どおりTAROが作る。JIROは再開に必要な事実をhandoffへ提供する。

## 5. Slack通知

Slack `#taro-jiro`（Channel ID: `C0BGKGN721X`）へ、許可された場合のみ投稿する。

通知本文には必ず以下を含める。

- `[PJ:xxx]`
- `operation_id`
- 結果: succeeded / partial / failed / unknown
- 成果物・handoffの正本URL
- 未完事項と次のowner

送信成功後、`execution.notification_receipts` に次を記録する。

```yaml
- channel: "C0BGKGN721X"
  message_id: "<Slack ts>"
  permalink: "<message permalink>"
  operation_id: "<same operation id>"
  sent_at: "<ISO 8601 with timezone>"
```

### 通知失敗時

- 成果物保存済み・通知未達が確定: 保存をやり直さず、同じ `operation_id` で通知だけ再試行。
- 到達したか不明: 受信側を `operation_id` で照合。照合不能なら自動再送せず `unknown` として引き継ぐ。
- すべて成功していない限り「完了」と書かない。

## 6. 終了カード

```yaml
project_id: "<id>"
session_id: "<id>"
operation_id: "<id>"
status: "<succeeded|partial|failed|unknown>"
verified_outputs:
  - "<URL>"
handoff_url: "<URL or none>"
notification_receipts: []
failed_steps: []
next_action:
  owner: "<owner>"
  action: "<specific action>"
```

## 品質チェック

- 次のAgentが「何を、なぜ、どの版で、どこから再開するか」を判断できるか。
- 保存した事実と、予定・提案・模擬を混同していないか。
- 既存成果物を再保存していないか。
- 外部通知の到達を、送信要求の成功だけで断定していないか。
- 秘密情報・個人情報をhandoffやSlackへ含めていないか。
