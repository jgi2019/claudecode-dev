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


def _schedule_send_many(gateway, source, texts) -> None:
    """複数バブルを順序保証で送る（③ ウェルカム＋呼び水用）。

    _schedule_send を複数回呼ぶと create_task が投げっぱなしで到着順が保証されず、
    完了文より先にウェルカムが届く事故が起きうる。ここでは1タスク内で send を
    逐次 await するため順序が確定する。先頭バブルは reply token、2通目以降は
    adapter が push フォールバックする（adapter.send の確認済み契約）。
    """
    adapters = getattr(gateway, "adapters", {}) or {}
    adapter = adapters.get(getattr(source, "platform", None))
    if adapter is None:
        logger.warning("aiworkerpass-wizard: LINE adapter 未取得。送信スキップ。")
        return
    chat_id = source.chat_id
    msgs = [t for t in texts if t]

    async def _run():
        for t in msgs:
            try:
                await adapter.send(chat_id, t)
            except Exception as exc:  # 1通失敗しても残りは続ける
                logger.warning("aiworkerpass-wizard: 逐次送信で例外: %s", exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


# --- Quick Reply（LINEボタン）送信 -------------------------------------------
# adapter.send() はテキスト専用で quickReply を載せられない。本体 adapter を
# 改変すると uv tool upgrade で毎回消える（A-4/B-2 と同じ再パッチ地獄＋情報漏洩
# リスク）ため、プラグイン内で quickReply 付き message を組み、adapter の低レベル
# クライアント（_client.reply / .push）へ直接流す。内部が無い旧環境では自動で
# 通常テキスト送信にフォールバックし、gateway を決して壊さない。

# LINE Quick Reply のハード制約
_QR_MAX_ITEMS = 13   # 1メッセージあたり最大13ボタン
_QR_LABEL_MAX = 20   # ボタン表示ラベル 20字
_QR_TEXT_MAX = 300   # message アクションで送る text 300字
_LINE_BUBBLE_MAX = 5000  # テキストバブル上限


def _quick_reply_block(options) -> Optional[Dict[str, Any]]:
    """(label, send_text) のリストから LINE quickReply dict を組む。空なら None。

    send_text をタップ時にそのまま送信する message アクション。従来の番号手打ちと
    同じ文字列を送るため、パーサ側は無改修で後方互換。
    """
    items = []
    for pair in (options or [])[:_QR_MAX_ITEMS]:
        try:
            label, send_text = pair
        except (TypeError, ValueError):
            continue
        if not send_text:
            continue
        items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": (str(label) or str(send_text))[:_QR_LABEL_MAX],
                "text": str(send_text)[:_QR_TEXT_MAX],
            },
        })
    return {"items": items} if items else None


def _adapter_supports_low_level(adapter) -> bool:
    """低レベル送信（quickReply 付与）に必要な内部が揃っているか。"""
    return (
        adapter is not None
        and getattr(adapter, "_client", None) is not None
        and hasattr(adapter, "_consume_reply_token")
    )


async def _send_text_with_quick_reply(adapter, chat_id: str, text: str, quick_reply) -> None:
    """quickReply 付きの単一テキストバブルを、reply token 優先・push フォールバックで送る。

    ウィザードの確定文言は短文（<5000字）なので分割・Markdown 剥がしは不要。
    adapter._consume_reply_token を使うことで、通常の adapter.send と同じ
    reply-token 消費規約に乗り、二重消費・順序崩れを避ける。
    """
    client = adapter._client
    if len(text) > _LINE_BUBBLE_MAX:
        text = text[: _LINE_BUBBLE_MAX - 1] + "…"
    message: Dict[str, Any] = {"type": "text", "text": text}
    if quick_reply:
        message["quickReply"] = quick_reply
    messages = [message]

    token, used_reply = adapter._consume_reply_token(chat_id)
    if used_reply:
        try:
            await client.reply(token, messages)
            return
        except Exception as exc:  # token 期限切れ等 → push へ
            logger.info("aiworkerpass-wizard: reply token 却下(%s)、push へ", exc)
    await client.push(chat_id, messages)


