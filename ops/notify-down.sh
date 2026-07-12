#!/usr/bin/env bash
# aiwp-notify-down.service（OnFailure=）から呼ばれる死活通知スクリプト。
# 通知先は運用チャネル(Slack #aiwp-ops)のみ。ユーザーのLINEには絶対に出さない。
#
# 【なぜ自己検証するか】
# gateway(aiwp-hermes)は systemctl restart 時に SIGTERM を受けると意図的に exit 1 で
# 終了する（hermes issue #42675: 予期せぬシグナル後に systemd Restart で復帰させるため）。
# systemd は exit 1 を failed と見なし OnFailure= を発火するため、reapply_patches.sh の
# 正常な再起動のたびに「gatewayが落ちた」誤通知が出てオオカミ少年化していた。
# そこで unit の失敗判定は変えず（実障害の exit 1 を握り潰さない）、通知の直前に
# 「本当に落ちているか」を公開トンネル経由 health で自己検証する。Restart=always
# (RestartSec=5) で数秒後に復帰するため、猶予内に 405 が返れば restart 由来と判断し無通知。
# 復帰しなければ実障害として通知する。（教訓: 復旧確認は必ず公開トンネル経由で）
set -a; [ -f "$HOME/.hermes/.env" ] && . "$HOME/.hermes/.env"; set +a

HEALTH_URL="${AIWP_HEALTH_URL:-https://api.aiwpsapp.com/line/webhook}"
LOG="$HOME/.hermes/logs/notify-down.log"
ts() { date '+%Y-%m-%d %H:%M:%S%z'; }

# 復帰待ち: RestartSec=5 + 起動時間を見込み、最大 ~40s（2s間隔×20回）public health を確認。
# oneshot の TimeoutStartSec(既定90s)内に収める。405 = gateway が公開経路で生存。
code=""
alive=0
for i in $(seq 1 20); do
  code="$(curl -s -o /dev/null -m 8 -w '%{http_code}' "$HEALTH_URL" || true)"
  if [ "$code" = "405" ]; then alive=1; break; fi
  sleep 2
done

if [ "$alive" = "1" ]; then
  # restart 由来。通知は抑止し、監査用にローカルへ記録するのみ。
  echo "$(ts) OnFailure発火 → public health=405で復帰確認（restart由来と判断）→ 通知抑止 (try=$i)" >> "$LOG" 2>/dev/null || true
  exit 0
fi

# 猶予内に復帰せず = 実障害。運用チャネルへ通知する。
echo "$(ts) OnFailure発火 → public health 未復帰(code=${code:-none}, ~40s) → 実障害と判断し通知" >> "$LOG" 2>/dev/null || true
[ -z "${SLACK_OPS_WEBHOOK:-}" ] && exit 0
MSG="⚠️ AI Worker's Pass の gateway が停止し自動復旧に失敗しました（VPS: aiwp-hermes / 公開health ~40s 未復帰・code=${code:-none}）。確認してください。"
curl -sS -m 10 -X POST "$SLACK_OPS_WEBHOOK" -H "Content-Type: application/json" -d "{\"text\":\"${MSG}\"}" >/dev/null
