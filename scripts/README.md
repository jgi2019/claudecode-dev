# scripts/ — 運用スクリプト資産

ルーティン候補のスクリプト置き場。VPSでは `~/aiwp/scripts/` に配置（scp同期）、正本は本リポ。
各スクリプトは引数・環境変数・出力先を以下に明記する。3回以上手動実行したら Skills 化を検討する。

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
