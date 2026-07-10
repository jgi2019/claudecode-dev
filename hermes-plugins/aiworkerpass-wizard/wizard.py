"""ウィザードの確定文言・回答パース・SOUL.md 3部マッピング（仕様書 §9）。

すべて平文（Markdown 不可 — §6.4/§9.5）。質問文は記号と改行のみで組む。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# --- §9.4 ウィザード前の宣言（不安への先回り。逐語で送る） ---------------------
DECLARATION = (
    "はじめまして。AI Worker's Pass です。\n"
    "これから6個、簡単な質問をさせてください。あなたに合ったお手伝いをするためです。\n"
    "お答えいただいた内容は、あなた専用の設定として保存され、他の方に共有されることはありません。\n"
    "いつでも「削除」と送れば、全部消せます。\n"
    "AIが答えられないときは、人間のスタッフが直接お答えします。その場合、あなたのご質問を私が拝見します。"
)


# --- §9.3 確定6問（番号選択は「番号を打つ」で成立するよう設計） -----------------
def q1_confirm_name(display_name: str) -> str:
    name = display_name.strip() if display_name and display_name.strip() else "あなた"
    return (
        "はじめまして。\n"
        f"「{name}」さん、でよろしいですか？\n"
        "1 このままでOK\n"
        "2 別の呼び方にする"
    )


Q1_RENAME_PROMPT = "では、どうお呼びすればよいですか？\n（例：たろう / 田中さん / 院長 など）"

Q2 = (
    "お仕事やお立場について教えてください。近いものを1つ、番号で。\n"
    "1 経営者・役員\n"
    "2 管理職・部門長\n"
    "3 現場のリーダー\n"
    "4 担当者・スタッフ\n"
    "5 ひとりで事業をしている"
)

Q3 = (
    "AIとの付き合い方について。当てはまるものを番号で。複数OK（例：1 3）。\n"
    "1 ChatGPTに、たまに質問する\n"
    "2 ChatGPTを、仕事で毎日使う\n"
    "3 プロジェクトやGPTsを作ったことがある\n"
    "4 Claude や Gemini なども試した\n"
    "5 まだ、どう使えばいいか探している最中"
)

Q4 = (
    "仕事の中で「これ、面倒だな」と感じることを教えてください。\n"
    "時間がかかっていることでも、気が重いことでも。\n"
    "小さなことでかまいません。"
)

Q5 = (
    "逆に、AIには任せたくないこと・触れてほしくないことはありますか？\n"
    "（例：お金の判断、お客様への最終返信 など）\n"
    "なければ「特にない」で大丈夫です。"
)

Q6 = "最後に。これができたら嬉しい・助かる、ということを教えてください。"


def completion(name: str) -> str:
    n = name.strip() if name and name.strip() else "あなた"
    return (
        "ありがとうございます。設定が完了しました。\n"
        f"これからは、いつでもお気軽にご相談ください。「{n}」さんに合わせてお答えします。"
    )


# --- 回答パース ---------------------------------------------------------------
_ROLE_LABELS = {
    1: "経営者・役員",
    2: "管理職・部門長",
    3: "現場のリーダー",
    4: "担当者・スタッフ",
    5: "ひとりで事業をしている",
}
_DECISION_MAKER_ROLES = {1, 2, 5}  # §9.3: 1・2・5 は決裁権を持つ

_AI_LABELS = {
    1: "ChatGPTにたまに質問する",
    2: "ChatGPTを仕事で毎日使う",
    3: "プロジェクトやGPTsを作ったことがある",
    4: "Claude/Gemini なども試した",
    5: "まだ、どう使えばいいか探している最中",
}
_PRACTICE_CAP_OPTION = 5  # §9.3: 5番が選ばれたら基礎から入る（practice_cap）


def parse_choice_single(text: str) -> int | None:
    """「1」「2」等の単一番号を拾う。全角数字も許容。"""
    t = (text or "").strip().translate(str.maketrans("１２３４５６７８９０", "1234567890"))
    for ch in t:
        if ch.isdigit():
            n = int(ch)
            if 1 <= n <= 9:
                return n
    return None


def parse_choice_multi(text: str) -> List[int]:
    """「1 3」「1,3」「135」等から番号集合を拾う（1..5）。"""
    t = (text or "").strip().translate(str.maketrans("１２３４５６７８９０", "1234567890"))
    out: List[int] = []
    for ch in t:
        if ch.isdigit():
            n = int(ch)
            if 1 <= n <= 5 and n not in out:
                out.append(n)
    return out


# --- SOUL.md 3部マッピング → system_prompt 生成 ------------------------------
def build_system_prompt(answers: Dict[str, Any]) -> str:
    """回答を Who You Are / Tone / Hard Limits にマッピングして system_prompt を生成。"""
    name = (answers.get("q1_name") or "あなた").strip() or "あなた"
    role_n = answers.get("q2_role_n")
    role_label = _ROLE_LABELS.get(role_n, "（未確認）")
    is_decision_maker = role_n in _DECISION_MAKER_ROLES
    ai_selected: List[int] = answers.get("q3_ai") or []
    practice_cap = _PRACTICE_CAP_OPTION in ai_selected  # 基礎から入る
    pain = (answers.get("q4_pain") or "").strip()
    hard_limits = (answers.get("q5_hardlimits") or "").strip()
    goal = (answers.get("q6_goal") or "").strip()

    lines: List[str] = []
    lines.append("あなたは「AI Worker's Pass」の担当AIです。以下の利用者の、専属の相談相手として応答します。")
    lines.append("")
    lines.append("# 利用者について（Who You Are）")
    lines.append(f"- 呼び方: {name} さん")
    dm = "（決裁権あり）" if is_decision_maker else ""
    lines.append(f"- 立場: {role_label}{dm}")
    if pain:
        lines.append(f"- 面倒・負担に感じていること: {pain}")
    if goal:
        lines.append(f"- 目指していること: {goal}")
    lines.append("")
    lines.append("# 話し方（Tone）")
    lines.append(f"- {name} さん、と呼ぶ。")
    if practice_cap:
        lines.append("- AIにまだ不慣れな段階。専門用語を避け、基礎から、一歩ずつ丁寧に説明する。")
    else:
        lines.append("- 要点から簡潔に答える。回りくどくしない。")
    if is_decision_maker:
        lines.append("- 導入・投資対効果・チームへの展開、という経営視点の語彙を持って答える。")
    lines.append("")
    lines.append("# やらないこと（Hard Limits）")
    if hard_limits and hard_limits not in ("特にない", "特に無い", "なし"):
        lines.append(f"- {hard_limits}")
    lines.append(
        "- 上記に触れる相談や、利用者に損害が及びうる判断が必要なときは、自分で判断せず"
        "「担当者に確認します」と伝えてエスカレーションする。"
    )
    lines.append("")
    lines.append("# 応答ルール（LINEの制約）")
    lines.append("- Markdownは使わない。見出し・箇条書き記号・コードブロック・太字は使わない。平文で短く。")
    lines.append("- 1回の返信は簡潔に。長くなるなら要点だけ先に返す。")
    lines.append("- 日本語で、やわらかく、丁寧に。")
    return "\n".join(lines)


def infer_industry(answers: Dict[str, Any]) -> str | None:
    """§9.6: 直接は聞かない。Q4自由記述の素材から後段（Phase 2）で推定する想定。
    MVPでは None（未推定）を返し、業種は空のままにする。"""
    return None
