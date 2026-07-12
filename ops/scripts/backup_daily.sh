#!/usr/bin/env bash
# AIWP 日次ローカルバックアップ（誤削除・誤migration対策の第1層）— VPS(aiwp-hermes)用
# - Supabase tenants を REST 経由で JSON ダンプ
# - ~/.hermes（memories/config/.env/auth/SOUL）を tar 退避
# - 14日ローテーション。失敗時のみ #aiwp-ops へ通知（正常時は無音）
# 注: VPS自体の消失には無力。オフサイト二層目は Lightsail 自動スナップショット
#     または Supabase Pro（HEY判断）で張る。
set -euo pipefail
set -a; [ -f "$HOME/.hermes/.env" ] && . "$HOME/.hermes/.env"; set +a
DEST="$HOME/backups/aiwp"
mkdir -p "$DEST"
TS="$(date +%Y%m%d)"

fail() {
  [ -n "${SLACK_OPS_WEBHOOK:-}" ] && curl -sS -m 10 -X POST "$SLACK_OPS_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"💾 AIWP 日次バックアップ失敗: $1（VPS: aiwp-hermes）\"}" >/dev/null || true
  exit 1
}

# 1) Supabase tenants ダンプ（service role・全列）
curl -sS -m 30 -f "${SUPABASE_URL}/rest/v1/tenants?select=*" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -o "$DEST/tenants-$TS.json" || fail "tenantsダンプ(REST)"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert isinstance(d,list) and len(d)>=1" \
  "$DEST/tenants-$TS.json" || fail "tenantsダンプが空/不正JSON"

# 2) ~/.hermes 退避（ログ・キャッシュ除外）
tar czf "$DEST/hermes-$TS.tgz" -C "$HOME" \
  --exclude=".hermes/logs" --exclude="*.log" --exclude="__pycache__" \
  .hermes || fail "hermes tar退避"

# 3) 14日ローテーション
find "$DEST" -name "tenants-*.json" -mtime +14 -delete
find "$DEST" -name "hermes-*.tgz" -mtime +14 -delete
echo "backup OK:"
ls -sh "$DEST/tenants-$TS.json" "$DEST/hermes-$TS.tgz"
