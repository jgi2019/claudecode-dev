#!/usr/bin/env bash
# 静的LP群(jgi-sites: oms/ai/dev/lab.udlr.jp)の死活監視。
# 通知先は運用チャネル(Slack)のみ。ユーザーのLINEには絶対に出さない。
#
# 【なぜHTTPコードだけでは足りないか】
# 2026-07-15 の調査で ai/dev.udlr.jp が「HTTP 200 を返すが body 0 バイト」の状態で
# 3ヶ月放置されていたことが判明した。Vercelは0バイトのファイルを正常に配信するため、
# コード監視は 200 OK = 正常と判定してすり抜ける。oms.udlr.jp の6日間沈黙障害
# (2026-07-14) も「配信は生きているが中身が出ない」同型で、コード監視では捕れない。
# そこで本スクリプトは HTTPコードに加え body の実バイト数を下限と突き合わせる。
#
# 【なぜ下限をサイト個別に持つか】
# 一律1バイトでは「0バイトは捕れるが、CSSだけ壊れて数百バイトの残骸が返る」を見逃す。
# 各サイトの実測値の概ね半分を下限に置き、明らかな痩せ細りも異常として拾う。
set -uo pipefail

set -a; [ -f "$HOME/.hermes/.env" ] && . "$HOME/.hermes/.env"; set +a

LOG="${CHECK_SITES_LOG:-$HOME/.hermes/logs/check-sites.log}"
STATE_DIR="${CHECK_SITES_STATE_DIR:-$HOME/.hermes/state/check-sites}"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

mkdir -p "$(dirname "$LOG")" "$STATE_DIR" 2>/dev/null || true
ts() { date '+%Y-%m-%d %H:%M:%S%z'; }
log() { echo "$(ts) $*" >> "$LOG" 2>/dev/null || true; }

# 監視対象: <URL> <期待HTTPコード> <body下限バイト> <必須文字列>
# 下限は 2026-07-15 実測値の約半分（2026-07-16 再実測で整合確認済み）。
# 必須文字列は「サイズは足りているが別物が返っている」（エラーページ・誤ルーティング等）を捕るため。
# 空白を含まない1トークンで書くこと（行が空白分割されるため）。LP作り替え時は両方更新する。
TARGETS=(
  "https://oms.udlr.jp/            200 20000  請求管理"
  "https://ai.udlr.jp/             200  1000  UDLR"
  "https://dev.udlr.jp/            200  1000  UDLR"
  "https://lab.udlr.jp/            200  1000  UDLR"
  "https://ai.udlr.jp/blueprint/   200 100000 Blueprint"
  "https://lab.udlr.jp/infra-case/ 200  5000  インフラ設計"
)

notify() {
  local msg="$1"
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] Slack通知: $msg"
    return 0
  fi
  if [ -z "${SLACK_OPS_WEBHOOK:-}" ]; then
    log "SLACK_OPS_WEBHOOK 未設定のため通知できず: $msg"
    return 0
  fi
  curl -sS -m 10 -X POST "$SLACK_OPS_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "$(printf '{"text":%s}' "$(printf '%s' "$msg" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')")" \
    >/dev/null || log "Slack通知の送信に失敗: $msg"
}

# 状態遷移時のみ通知する（正常時の毎回通知や、障害中の連投を防ぐ）。
# state ファイルに前回の ok/ng を保持し、変化した時だけ鳴らす。
state_file_for() { echo "$STATE_DIR/$(printf '%s' "$1" | tr -c 'a-zA-Z0-9' '_')"; }

fail_count=0
for entry in "${TARGETS[@]}"; do
  # shellcheck disable=SC2086
  set -- $entry
  url="$1"; want_code="$2"; min_bytes="$3"; marker="${4:-}"

  body="$(curl -sS -L -m 20 "$url" 2>/dev/null)" || body=""
  code="$(curl -sS -L -o /dev/null -m 20 -w '%{http_code}' "$url" 2>/dev/null)" || code="000"
  size="$(printf '%s' "$body" | wc -c | tr -d ' ')"

  reason=""
  if [ "$code" != "$want_code" ]; then
    reason="HTTP ${code}（期待 ${want_code}）"
  elif [ "$size" -lt "$min_bytes" ]; then
    reason="HTTP ${code} だが body ${size}バイト（下限 ${min_bytes}バイトを下回る）"
  # 文字列照合はパイプ+grepを使わない: set -o pipefail 下では grep -q のマッチ即終了で
  # printf が SIGPIPE(141) を受け、大きいbodyだけ偽NGになる（263KBページで実発生）。
  elif [ -n "$marker" ] && [[ "$body" != *"$marker"* ]]; then
    reason="HTTP ${code} / ${size}バイトだが必須文字列「${marker}」が見つからない（別コンテンツが返っている可能性）"
  fi

  sf="$(state_file_for "$url")"
  prev="$(cat "$sf" 2>/dev/null || echo "ok")"

  if [ -n "$reason" ]; then
    fail_count=$((fail_count + 1))
    log "NG $url — $reason"
    if [ "$prev" != "ng" ]; then
      notify "🚨 サイト異常を検知しました
・URL: ${url}
・症状: ${reason}
※「200 OK だが中身が空」はブラウザで開くまで気づけません。確認をお願いします。"
    fi
    echo "ng" > "$sf" 2>/dev/null || true
    [ "$DRY_RUN" = "1" ] && echo "NG   $url — $reason"
  else
    log "OK $url — HTTP ${code} / ${size}バイト"
    if [ "$prev" = "ng" ]; then
      notify "✅ 復旧を確認しました
・URL: ${url}
・状態: HTTP ${code} / ${size}バイト"
    fi
    echo "ok" > "$sf" 2>/dev/null || true
    [ "$DRY_RUN" = "1" ] && echo "OK   $url — HTTP ${code} / ${size}バイト"
  fi
done

[ "$fail_count" -gt 0 ] && exit 1
exit 0
