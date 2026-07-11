"""aiworkerpass-wizard — AI Worker's Pass 初回オンボーディングウィザード（仕様書 §9）。

pre_gateway_dispatch フック（受信メッセージごと・エージェント応答前）で、LINE利用者の
オンボーディング状態を Supabase tenants で管理し、確定文言の6問ウィザードを進める。
完了時に回答を SOUL.md 3部へマッピングして system_prompt を生成・保存する。

- 未オンボーディング → ウィザードを進め、確定文言を直接送信し {"action":"skip"}（LLM非経由）
- オンボーディング済み → None を返し通常応答（Hermes が tenant.system_prompt を使う想定）

設計と実装契約の根拠は Hermes 実体コード（gateway/run.py の pre_gateway_dispatch、
plugins/platforms/line/adapter.py の send()）で確認済み。例外は全て握り潰し、gateway を
決して壊さない（最悪でも通常応答にフォールバック）。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from . import store, wizard

logger = logging.getLogger("aiworkerpass_wizard")

_RESET_KEYWORD = "削除"  # §9.4: いつでも「削除」で消せる


def _is_line(source) -> bool:
    val = getattr(getattr(source, "platform", None), "value", None)
    return str(val).lower() == "line"


def _schedule_send(gateway, source, text: str) -> None:
    """同期フックから async の adapter.send をイベントループに載せる。"""
    adapters = getattr(gateway, "adapters", {}) or {}
    adapter = adapters.get(getattr(source, "platform", None))
    if adapter is None:
        logger.warning("aiworkerpass-wizard: LINE adapter 未取得。送信スキップ。")
        return
    coro = adapter.send(source.chat_id, text)  # reply-token自動 / Markdown剥がし / 分割込み
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # gateway では稼働中ループがあるはず。無い場合のみ同期実行。
        asyncio.run(coro)


def _patch_answers(current: Optional[Dict[str, Any]], **updates) -> Dict[str, Any]:
    a = dict(current or {})
    a.update(updates)
    return a


def _on_pre_gateway_dispatch(event=None, gateway=None, session_store=None, **_kw):
    try:
        source = getattr(event, "source", None)
        if source is None or not _is_line(source):
            return None
        user_id = getattr(source, "user_id", None)
        chat_id = getattr(source, "chat_id", None)
        if not user_id or not chat_id:
            return None
        if not store.is_configured():
            return None  # 未設定なら通常応答にフォールバック（ウィザード無効）

        text = (getattr(event, "text", "") or "").strip()
        # 内部ID（Uab..）が user_name として来るケースを弾く。掃除済みの名前だけ使う。
        display_name = wizard.sanitize_display_name(getattr(source, "user_name", ""))

        tenant = store.get_tenant(user_id)

        # 「削除」— どの段階でもデータをクリアして初期化
        if text == _RESET_KEYWORD and tenant is not None:
            store.update_tenant(user_id, {
                "onboarding_step": 0,
                "onboarding_complete": False,
                "onboarding_answers": {},
                "system_prompt": None,
            })
            _schedule_send(gateway, source, "承知しました。あなたの設定を消去しました。\nもう一度何か送っていただければ、最初から始めます。")
            return {"action": "skip", "reason": "wizard-reset"}

        # --- 新規ユーザー: 宣言 + Q1 を1通で送る（reply token 1つに収める） ---
        if tenant is None:
            seed_name = display_name or "（確認中）"
            store.create_tenant(user_id, seed_name)
            if display_name:
                # 表示名あり → 確認フロー（1/2で選ぶ）
                store.update_tenant(user_id, {"onboarding_step": 1})
                first = wizard.DECLARATION + "\n\n" + wizard.q1_confirm_name(display_name)
            else:
                # 表示名なし（ID等）→ 最初から名前を聞く。次の返信を名前として拾う。
                store.update_tenant(user_id, {
                    "onboarding_step": 1,
                    "onboarding_answers": {"_awaiting_rename": True},
                })
                first = wizard.DECLARATION + "\n\n" + wizard.Q1_ASK_NAME
            _schedule_send(gateway, source, first)
            return {"action": "skip", "reason": "wizard-start"}

        # --- オンボーディング済み → 通常応答 ---
        if tenant.get("onboarding_complete"):
            return None

        step = int(tenant.get("onboarding_step") or 0)
        answers: Dict[str, Any] = tenant.get("onboarding_answers") or {}

        # step 0（宣言送信前にレコードだけある異常系）→ 宣言+Q1 を出し直す
        if step <= 0:
            if display_name:
                store.update_tenant(user_id, {"onboarding_step": 1})
                q1 = wizard.q1_confirm_name(display_name)
            else:
                store.update_tenant(user_id, {"onboarding_step": 1, "onboarding_answers": {"_awaiting_rename": True}})
                q1 = wizard.Q1_ASK_NAME
            _schedule_send(gateway, source, wizard.DECLARATION + "\n\n" + q1)
            return {"action": "skip", "reason": "wizard-restart-q1"}

        # === Q1: 呼び方の確認 ===
        if step == 1:
            if answers.get("_awaiting_rename"):
                new_name = text or display_name or "あなた"
                a = _patch_answers(answers, q1_name=new_name)
                a.pop("_awaiting_rename", None)
                store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 2, "name": new_name})
                _schedule_send(gateway, source, wizard.Q2)
                return {"action": "skip"}
            choice = wizard.parse_choice_single(text)
            if choice == 1:
                keep = display_name or "あなた"
                a = _patch_answers(answers, q1_name=keep)
                store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 2, "name": keep})
                _schedule_send(gateway, source, wizard.Q2)
                return {"action": "skip"}
            if choice == 2:
                a = _patch_answers(answers, _awaiting_rename=True)
                store.update_tenant(user_id, {"onboarding_answers": a})
                _schedule_send(gateway, source, wizard.Q1_RENAME_PROMPT)
                return {"action": "skip"}
            _schedule_send(gateway, source, wizard.q1_confirm_name(display_name))  # 無効 → 再提示
            return {"action": "skip"}

        # === Q2: お仕事・立場（単一番号 1..5） ===
        if step == 2:
            choice = wizard.parse_choice_single(text)
            if choice not in (1, 2, 3, 4, 5):
                _schedule_send(gateway, source, "番号（1〜5）で教えてください。\n\n" + wizard.Q2)
                return {"action": "skip"}
            a = _patch_answers(answers, q2_role_n=choice)
            store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 3, "role": wizard._ROLE_LABELS.get(choice)})
            _schedule_send(gateway, source, wizard.Q3)
            return {"action": "skip"}

        # === Q3: AIとの付き合い方（複数番号 1..5） ===
        if step == 3:
            picks = wizard.parse_choice_multi(text)
            if not picks:
                _schedule_send(gateway, source, "番号で教えてください（複数OK・例：1 3）。\n\n" + wizard.Q3)
                return {"action": "skip"}
            a = _patch_answers(answers, q3_ai=picks)
            store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 4})
            _schedule_send(gateway, source, wizard.Q4)
            return {"action": "skip"}

        # === Q4: 面倒だと感じること（自由記述） ===
        if step == 4:
            a = _patch_answers(answers, q4_pain=text)
            store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 5})
            _schedule_send(gateway, source, wizard.Q5)
            return {"action": "skip"}

        # === Q5: AIに任せたくないこと = Hard Limits（自由記述） ===
        if step == 5:
            a = _patch_answers(answers, q5_hardlimits=text)
            store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 6})
            _schedule_send(gateway, source, wizard.Q6)
            return {"action": "skip"}

        # === Q6: ゴール（自由記述）→ 完了。system_prompt 生成・保存 ===
        if step == 6:
            a = _patch_answers(answers, q6_goal=text)
            system_prompt = wizard.build_system_prompt(a)
            patch = {
                "onboarding_answers": a,
                "onboarding_step": 7,
                "onboarding_complete": True,
                "system_prompt": system_prompt,
                "goals": a.get("q6_goal"),
            }
            industry = wizard.infer_industry(a)
            if industry:
                patch["industry"] = industry
            store.update_tenant(user_id, patch)
            _schedule_send(gateway, source, wizard.completion(a.get("q1_name") or "あなた"))
            return {"action": "skip", "reason": "wizard-complete"}

        # 想定外の step → 通常応答にフォールバック
        return None

    except Exception as exc:  # gateway を絶対に壊さない
        logger.warning("aiworkerpass-wizard: ハンドラ例外（通常応答にフォールバック）: %s", exc, exc_info=True)
        return None


def register(ctx) -> None:
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
    logger.info("aiworkerpass-wizard: registered pre_gateway_dispatch hook")
