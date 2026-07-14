"""aiwp-escalation — エスカレーション検知 → Slack #aiwp-ops 通知（gateway dir-hook）。

agent:end イベント（gateway/run.py が emit。context に platform/user_id/
chat_id/response[:500] を含む）で発火し、LINE利用者向け応答に
エスカレーション文言が含まれた時だけ 運営チャネル #aiwp-ops(SLACK_OPS_WEBHOOK) へ通知する。

設計上の約束:
- ユーザー本人には何も送らない（通知は運営のみ）
- 通知は Slack 一本化（LINE push は課金ゼロ化のため停止・設計シート§6）。
  HEY への LINE 通知は Slack で代替できている前提
- escalations テーブルへは1件INSERT（管理画面 画面2 の受信箱と共用。Type A-D は画面で付与）
- 例外は全て握り潰し、gateway を絶対に壊さない
- 同一ユーザーからの連続発火は10分間デデュープ（通知スパム防止）
- SLACK_OPS_WEBHOOK 未設定なら通知は無音（INSERT は継続）
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

logger = logging.getLogger("aiwp_escalation")

# 検知フレーズ（persona側の確定文言に合わせる。env で上書き可）
_DEFAULT_PHRASES = "運営に伝え,運営にお伝え,運営に共有,運営に報告"

# user_id -> last notified epoch。プロセス内デデュープ（10分）
_last_sent: dict[str, float] = {}
_DEDUPE_SEC = 600


def _phrases() -> list[str]:
    raw = os.environ.get("AIWP_ESCALATION_PHRASES", _DEFAULT_PHRASES)
    return [p.strip() for p in raw.split(",") if p.strip()]


def _supabase_creds() -> tuple[str, str] | None:
    url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    return (url, key) if url and key else None


async def _insert_escalation(line_user_id: str, summary: str, detail: str) -> None:
    """escalations テーブルへ1件INSERT（管理画面のエスカレーション画面と共用）。

    このフックは plugin パッケージの store.py を import できない（sys.path が別）ため、
    同じ env(SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY) から service_role で PostgREST を
    直接叩く。tenant_id は line_user_id から tenants を1件引いて紐付ける（引けなければ
    NULLのまま。schema上 null可）。例外は握り潰して gateway/通知を絶対に壊さない。
    """
    c = _supabase_creds()
    if not c:
        return
    url, key = c
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        import aiohttp
        async with aiohttp.ClientSession() as sess:
            tenant_id = None
            async with sess.get(
                f"{url}/rest/v1/tenants",
                params={"line_user_id": f"eq.{line_user_id}", "select": "id", "limit": "1"},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as tr:
                if tr.status == 200:
                    rows = await tr.json()
                    if rows:
                        tenant_id = rows[0].get("id")
            payload = {
                "tenant_id": tenant_id,
                "line_user_id": line_user_id,
                "summary": summary[:200] or "エスカレーション検知",
                "detail": detail[:2000],
                # source は CHECK 制約 ('hook','slack','manual') 準拠。gatewayフック由来=hook。
                # （旧 'ai_auto' は制約違反でINSERTが常に失敗していた＝2026-07-13修正）
                "source": "hook",
            }
            async with sess.post(
                f"{url}/rest/v1/escalations",
                headers={**headers, "Prefer": "return=minimal"},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    logger.warning("aiwp-escalation: escalations INSERT %s: %s", resp.status, body[:200])
    except Exception as exc:
        logger.warning("aiwp-escalation: escalations INSERT 失敗: %s", exc)


async def _notify_slack(text: str) -> None:
    """運営チャネル #aiwp-ops(SLACK_OPS_WEBHOOK) へ通知。未設定なら無音。例外は握り潰す。"""
    hook = (os.environ.get("SLACK_OPS_WEBHOOK") or "").strip()
    if not hook:
        return
    try:
        import aiohttp
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                hook,
                json={"text": text[:3900]},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status not in (200, 204):
                    body = await resp.text()
                    logger.warning("aiwp-escalation: Slack通知 %s: %s", resp.status, body[:200])
    except Exception as exc:
        logger.warning("aiwp-escalation: Slack通知 失敗: %s", exc)


# HEY への Slack メンション先（ハードコード。将来 Operator 追加時に設定値化する前提）。
_HEY_SLACK_MENTION = os.environ.get("AIWP_OPS_MENTION", "<@U05RJDCT6DN>").strip()


async def _fetch_tenant_name(line_user_id: str) -> str:
    """tenants.name（オンボで確定した表示名）を1件引く。取れなければ空文字を返す。"""
    c = _supabase_creds()
    if not c:
        return ""
    url, key = c
    try:
        import aiohttp
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                f"{url}/rest/v1/tenants",
                params={"line_user_id": f"eq.{line_user_id}", "select": "name", "limit": "1"},
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as tr:
                if tr.status == 200:
                    rows = await tr.json()
                    if rows:
                        return str(rows[0].get("name") or "").strip()
    except Exception as exc:
        logger.warning("aiwp-escalation: tenant名 取得失敗: %s", exc)
    return ""


async def _notify_slack_escalation(line_user_id: str, user_msg: str, excerpt: str) -> None:
    """#aiwp-ops へエスカレ通知。HEYメンション＋利用者表示名＋管理画面直リンク。"""
    name = await _fetch_tenant_name(line_user_id)
    who = name or line_user_id  # 表示名が取れなければ ID にフォールバック
    text = (
        "🚨 AI Worker's Pass エスカレーション検知\n"
        f"{_HEY_SLACK_MENTION}\n"
        f"利用者: {who}\n"
        f"直前の発言: {user_msg}\n"
        f"AI応答(抜粋): {excerpt}\n\n"
        "📋 https://aiwp-admin.vercel.app/escalations"
    )
    await _notify_slack(text)


async def handle(event_type: str, context: dict) -> None:
    try:
        if str(context.get("platform", "")).lower() != "line":
            return
        user_id = str(context.get("user_id") or "")
        if not user_id:
            return
        # HEY自身の会話は通知しない（AIWP_ESCALATION_LINE_USER 未設定なら判定スキップ）。
        hey = (os.environ.get("AIWP_ESCALATION_LINE_USER") or "").strip()
        if hey and user_id == hey:
            return
        response = context.get("response") or ""
        if not any(p in response for p in _phrases()):
            return
        now = time.time()
        if now - _last_sent.get(user_id, 0) < _DEDUPE_SEC:
            return
        _last_sent[user_id] = now

        user_msg = (context.get("message") or "")[:200]
        excerpt = response[:200]
        # emit は handler の例外を握るが、こちらでも fire-and-forget にして
        # agent:end の後続処理を一切遅らせない。10分デデュープ内なので
        # Slack通知と escalations INSERT は対で1回ずつ（DB行の乱立も防ぐ）。
        loop = asyncio.get_running_loop()
        loop.create_task(_notify_slack_escalation(user_id, user_msg, excerpt))
        summary = f"[自動検知] {excerpt}" if excerpt else "エスカレーション検知"
        detail = f"利用者発言: {user_msg}\nAI応答(抜粋): {excerpt}"
        loop.create_task(_insert_escalation(user_id, summary, detail))
    except Exception as exc:
        logger.warning("aiwp-escalation: handler 例外: %s", exc)