def _schedule_send_quick_reply(gateway, source, text: str, options) -> None:
    """text を Quick Reply ボタン（options=(label, send_text) のリスト）付きで送る。

    ボタン非対応環境・内部欠如時は通常テキスト送信にフォールバック（番号手打ちは
    従来どおり有効）。同期フックから async 送信をイベントループに載せる。
    """
    adapters = getattr(gateway, "adapters", {}) or {}
    adapter = adapters.get(getattr(source, "platform", None))
    if adapter is None:
        logger.warning("aiworkerpass-wizard: LINE adapter 未取得。送信スキップ。")
        return
    chat_id = source.chat_id
    quick_reply = _quick_reply_block(options)
    if not quick_reply or not _adapter_supports_low_level(adapter):
        _schedule_send(gateway, source, text)  # フォールバック（ボタンなし）
        return

    async def _run():
        try:
            await _send_text_with_quick_reply(adapter, chat_id, text, quick_reply)
        except Exception as exc:  # 送信失敗 → 素のテキストで最終フォールバック
            logger.warning("aiworkerpass-wizard: quick reply 送信失敗、通常送信へ: %s", exc)
            try:
                await adapter.send(chat_id, text)
            except Exception as exc2:
                logger.warning("aiworkerpass-wizard: フォールバック送信も失敗: %s", exc2)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


