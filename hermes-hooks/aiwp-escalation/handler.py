"""aiwp-escalation — エスカレーション検知 → HEY LINE push（gateway dir-hook）。

agent:end イベント（gateway/run.py が emit。context に platform/user_id/
chat_id/response[:500] を含む）で発火し、LINE利用者向け応答に
エスカレーション文言が含まれた時だけ HEY の LINE へ push する。

設計上の約束:
- ユーザー本人には何も送らない（通知は運営=HEYのみ）
- 例外は全て握り潰し、gateway を絶対に壊さない
- 同一ユーザーからの連続発火は10分間デデュープ（通知スパム防止）
- env 未設定なら無音で無効（SLACK_OPS_WEBHOOK と同じ思想）
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


async def _push_line(to_user: str, text: str) -> None:
    token = (os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") or "").strip()
    if not token:
        return
    try:
        import aiohttp
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://api.line.me/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"to": to_user, "messages": [{"type": "text", "text": text[:4900]}]},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("aiwp-escalation: LINE push %s: %s", resp.status, body[:200])
    except Exception as exc:
        logger.warning("aiwp-escalation: LINE push 失敗: %s", exc)


async def handle(event_type: str, context: dict) -> None:
    try:
        if str(context.get("platform", "")).lower() != "line":
            return
        hey = (os.environ.get("AIWP_ESCALATION_LINE_USER") or "").strip()
        if not hey:
            return  # 未設定なら無効（無音）
        user_id = str(context.get("user_id") or "")
        if not user_id or user_id == hey:
            return  # HEY自身の会話では通知しない
        response = context.get("response") or ""
        if not any(p in response for p in _phrases()):
            return
        now = time.time()
        if now - _last_sent.get(user_id, 0) < _DEDUPE_SEC:
            return
        _last_sent[user_id] = now

        user_msg = (context.get("message") or "")[:200]
        excerpt = response[:200]
        text = (
            "🚨 AI Worker's Pass エスカレーション\n"
            f"利用者: {user_id}\n"
            f"直前の発言: {user_msg}\n"
            f"AI応答(抜粋): {excerpt}\n\n"
            "対応が必要か確認してください。"
        )
        # emit は handler の例外を握るが、こちらでも fire-and-forget にして
        # agent:end の後続処理を一切遅らせない。
        asyncio.get_running_loop().create_task(_push_line(hey, text))
    except Exception as exc:
        logger.warning("aiwp-escalation: handler 例外: %s", exc)
