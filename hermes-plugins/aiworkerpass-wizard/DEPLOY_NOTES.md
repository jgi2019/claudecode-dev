# AI Worker's Pass — デプロイ時の必須手順（VPS / hermes再インストール時に再適用）

このプラグイン（`aiworkerpass-wizard`）は Hermes のプラグイン機構でロードされるが、
**プラグイン外＝Hermes本体への小パッチが1点**ある。`uv tool upgrade hermes-agent` や
VPS への新規インストールで **site-packages が入れ替わると消える**ので、下記を再適用すること。

## 本体パッチ A-4: 学習通知の日本語化（Self-improvement review バブル）

- 対象: `<site-packages>/agent/background_review.py`
- 目的: LINE利用者に届く英語のシステムバブル `💾 Self-improvement review: {summary}` を
  日本語＋🧠 に置換（通知自体は残す＝「理解していってる」信号は core value）。
- プラグイン層からは `agent` も学習結果も取得できず（hookのkwargsに非公開・レビューはfork実行）
  再pushで代替できないため、本体パッチが唯一の実現手段。

### 変更箇所（ユーザーに届く callback 側のみ）

```python
# 変更前
                    _bg_cb(
                        f"💾 Self-improvement review: {summary}"
                    )
# 変更後
                    _bg_cb(
                        "🧠 あなたのことをもう少し理解しました😊"
                    )
```

※ 直前の `agent._safe_print(f"  💾 Self-improvement review: {summary}")`（コンソール/運用者向けログ）は
デバッグ用に**英語＋summaryのまま残す**（LINEには出ない）。

### VPSセットアップ（B-1）での自動適用スニペット例

```bash
SP=$(python3 -c "import agent, os; print(os.path.dirname(agent.__file__))")
python3 - "$SP/background_review.py" <<'PY'
import sys, io
p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()
old = '                    _bg_cb(\n                        f"💾 Self-improvement review: {summary}"\n                    )'
new = '                    _bg_cb(\n                        "🧠 あなたのことをもう少し理解しました😊"\n                    )'
if old in s:
    io.open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("A-4 patch applied")
elif "あなたのことをもう少し理解しました" in s:
    print("A-4 patch already present")
else:
    raise SystemExit("A-4 patch anchor NOT found — Hermes内部変更の可能性。手動確認せよ")
PY
```

適用後は `python3 -m py_compile "$SP/background_review.py"` で構文確認し、gateway再起動。

---

# VPS本番デプロイ構成（2026-07-12 移行完了）

Mac常駐（フォアグラウンド＋quick/named tunnel）から **AWS Lightsail 常駐** へ移行済み。
Macは撤収。以下がVPS本番の正本構成。

## インフラ
- **Lightsail**: インスタンス `aiwp-hermes` / 東京(ap-northeast-1) / Ubuntu 22.04 LTS / 2GB・2vCPU・60GB
- **静的IP**: `52.198.229.135`（`aiwp-static-ip`） / SSHユーザー `ubuntu`
- **公開URL**: `https://api.aiwpsapp.com/line/webhook`（Cloudflare named tunnel `aiwp-gateway` 経由）
- **gateway待受**: `localhost:8646`（hermesのLINEデフォルトポート `DEFAULT_WEBHOOK_PORT`）

## インストール（B-1）
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh                 # uv
uv tool install --python 3.11 --with aiohttp "hermes-agent==0.18.2"   # ★aiohttp必須(下記)
curl -sL -o /tmp/cf.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i /tmp/cf.deb
```
**★落とし穴1**: LINEアダプタは `aiohttp` を要求する（`check_requirements`）。`hermes-agent` 本体には含まれないので `--with aiohttp` 必須。無いと "Platform 'LINE' requirements not met" で adapter生成失敗・8646未listen。

## 配置ファイル（Mac→VPS転送。**secretはchatに出さずscp直送**）
- `~/.hermes/config.yaml`（正体固定=agent.system_prompt下地含む）, `auth.json`, `SOUL.md`
- `~/.hermes/.env` … **creds実体はここ**（config.yaml外）。必要キー（値は各自）:
  `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`, `LINE_ALLOW_ALL_USERS`,
  `LINE_PUBLIC_URL`, `LINE_HOME_CHANNEL`(★), `ANTHROPIC_API_KEY`,
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SLACK_OPS_WEBHOOK`(任意・死活通知先)
- `~/.cloudflared/`: `<tunnel-uuid>.json`(認証), `cert.pem`, `config.yml`(ingress: api.aiwpsapp.com→localhost:8646)
- プラグイン: `~/aiwp/hermes-plugins/aiworkerpass-wizard/` を `~/.hermes/plugins/aiworkerpass-wizard` にsymlink
- **A-4本体パッチ**（上記）を再適用

**★落とし穴2**: `LINE_HOME_CHANNEL` 未設定だと、初回メッセージ時に英語の
"📬 No home channel is set for Line…" がユーザーLINEに漏れる（gateway/run.py）。必ず設定して抑止。

## 常駐（systemd）
- `aiwp-hermes.service` … `hermes gateway run`・`Restart=always`・`enabled`。
  drop-in `onfailure.conf`: `OnFailure=aiwp-notify-down.service` + `StartLimitIntervalSec=300`/`Burst=5`
- `aiwp-cloudflared.service` … `cloudflared tunnel --config ~/.cloudflared/config.yml run aiwp-gateway`・`enabled`
- `aiwp-notify-down.service` … oneshot（OnFailure専用）→ `~/aiwp/ops/notify-down.sh`
  **死活通知は Slack(`SLACK_OPS_WEBHOOK`)へのみ**。ユーザーLINEには絶対送らない（未設定なら無音）
- cron `/etc/cron.d/aiwp-weekly-restart`: 週次(日4:00 JST)自動再起動（保険）

## カットオーバー手順（Mac→VPS・応答停止リスク帯）
1. VPSで hermes + cloudflared を起動（この時点でMacと2レプリカ＝無停止）
2. Mac側 `launchctl unload ~/Library/LaunchAgents/com.jgi.aiwp.cloudflared.plist` で停止
3. `curl -o/dev/null -w '%{http_code}' https://api.aiwpsapp.com/line/webhook` が **405** ならVPSが応答＝成功
4. Mac gateway停止（Ctrl+C）
※復旧確認は必ず公開トンネル経由（ローカルhealth誤診の教訓）

## 未完タスク（次セッション以降・ハンドオフ参照）
- テナント分離（`memories/{user_id}/USER.md`スコープ化・本体パッチ）… テスター2人目前に必須
- BANフラグ（Supabase `tenants.banned` + pre_llm_call遮断）
- エスカレーション通知（AIが「運営に伝えます」時のみHEYへpush）
- 外形監視（公開URLへの定期health）
