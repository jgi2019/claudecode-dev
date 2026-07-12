"""Supabase tenants ストア（オンボーディングウィザード用）。

PostgREST エンドポイント経由で tenants テーブルを読み書きする。RLS が有効なため
service_role キーを使い、サーバー側書き込みで RLS をバイパスする。

認証情報は環境変数から取得（~/.hermes/.env に置く）:
  SUPABASE_URL                 例: https://itcwabtxlxemfhoaefxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY    Supabase ダッシュボード Settings > API の service_role キー

同期 requests を使う。pre_gateway_dispatch フックは同期呼び出しで、tenant の有無に
よって skip/allow を返す必要があるため、DB 参照は同期で完了させる（MVP。将来は
スレッドプール化を検討）。すべてのエラーは呼び出し側で握りつぶす前提で raise する。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 6  # 秒。イベントループを長く塞がないための上限。


def _creds() -> Optional[tuple[str, str]]:
    url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        logger.warning(
            "aiworkerpass-wizard: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が未設定。"
            "ウィザードは動作しません（~/.hermes/.env を確認）。"
        )
        return None
    return url, key


def is_configured() -> bool:
    return _creds() is not None


def _headers(key: str, prefer: str = "") -> Dict[str, str]:
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def get_tenant(line_user_id: str) -> Optional[Dict[str, Any]]:
    """line_user_id で tenant を1件引く。無ければ None。未設定でも None。"""
    c = _creds()
    if not c:
        return None
    url, key = c
    r = requests.get(
        f"{url}/rest/v1/tenants",
        params={"line_user_id": f"eq.{line_user_id}", "select": "*", "limit": "1"},
        headers=_headers(key),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def create_tenant(line_user_id: str, name: str) -> Optional[Dict[str, Any]]:
    """新規 tenant を作成（name は NOT NULL なので暫定値をseed）。作成行を返す。"""
    c = _creds()
    if not c:
        return None
    url, key = c
    r = requests.post(
        f"{url}/rest/v1/tenants",
        headers=_headers(key, prefer="return=representation"),
        json={
            "line_user_id": line_user_id,
            "name": name,
            "onboarding_step": 0,
            "onboarding_complete": False,
            "onboarding_answers": {},
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def update_tenant(line_user_id: str, patch: Dict[str, Any]) -> None:
    """line_user_id 一致行を patch で更新。"""
    c = _creds()
    if not c:
        return
    url, key = c
    r = requests.patch(
        f"{url}/rest/v1/tenants",
        params={"line_user_id": f"eq.{line_user_id}"},
        headers=_headers(key, prefer="return=minimal"),
        json=patch,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()


def save_conversation(
    line_user_id: str,
    tenant_id: Optional[str],
    user_message: Optional[str],
    assistant_response: Optional[str],
) -> None:
    """C-2 会話自動保存: 1往復を既存 conversation_logs へINSERT（管理画面MVPと共用）。

    conversation_logs は「1メッセージ=1行」モデル（role='user'|'assistant'|'system' +
    content）。よって1往復を user 行と assistant 行の**2行**として一括INSERTする。
    user 行の created_at を assistant 行より 1ms 早くして時系列順を保証する
    （両方 default now() だと同値になり user→assistant の順が崩れるため）。

    同期 requests。呼び出し側は fire-and-forget（別スレッド）で呼び、応答UX/gateway を
    ブロックしないこと。未設定なら何もしない。エラーは呼び出し側で握り潰す前提で raise。
    """
    c = _creds()
    if not c:
        return
    from datetime import datetime, timedelta, timezone

    base = datetime.now(timezone.utc)
    rows = []
    um = (user_message or "").strip()
    ar = (assistant_response or "").strip()
    if um:
        rows.append({
            "line_user_id": line_user_id,
            "tenant_id": tenant_id,
            "role": "user",
            "content": um,
            "created_at": base.isoformat(),
        })
    if ar:
        rows.append({
            "line_user_id": line_user_id,
            "tenant_id": tenant_id,
            "role": "assistant",
            "content": ar,
            "created_at": (base + timedelta(milliseconds=1)).isoformat(),
        })
    if not rows:  # 両方空の往復は保存しない
        return
    url, key = c
    r = requests.post(
        f"{url}/rest/v1/conversation_logs",
        headers=_headers(key, prefer="return=minimal"),
        json=rows,  # 配列 = 複数行を1リクエストで一括INSERT
        timeout=_TIMEOUT,
    )
    r.raise_for_status()


def bump_cost(
    tenant_id: Optional[str],
    model: Optional[str],
    api_calls: int,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    """cost_tracking を (usage_date=JST today, tenant_id, model) 単位で日次加算する。

    PostgREST 単体では「行が無ければINSERT・有れば加算UPDATE」を原子的にできない
    （Prefer: merge-duplicates は上書きであって加算ではない）ため、DB側の RPC
    increment_cost_tracking() を呼ぶ。同関数は INSERT ... ON CONFLICT DO UPDATE で
    api_calls/input_tokens/output_tokens/cost_usd をアトミックに += する。
    フックの多重発火・並行呼び出しでも二重加算にならない。

    tenant_id が無い（session未マップ）呼び出しは呼び出し側で除外する想定。
    同期 requests。呼び出し側は fire-and-forget（別スレッド）で呼ぶこと。未設定なら何もしない。
    """
    c = _creds()
    if not c:
        return
    if not tenant_id:
        return  # テナント未特定のコストは日次集計キーが立たないため記録しない
    url, key = c
    r = requests.post(
        f"{url}/rest/v1/rpc/increment_cost_tracking",
        headers=_headers(key, prefer="return=minimal"),
        json={
            "p_tenant_id": tenant_id,
            "p_model": model,
            "p_calls": int(api_calls),
            "p_input": int(input_tokens),
            "p_output": int(output_tokens),
            "p_cost": float(cost_usd),
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
