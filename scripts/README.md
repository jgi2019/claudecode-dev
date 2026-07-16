# scripts/ — 運用スクリプト資産

ルーティン候補のスクリプト置き場。VPSでは `~/aiwp/scripts/` に配置（scp同期）、正本は本リポ。
各スクリプトは引数・環境変数・出力先を以下に明記する。3回以上手動実行したら Skills 化を検討する。

## faq_batch.py
SHERPA FAQ候補の夜間バッチ生成。Stage1で Perplexity Sonar が課題ごとに一次情報（解決手法・ツール・出典URL）を集め、
Stage2で Claude が FAQ（question/answer）に整形して品質スコアを付ける。数百件を回す前提の2段パイプライン。

- 実行:
  ```bash
  python3 scripts/faq_batch.py --outdir ~/Desktop/faq_candidates --dry-run   # APIを叩かず対象件数のみ
  python3 scripts/faq_batch.py --outdir ~/Desktop/faq_candidates --limit 5   # 先頭5件で試走
  python3 scripts/faq_batch.py --outdir ~/Desktop/faq_candidates             # 全件
  ```
- 引数: `--outdir`（既定 `~/Desktop/faq_candidates`）/ `--limit`（0=全件）/ `--workers`（既定4）/
  `--model`（`haiku`|`sonnet`|`opus`、既定 haiku）/ `--dry-run`
- 必要env: `PERPLEXITY_API_KEY`, `ANTHROPIC_API_KEY`（`~/.hermes/.env` から自動読込。値はログに出さない）
- 入力: `<outdir>/_input_issues.json`（Notion課題DBから抽出した配列）
- 出力: `<outdir>/stage1/<id>.json`（Sonar生結果）/ `<outdir>/stage2/<id>.json`（FAQ 1件）/
  `<outdir>/faq_candidates.json`（最終成果物）
- 安全策: **レジューム可**。1件1ファイルで完了済みをファイル存在で判定しスキップするため、途中で落ちても
  再実行でAPI費用を二重に払わない。本番書き込みは一切なし（ローカル出力のみ）。
- コスト特性（2026-07-15実測）: Sonar はリクエスト固定手数料 $5/1000req が支配的で、コストの約8割。
  **トークン量ではなく「何件叩くか」でほぼ決まる**ため、プロンプト短縮等の節約策は効かない。件数で絞ること。

## regen_system_prompts.py
既存オンボ完了テナントの `tenants.system_prompt` を、現行 `wizard.build_system_prompt` で再生成・更新する。
persona（wizard.py の静的文言）を変更した後、既存テナントへ反映するために使う（新規オンボは自動反映のため対象外）。

- 実行（VPS）:
  ```bash
  set -a; . ~/.hermes/.env; set +a
  python3 ~/aiwp/scripts/regen_system_prompts.py           # ドライラン（差分のみ・無変更）
  python3 ~/aiwp/scripts/regen_system_prompts.py --apply   # 実更新
  ```
- 必要env: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`（`~/.hermes/.env`）
- 出力: `--apply` 時、更新前 system_prompt を `~/aiwp/scripts/backup_system_prompts_<epoch>.json` に退避
- 安全策: 生成物に目印（現行persona）が無ければスキップ、既存と同一なら無更新。冪等。
- 実行後: `sudo systemctl restart aiwp-hermes` は不要（system_prompt はDB読込のため次ターンから反映）。

## check_sites.sh
静的LP群(jgi-sites: oms/ai/dev/lab.udlr.jp)の死活監視。**HTTPコードに加えbodyの実バイト数を検査**し、
「200 OK だが中身が空/痩せ細り」を検知する。cronで定期実行する前提。

- 実行:
  ```bash
  ~/aiwp/scripts/check_sites.sh --dry-run   # Slackに投げず結果を標準出力（動作確認用）
  ~/aiwp/scripts/check_sites.sh             # 本番（異常時のみSlack通知）
  ```
- cron例（10分毎）: `*/10 * * * * $HOME/aiwp/scripts/check_sites.sh >/dev/null 2>&1`
- 必要env: `SLACK_OPS_WEBHOOK`（`~/.hermes/.env`）。未設定なら通知せずログのみ。
- 出力: ログ `~/.hermes/logs/check-sites.log` / 状態 `~/.hermes/state/check-sites/`
  （env `CHECK_SITES_LOG` `CHECK_SITES_STATE_DIR` で変更可。テスト時の隔離に使う）
- 終了コード: 全件正常=0 / 1件でも異常=1
- 安全策: 読み取り専用(curl GETのみ)。状態遷移時のみ通知するため障害中の連投や正常時の常時通知はしない。
  復旧時は復旧通知を出す。
- **監視対象・下限バイト・必須文字列はスクリプト内 `TARGETS` に定義**。下限は2026-07-15実測値の約半分。
  必須文字列（2026-07-16追加）は「サイズは足りるが別コンテンツが返る」誤ルーティング等を検知する。
  空白を含まない1トークンで書く。LPを作り替えたら下限・文字列の両方を更新すること（さもないと誤報になる）。

### なぜコード監視では不十分か（2026-07-15 の教訓）
ai/dev.udlr.jp が「HTTP 200 / body 0バイト」で約3ヶ月放置されていた。Vercelは0バイトのファイルを
正常に配信するため、コードだけ見る監視は 200 OK=正常 と判定してすり抜ける。oms.udlr.jp の6日間沈黙
(2026-07-14)も「配信は生きているが中身が出ない」同型。**「疎通している」と「中身が出ている」は別物**。
なお `ops/notify-down.sh` はHermes gateway専用(期待値405)でLP群は見ていない。両者を混同しないこと。

## hermes_snapshot.py
テナント別 `tenants.system_prompt`（AIWPの売り「学習データ継続保証」の実体＝知の資本）を日次でgit退避する。
7/14設計議論で確定した防御策。出力先は本リポ `ops/snapshots/hermes/system_prompts.json`（履歴はgitが持つ）。

- 実行（VPS・cron 日次）:
  ```bash
  python3 ~/aiwp/scripts/hermes_snapshot.py --repo ~/aiwp/claudecode-dev --commit --push
  ```
- 引数: `--repo`（スナップショット置き場のgitリポ。既定=スクリプトのあるリポ）/ `--commit` / `--push` / `--force`
- 必要env: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`（`~/.hermes/.env` から自動読込。値はログに出さない）
- 安全策: テナント数が前回より減ったら上書きせず異常終了（本体DB異常の日にバックアップまで潰す事故を防止。意図的な削除時のみ `--force`）。差分がなければcommitしない（冪等）。
- 注意: スナップショットにはテナントのニックネームとオンボ回答（軽度の個人情報）が含まれる。**privateリポ以外に置かない・ログに全文を出さない**。
