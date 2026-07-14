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
