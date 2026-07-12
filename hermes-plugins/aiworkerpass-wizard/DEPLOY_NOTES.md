# AI Worker's Pass — デプロイ時の必須手順（VPS / hermes再インストール時に再適用）

このプラグイン（`aiworkerpass-wizard`）は Hermes のプラグイン機構でロードされるが、
**プラグイン外＝Hermes本体への小パッチが1点**ある。`uv tool upgrade hermes-agent` や
VPS への新規インストールで **site-packages が入れ替わると消える**ので、下記を再適用すること。

## ★再適用は自動化済み（2026-07-12）— 手作業でやらない

```bash
cd ~/aiwp
ops/scripts/reapply_patches.sh --upgrade   # uv tool upgrade→A-4/B-2再適用→検証→再起動→公開health
ops/scripts/reapply_patches.sh             # upgrade済みの環境に再適用だけしたい時
ops/scripts/reapply_patches.sh --check     # 適用状態の監査のみ（変更なし・cron向き）
```

- 冪等。A-4/B-2のアンカー検証・py_compile・plugin/hook symlink 確認・
  **公開トンネル経由health(405)** までワンコマンド。検証NGなら再起動せず exit 1。
- `uv tool upgrade hermes-agent` を**単体で叩くのは禁止**。必ず `--upgrade` 経由で。
  （B-2が外れたまま運用＝テナント間メモリ混在＝情報漏洩事故のため）
- 以下の A-4 節・B-2 節は仕組みの説明とスクリプト障害時の手動フォールバック。

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

---

# 本体パッチ B-2: テナント別メモリ分離（2026-07-12 実装）

- 対象: `tools/memory_tool.py` + `agent/agent_init.py`（hermes-agent==0.18.2）
- 適用: **`python3 ops/patches/patch_tenant_memory.py`**（冪等・アンカー検証・py_compile込み）
- 効果: gateway経由（platform+user_id あり）のagentは `memories/{sanitized_user_id}/` に
  メモリが閉じる。CLI/ownerセッションは従来どおり `memories/` 直下（互換）。
- background_review は `agent._memory_store` 共有参照のためスコープ自動継承。
- 既知の限界: `learning_mutations.py` / `learning_graph.py`（journey機能・CLI専用）は
  グローバルのまま。LINE利用者からは到達不能なので v1 対象外。
- **A-4 と同様、`uv tool upgrade` / 再インストールのたびに再適用必須**。
- VPS移行時のメモリ移行: 既存グローバル `memories/USER.md` には**複数利用者分が
  混在している可能性がある**（tenants には HEY=さとう と みーちゃん の2人が既存）。
  誰かのスコープへ移すのは誤りなので、**アーカイブ退避**とする:
  `mv ~/.hermes/memories/USER.md ~/.hermes/memories/USER.md.pre-b2.bak`
  （各利用者のメモリは以後の会話で各スコープに再蓄積される。旧内容が必要なら
  .bak を目視で仕分け）

# BANフラグ 第4層（2026-07-12 実装）

- Supabase: `banned boolean not null default false` **適用済み（2026-07-12・migration:
  add_banned_flag_to_tenants）**。再インストール時の再適用は不要（DB側に永続）。
- プラグイン `__init__.py`: `pre_gateway_dispatch` 冒頭で `tenant.banned` なら
  `{"action":"skip"}` — **ウィザードもLLMも走らない完全遮断・無応答**（TARO指示は
  pre_llm_call遮断だったが、dispatch層の方が上流でコストゼロのため改良）。
  pre_llm_call にも保険チェックあり。
- BAN操作: Supabase tenants の該当行 `banned=true`。解除は `false`。再起動不要。

# エスカレーション通知フック（2026-07-12 実装）

- 実体: リポジトリ `hermes-hooks/aiwp-escalation/`（HOOK.yaml + handler.py）
- 設置: `ln -s ~/aiwp/hermes-hooks/aiwp-escalation ~/.hermes/hooks/aiwp-escalation`
  （gateway/hooks.py の dir-hook 機構。本体パッチ不要）
- 動作: `agent:end` でLINE応答に「運営に伝え」等の文言を検知 → HEYのLINEへpush。
  ユーザー本人には何も送らない。同一ユーザー10分デデュープ。
- 必要env（`~/.hermes/.env`）: `AIWP_ESCALATION_LINE_USER`（HEYのLINE user_id＝
  Supabase tenants で name='さとう' の行の line_user_id。HEY本人確認済み 2026-07-12）。
  未設定なら無音で無効。フレーズは `AIWP_ESCALATION_PHRASES`（カンマ区切り）で上書き可。
- ★personaの system_prompt 側に「運営対応が必要な時は『運営に伝えます』と言う」旨の
  確定文言を入れておくこと（検知フレーズと対で機能する）。

# Slack Ops webhook（死活通知）

- 通知先: Slack **#aiwp-ops**（C0BGS54LUUS・2026-07-12新設）
- 手順: Slack App の Incoming Webhooks で #aiwp-ops 向けURLを発行 →
  VPS `~/.hermes/.env` に `SLACK_OPS_WEBHOOK=<URL>` 追加 → gateway再起動。
  既存の `aiwp-notify-down.service`（OnFailure）が拾う。設定までは無音。

## 未完タスク（次セッション以降・ハンドオフ参照）
- ~~テナント分離~~ ✅ 2026-07-12 実装（B-2。上記）
- ~~BANフラグ~~ ✅ 2026-07-12 実装（上記）
- ~~エスカレーション通知~~ ✅ 2026-07-12 実装（上記）
- Slack Ops webhook … #aiwp-ops作成済み。**webhook URL発行（HEY作業）+ VPS .env反映が残**
- VPSへの反映一式（SSH鍵受領後）: git pull → B-2パッチ適用 → hooks symlink →
  .env 2キー追加（SLACK_OPS_WEBHOOK / AIWP_ESCALATION_LINE_USER）→ メモリ移行 →
  gateway再起動 → **公開トンネル経由health確認**
- 外形監視（公開URLへの定期health）
