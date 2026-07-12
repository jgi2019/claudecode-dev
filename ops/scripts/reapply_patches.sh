#!/usr/bin/env bash
# AIWP 本体パッチ再適用（A-4 + B-2）＋ 適用確認 — VPS(aiwp-hermes)用
#
# hermes-agent は site-packages 直パッチ運用のため、`uv tool upgrade` /
# 再インストールのたびにパッチが消える。消えたまま運用すると:
#   - B-2消失 = テナント分離が外れ、利用者間でメモリ混在（情報漏洩事故）
#   - A-4消失 = 英語システムバブルが利用者LINEに漏れる
# よって upgrade 後は必ず本スクリプトを実行すること（DEPLOY_NOTES.md 参照）。
#
# 使い方（VPSの ~/aiwp リポジトリ内で実行）:
#   ops/scripts/reapply_patches.sh            # 再適用 → 検証 → gateway再起動 → 公開health確認
#   ops/scripts/reapply_patches.sh --check    # 適用状態の確認のみ（変更・再起動なし）
#   ops/scripts/reapply_patches.sh --upgrade  # uv tool upgrade hermes-agent → 再適用 → 再起動 → health
set -euo pipefail

MODE="apply"
case "${1:-}" in
  --check)   MODE="check" ;;
  --upgrade) MODE="upgrade" ;;
  "")        ;;
  *) echo "usage: $0 [--check|--upgrade]" >&2; exit 2 ;;
esac

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERMES_PY="$HOME/.local/share/uv/tools/hermes-agent/bin/python"
HEALTH_URL="https://api.aiwpsapp.com/line/webhook"
FAIL=0

note() { printf '%s\n' "$*"; }
bad()  { printf 'NG  %s\n' "$*"; FAIL=1; }
ok()   { printf 'OK  %s\n' "$*"; }

# ---------------------------------------------------------------- 0. upgrade
if [ "$MODE" = "upgrade" ]; then
  note "== uv tool upgrade hermes-agent =="
  uv tool upgrade hermes-agent
fi

# ---------------------------------------------------------------- 1. site-packages 検出
if [ ! -x "$HERMES_PY" ]; then
  echo "hermes-agent の uv tool 環境が見つからない: $HERMES_PY" >&2
  exit 1
fi
SP="$("$HERMES_PY" -c 'import agent, os; print(os.path.dirname(os.path.dirname(agent.__file__)))')"
note "site-packages: $SP"

# ---------------------------------------------------------------- 2. A-4（学習通知の日本語化）
apply_a4() {
  "$HERMES_PY" - "$SP/agent/background_review.py" <<'PY'
import sys, io
p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()
old = '                    _bg_cb(\n                        f"\U0001f4be Self-improvement review: {summary}"\n                    )'
new = '                    _bg_cb(\n                        "\U0001f9e0 あなたのことをもう少し理解しました\U0001f60a"\n                    )'
if "あなたのことをもう少し理解しました" in s:
    print("  A-4: already applied")
elif old in s:
    io.open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("  A-4: applied")
else:
    raise SystemExit("  A-4: anchor NOT found — Hermes内部変更の可能性。手動確認せよ")
PY
}

check_a4() {
  if grep -q "あなたのことをもう少し理解しました" "$SP/agent/background_review.py"; then
    ok "A-4 学習通知の日本語化 (background_review.py)"
  else
    bad "A-4 未適用: 英語バブルが利用者LINEに漏れる状態"
  fi
}

# ---------------------------------------------------------------- 3. B-2（テナント別メモリ分離）
check_b2() {
  local miss=0
  grep -q "def sanitize_scope" "$SP/tools/memory_tool.py" || miss=1
  grep -q "テナント分離 B-2" "$SP/agent/agent_init.py" || miss=1
  if [ "$miss" = 0 ]; then
    ok "B-2 テナント別メモリ分離 (memory_tool.py / agent_init.py)"
  else
    bad "B-2 未適用: テナント分離が外れている＝メモリ混在（情報漏洩）状態"
  fi
}

if [ "$MODE" = "check" ]; then
  note "== 適用状態チェック（変更なし） =="
  check_a4
  check_b2
else
  note "== A-4 適用 =="
  apply_a4
  note "== B-2 適用 =="
  HERMES_SP="$SP" python3 "$REPO_ROOT/ops/patches/patch_tenant_memory.py"
  note "== 適用後検証 =="
  check_a4
  check_b2
  "$HERMES_PY" -m py_compile "$SP/agent/background_review.py" \
    && ok "py_compile (background_review.py)" || bad "py_compile 失敗 (background_review.py)"
fi

# ---------------------------------------------------------------- 4. プラグイン/フックの symlink
[ -e "$HOME/.hermes/plugins/aiworkerpass-wizard" ] \
  && ok "plugin symlink (aiworkerpass-wizard)" \
  || bad "plugin symlink 消失: ~/.hermes/plugins/aiworkerpass-wizard"
[ -e "$HOME/.hermes/hooks/aiwp-escalation" ] \
  && ok "hook symlink (aiwp-escalation)" \
  || bad "hook symlink 消失: ~/.hermes/hooks/aiwp-escalation（エスカレ通知が無効化）"

if [ "$FAIL" != 0 ]; then
  echo "*** 検証NGあり。gateway再起動はスキップ。上のNGを解消して再実行せよ ***" >&2
  exit 1
fi

if [ "$MODE" = "check" ]; then
  note "チェック完了（全て適用済み）"
  exit 0
fi

# ---------------------------------------------------------------- 5. gateway 再起動 + 公開health
if command -v systemctl >/dev/null 2>&1; then
  note "== gateway 再起動 =="
  sudo systemctl restart aiwp-hermes
else
  note "systemd なし（開発機）: gateway再起動はスキップ"
fi

note "== 公開トンネル経由 health（教訓: ローカルhealthで済ませない） =="
for i in $(seq 1 12); do
  CODE="$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$HEALTH_URL" || true)"
  if [ "$CODE" = "405" ]; then
    ok "公開health $HEALTH_URL → 405（POST専用が生存）"
    note "パッチ再適用 完了"
    exit 0
  fi
  note "  health=$CODE 待機中 ($i/12)…"
  sleep 5
done
bad "公開health が 405 にならない（最終=$CODE）。トンネル/gatewayを調査せよ"
exit 1
