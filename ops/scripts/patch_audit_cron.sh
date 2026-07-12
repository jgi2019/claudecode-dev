#!/usr/bin/env bash
# 日次パッチ監査: reapply_patches.sh --check がNGなら #aiwp-ops へ通知（正常時は無音）
set -a; [ -f "$HOME/.hermes/.env" ] && . "$HOME/.hermes/.env"; set +a
OUT="$("$HOME/aiwp/ops/scripts/reapply_patches.sh" --check 2>&1)" && exit 0
[ -z "${SLACK_OPS_WEBHOOK:-}" ] && exit 1
TEXT="🩹 AIWP パッチ監査NG: 本体パッチ(A-4/B-2)またはsymlinkが外れています。reapply_patches.sh を実行してください。\n\`\`\`$(printf "%s" "$OUT" | tail -8 | sed "s/\"/\\\\\"/g")\`\`\`"
curl -sS -m 10 -X POST "$SLACK_OPS_WEBHOOK" -H "Content-Type: application/json" -d "{\"text\":\"${TEXT}\"}" >/dev/null
exit 1