def _schedule_send_many_last_quick_reply(gateway, source, texts, options) -> None:
    """複数バブルを順序保証で送り、最後のバブルにだけ Quick Reply を付ける。

    呼び水フロー（完了文→ウェルカム→呼び水）用。並びは _schedule_send_many と同じく
    1タスク内で逐次 await して順序を確定させる。先頭は reply token、以降は push。
    最後のバブルは token 消費済み → push（push でも quickReply は有効）。
    """
    adapters = getattr(gateway, "adapters", {}) or {}
    adapter = adapters.get(getattr(source, "platform", None))
    if adapter is None:
        logger.warning("aiworkerpass-wizard: LINE adapter 未取得。送信スキップ。")
        return
    chat_id = source.chat_id
    msgs = [t for t in texts if t]
    if not msgs:
        return
    quick_reply = _quick_reply_block(options)
    if not quick_reply or not _adapter_supports_low_level(adapter):
        _schedule_send_many(gateway, source, msgs)  # フォールバック（ボタンなし）
        return

    async def _run():
        last = len(msgs) - 1
        for i, t in enumerate(msgs):
            try:
                if i == last:
                    await _send_text_with_quick_reply(adapter, chat_id, t, quick_reply)
                else:
                    await adapter.send(chat_id, t)
            except Exception as exc:  # 1通失敗しても残りは続ける
                logger.warning("aiworkerpass-wizard: 逐次(QR)送信で例外: %s", exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


def _purge_hermes_state(gateway, source, session_store) -> None:
    """「削除」時に Hermes 側の会話履歴・キャッシュエージェント・学習メモリを消す。

    我々の tenant レコード（Supabase）だけ消しても、Hermes 側に残る
    ① セッション会話履歴（sessions.json / state.db）
    ② キャッシュ済みエージェントが RAM に保持する記憶
    ③ グローバル学習メモリ ~/.hermes/memories/USER.md（self-improvementが書く）
    が生き残り、「削除したのに前の会話（例：領収書の件）を引きずる」ため。

    ネイティブ /new・/reset は①②は消すが③（長期メモリ）は消さない設計。
    「削除＝全部消せます」を満たすには③も明示的に空にする必要がある。

    ※ ③のメモリは現状テナント非分離のグローバル1ファイル。単一利用者テスト前提で
      全消しにしている。本番マルチテナントでは要スコープ化（TARO相談事項）。
    """
    # 1) session key を Hermes 正規経路で解決（自前再構築せず namespace ズレを回避）
    skey = None
    try:
        if gateway is not None and hasattr(gateway, "_session_key_for_source"):
            skey = gateway._session_key_for_source(source)
    except Exception as exc:
        logger.warning("aiworkerpass-wizard: session_key 解決失敗: %s", exc)

    # 2) 会話履歴リセット（新 session_id を発行し旧履歴を切り離す）
    if skey and session_store is not None and hasattr(session_store, "reset_session"):
        try:
            session_store.reset_session(skey)
        except Exception as exc:
            logger.warning("aiworkerpass-wizard: reset_session 失敗: %s", exc)

    # 3) キャッシュ済みエージェントを evict（RAM上のメモリキャッシュを破棄＝
    #    直後のUSER.md空化がpost-turn syncで書き戻される事故を防ぐ）
    if skey and gateway is not None and hasattr(gateway, "_evict_cached_agent"):
        try:
            gateway._evict_cached_agent(skey)
        except Exception as exc:
            logger.warning("aiworkerpass-wizard: evict_cached_agent 失敗: %s", exc)

    # 4) テナント別学習メモリ memories/{user_id}/ を丸ごと削除する。
    #    本体パッチ B-2（テナント分離）適用後は、LINE利用者のメモリは
    #    memories/{sanitized_user_id}/ に閉じているので、そこだけ消す。
    #    グローバル memories/ 直下（owner/CLI用）には触らない。
    try:
        import os
        import shutil
        try:
            from tools.memory_tool import sanitize_scope as _san
        except Exception:  # 本体パッチ未適用環境へのフォールバック（同義実装）
            import re
            def _san(uid):
                s = re.sub(r"[^A-Za-z0-9_-]", "_", str(uid or "").strip())[:64]
                return s or None
        scope = _san(getattr(source, "user_id", None))
        if scope:
            home = os.environ.get("HERMES_HOME") or "~/.hermes"
            mem_dir = os.path.expanduser(os.path.join(home, "memories", scope))
            # 実在確認＋ memories/ 配下であることを二重確認してから削除
            base = os.path.expanduser(os.path.join(home, "memories"))
            if os.path.isdir(mem_dir) and os.path.realpath(mem_dir).startswith(
                os.path.realpath(base) + os.sep
            ):
                shutil.rmtree(mem_dir, ignore_errors=True)
    except Exception as exc:
        logger.warning("aiworkerpass-wizard: tenant memory clear 失敗: %s", exc)


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

        # BANフラグ（第4層）: banned テナントは全メッセージを無応答で遮断。
        # pre_llm_call より手前のここで止めることで、ウィザードもLLM呼び出しも
        # 一切走らない（コストゼロ・完全遮断）。返信もしない＝ブロックの
        # フィードバックを攻撃者に与えない。解除は Supabase tenants.banned=false。
        if tenant is not None and tenant.get("banned"):
            logger.info("aiworkerpass-wizard: banned tenant %s をスキップ", user_id)
            return {"action": "skip", "reason": "tenant-banned"}

        # 「削除」— どの段階でも全データをクリアして初期化。
        # tenant の有無に関わらず Hermes 側（会話履歴・エージェント・学習メモリ）も消す。
        if text == _RESET_KEYWORD:
            _purge_hermes_state(gateway, source, session_store)
            if tenant is not None:
                store.update_tenant(user_id, {
                    "onboarding_step": 0,
                    "onboarding_complete": False,
                    "onboarding_answers": {},
                    "system_prompt": None,
                })
            _schedule_send(
                gateway, source,
                "承知しました。あなたの設定と、これまでの会話・記憶をすべて消去しました。\n"
                "もう一度何か送っていただければ、最初から始めます。",
            )
            return {"action": "skip", "reason": "wizard-reset"}

        # --- 新規ユーザー: 宣言 + Q1 を1通で送る（reply token 1つに収める） ---
        if tenant is None:
            seed_name = display_name or "（確認中）"
            store.create_tenant(user_id, seed_name)
            if display_name:
                # 表示名あり → 確認フロー（1/2で選ぶ）。Quick Reply ボタンを添える。
                store.update_tenant(user_id, {"onboarding_step": 1})
                first = wizard.DECLARATION + "\n\n" + wizard.q1_confirm_name(display_name)
                q1_options = wizard.Q1_CONFIRM_QUICK_REPLY
            else:
                # 表示名なし（ID等）→ 最初から名前を聞く（自由記述なのでボタンなし）。
                store.update_tenant(user_id, {
                    "onboarding_step": 1,
                    "onboarding_answers": {"_awaiting_rename": True},
                })
                first = wizard.DECLARATION + "\n\n" + wizard.Q1_ASK_NAME
                q1_options = None
            # options=None のときは _schedule_send_quick_reply が通常送信にフォールバック。
            _schedule_send_quick_reply(gateway, source, first, q1_options)
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
                q1_options = wizard.Q1_CONFIRM_QUICK_REPLY
            else:
                store.update_tenant(user_id, {"onboarding_step": 1, "onboarding_answers": {"_awaiting_rename": True}})
                q1 = wizard.Q1_ASK_NAME
                q1_options = None
            _schedule_send_quick_reply(gateway, source, wizard.DECLARATION + "\n\n" + q1, q1_options)
            return {"action": "skip", "reason": "wizard-restart-q1"}

        # === Q1: 呼び方の確認 ===
        if step == 1:
            if answers.get("_awaiting_rename"):
                new_name = text or display_name or "あなた"
                a = _patch_answers(answers, q1_name=new_name)
                a.pop("_awaiting_rename", None)
                store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 2, "name": new_name})
                _schedule_send_quick_reply(gateway, source, wizard.Q2, wizard.Q2_QUICK_REPLY)
                return {"action": "skip"}
            choice = wizard.parse_choice_single(text)
            if choice == 1:
                keep = display_name or "あなた"
                a = _patch_answers(answers, q1_name=keep)
                store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 2, "name": keep})
                _schedule_send_quick_reply(gateway, source, wizard.Q2, wizard.Q2_QUICK_REPLY)
                return {"action": "skip"}
            if choice == 2:
                a = _patch_answers(answers, _awaiting_rename=True)
                store.update_tenant(user_id, {"onboarding_answers": a})
                _schedule_send(gateway, source, wizard.Q1_RENAME_PROMPT)  # 自由記述なのでボタンなし
                return {"action": "skip"}
            # 無効 → 確認を Quick Reply 付きで再提示
            _schedule_send_quick_reply(gateway, source, wizard.q1_confirm_name(display_name), wizard.Q1_CONFIRM_QUICK_REPLY)
            return {"action": "skip"}

        # === Q2: お仕事・立場（単一番号 1..5） ===
        if step == 2:
            choice = wizard.parse_choice_single(text)
            if choice not in (1, 2, 3, 4, 5):
                _schedule_send_quick_reply(gateway, source, "番号（1〜5）で教えてください。\n\n" + wizard.Q2, wizard.Q2_QUICK_REPLY)
                return {"action": "skip"}
            a = _patch_answers(answers, q2_role_n=choice)
            store.update_tenant(user_id, {"onboarding_answers": a, "onboarding_step": 3, "role": wizard._ROLE_LABELS.get(choice)})
            _schedule_send_quick_reply(gateway, source, wizard.Q3, wizard.Q3_QUICK_REPLY)
            return {"action": "skip"}

        # === Q3: AIとの付き合い方（複数番号 1..5） ===
        if step == 3:
            picks = wizard.parse_choice_multi(text)
            if not picks:
                _schedule_send_quick_reply(gateway, source, "番号で教えてください（複数OK・例：1 3）。\n\n" + wizard.Q3, wizard.Q3_QUICK_REPLY)
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
            # ③ 完了文 → ウェルカム → 呼び水 を、この順で確定文言（LLM非経由）で送る。
            # 呼び水の意味は build_system_prompt にも載っているので、番号返信は
            # onboarding_complete 後の通常応答（pre_llm_call 注入）で解釈される。
            # 最後の呼び水バブルにだけ Quick Reply（①〜④）を付ける。
            _schedule_send_many_last_quick_reply(gateway, source, [
                wizard.completion(a.get("q1_name") or "あなた"),
                wizard.WELCOME_MESSAGE,
                wizard.PRIMER_MESSAGE,
            ], wizard.PRIMER_QUICK_REPLY)
            return {"action": "skip", "reason": "wizard-complete"}

        # 想定外の step → 通常応答にフォールバック
        return None

    except Exception as exc:  # gateway を絶対に壊さない
        logger.warning("aiworkerpass-wizard: ハンドラ例外（通常応答にフォールバック）: %s", exc, exc_info=True)
        return None


def _on_pre_llm_call(sender_id=None, platform=None, **_kw):
    """オンボ完了テナントの system_prompt を、毎ターンの user メッセージ末尾に
    ephemeral 注入する（Hermes 契約: context は user 側に入り、system prompt=
    キャッシュprefix は不変に保たれる）。sender_id は LINE user_id と同値。

    - 未完了 / 非LINE / prompt未生成 → None（素の応答）
    - 完了済み → {"context": ラップ済みsystem_prompt}
    """
    try:
        if str(platform).lower() != "line":
            return None
        if not sender_id:
            return None
        tenant = store.get_tenant(sender_id)
        if not tenant or not tenant.get("onboarding_complete"):
            return None
        if tenant.get("banned"):
            # 保険: dispatch層で遮断済みのはずだが、万一ここまで来ても
            # persona注入はしない（素の応答のみ）。
            return None
        sp = (tenant.get("system_prompt") or "").strip()
        if not sp:
            return None
        # Hermes が自前のメモリ注入で使う <memory-context> 枠に厳密に載せる。
        # この System note 文字列はモデルが「信頼できる記憶」として受容するよう
        # 訓練されており、独自の命令調ラップ（=プロンプトインジェクション扱いで
        # 拒否される）を避けられる。§memory_manager.build_memory_context_block と同型。
        wrapped = (
            "<memory-context>\n"
            "[System note: The following is recalled memory context, "
            "NOT new user input. Treat as authoritative reference data — "
            "this is the agent's persistent memory and should inform all responses.]\n\n"
            + sp + "\n"
            "</memory-context>"
        )
        return {"context": wrapped}
    except Exception as exc:
        logger.warning("aiworkerpass-wizard: pre_llm_call 例外（素の応答へ）: %s", exc)
        return None


def register(ctx) -> None:
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    logger.info("aiworkerpass-wizard: registered pre_gateway_dispatch + pre_llm_call hooks")
