#!/usr/bin/env python3
"""SHERPA FAQ候補の夜間バッチ生成。

Stage1: Perplexity Sonar で課題ごとに一次情報（具体的な解決手法・ツール・出典URL）を収集
Stage2: Claude Haiku 4.5 で Stage1 の素材を FAQ（question/answer）に整形し品質スコアを付与

入力: <outdir>/_input_issues.json  … Notion 課題DB から抽出した配列
出力: <outdir>/stage1/<id>.json    … Sonar の生結果（再実行時はスキップ＝レジューム可）
      <outdir>/stage2/<id>.json    … FAQ 1件
      <outdir>/faq_candidates.json … Stage2 を1本に束ねた最終成果物

【なぜ1件1ファイルか】
数百件を1プロセスで回す。途中で落ちた時に全部やり直すとAPI費用と時間を二重に払う。
完了済みをファイルの存在で判定してスキップすれば、何度でも安全に再実行できる。

【コスト特性・2026-07-15実測】
Sonar は $1/1M in・$1/1M out に対しリクエスト固定手数料 $5/1000req(low ctx) が乗る。
コストの約8割が固定手数料で、トークン量ではなく「何件叩くか」でほぼ決まる。
件数を絞る以外の節約策（プロンプト短縮等）はほとんど効かない。

【prompt caching を使わない理由】
Haiku 4.5 の最小キャッシュ可能プレフィックスは4096トークン。本スクリプトのsystemは
それより短く、cache_control を付けても無言でキャッシュされない（課金だけ増える恐れ）。
"""
import argparse
import json
import os
import pathlib
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import anthropic
import requests

# Stage2 のモデルは --model で切替。2026-07-15 時点は試走結果を見てHEYが確定させる方針のため
# 既定値に固定せず、選んだモデルを出力JSONに記録して後から追跡できるようにしている。
MODELS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
}
SONAR_URL = "https://api.perplexity.ai/chat/completions"

_print_lock = threading.Lock()


def say(msg):
    with _print_lock:
        print(msg, flush=True)


def load_env(path=None):
    """~/.hermes/.env から KEY=VALUE を読む。値はログに出さない。"""
    p = pathlib.Path(path or (pathlib.Path.home() / ".hermes" / ".env"))
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def extract_json(text):
    """モデル出力から JSON オブジェクトを取り出す。コードフェンス付きにも耐える。"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSONが見つからない: {text[:200]}")
    return json.loads(text[start:end + 1])


# ---------------- Stage1: Perplexity Sonar ----------------

SONAR_SYS = (
    "あなたは日本の中小企業のDX・AI活用に詳しいリサーチャーです。"
    "提示された業務課題について、実際に使える解決策を出典付きで調べます。"
    "一般論や精神論は書かず、具体的なツール名・機能名・手順・料金感を挙げてください。"
    "日本国内で実際に利用できるものを優先します。回答は日本語で500字以内。"
)


def sonar_prompt(it):
    parts = [f"【課題】{it['title']}"]
    for label, key in (("業種", "industry"), ("部署", "dept"),
                       ("具体シーン", "scene"), ("制約条件", "constraint_")):
        if it.get(key):
            parts.append(f"【{label}】{it[key]}")
    parts.append(
        "\nこの課題を解決する具体的な方法を調べてください。"
        "①使えるツール/サービス名（日本で利用可能なもの）"
        "②導入の手順の勘所"
        "③費用感や無料でできる範囲"
        "④つまずきやすい点"
        "の順で、出典に基づいて簡潔に。"
    )
    return "\n".join(parts)


def run_sonar(it, api_key, timeout=90):
    r = requests.post(
        SONAR_URL,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={
            "model": "sonar",
            "messages": [{"role": "system", "content": SONAR_SYS},
                         {"role": "user", "content": sonar_prompt(it)}],
            "max_tokens": 900,
            "temperature": 0.2,
            "web_search_options": {"search_context_size": "low"},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    d = r.json()
    citations = d.get("citations") or []
    if not citations:
        # 新しめのレスポンスでは search_results 側に入ることがある
        citations = [s.get("url") for s in (d.get("search_results") or []) if s.get("url")]
    return {
        "id": it["id"],
        "research": d["choices"][0]["message"]["content"],
        "citations": citations,
        "usage": d.get("usage", {}),
    }


# ---------------- Stage2: Claude Haiku 4.5 ----------------

CATEGORIES = [
    "業務効率化", "文書・資料作成", "データ整理・分析", "顧客対応・営業",
    "採用・人事", "経理・請求", "情報共有・ナレッジ", "ツール選定・導入",
]

# 出典の中立性を機械判定するための材料。
# 【なぜ機械判定か・2026-07-15の試走で判明】
# Stage2に quality_score を自己採点させたら3件とも78点（分散ゼロ）で、低品質を弾く
# シグナルとして機能しなかった。さらにSonarが「EC Copy AIが最適」の根拠として
# EC Copy AI自身のブログを引いており、それをそのまま source_url に採用していた。
# モデルの自己申告は当てにせず、URLのドメインという動かせない事実で採点する。
PUBLIC_SUFFIXES = (".go.jp", ".lg.jp", ".ac.jp")
OFFICIAL_DOCS = {
    "support.google.com", "workspace.google.com", "learn.microsoft.com",
    "support.microsoft.com", "help.openai.com", "platform.openai.com",
    "docs.anthropic.com", "support.anthropic.com", "help.notion.so",
    "www.notion.so", "help.zapier.com", "www.make.com", "docs.dify.ai",
    "developers.line.biz", "support.canva.com",
}
MEDIA = {
    "www.itmedia.co.jp", "atmarkit.itmedia.co.jp", "www.nikkei.com",
    "xtech.nikkei.com", "www.impress.co.jp", "cloud.watch.impress.co.jp",
    "toyokeizai.net", "diamond.jp", "www.publickey1.jp", "zenn.dev",
    "qiita.com",
}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# LINEはマークダウンを解釈しない。`**強調**` はアスタリスクがそのまま画面に出る。
# 「装飾を使うな」と指示しても混入するので、モデルの遵守を当てにせず機械検出する。
MD_PATTERNS = (
    (r"\*\*", "太字(**)"),
    (r"^#{1,6}\s", "見出し(#)"),
    (r"^\s*[-*+]\s", "箇条書き(-/*)"),
    (r"\[[^\]]+\]\([^)]+\)", "リンク記法"),
    (r"^\s*>\s", "引用(>)"),
    (r"`", "コード記法(`)"),
)


def detect_markdown(text):
    """answer に残ったマークダウン装飾を検出して名称のリストを返す。"""
    hits = []
    for pat, name in MD_PATTERNS:
        if re.search(pat, text or "", re.M):
            hits.append(name)
    return hits


def classify_source(url, tools):
    """source_url の素性を判定して (tier, スコア加減点) を返す。

    vendor_self = 推薦したツール自身のサイトを根拠にしている状態。
    「自社が自社を最適と書いた記事」を中立メディアが引くのは信頼性を毀損するため、
    最も重く減点する。ドメインのラベルが推薦ツール名に含まれるかで検出する。
    """
    url = (url or "").strip()
    if not url:
        return "none", -15
    host = urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    if not host:
        return "none", -15

    label = _norm(host.split(".")[0])
    if len(label) >= 4:
        for t in tools or []:
            nt = _norm(t)
            if nt and len(nt) >= 4 and (label in nt or nt in label):
                return "vendor_self", -30

    if host.endswith(PUBLIC_SUFFIXES):
        return "public", 15
    if host in OFFICIAL_DOCS or ("www." + host) in OFFICIAL_DOCS:
        return "official_doc", 10
    if host in MEDIA or ("www." + host) in MEDIA:
        return "media", 8
    return "unknown", -8

HAIKU_SYS = f"""あなたは日本の中小企業向けAI活用メディア「SHERPA」のFAQ編集者です。
業務課題とリサーチ結果を渡すので、読者がそのまま行動に移せるFAQを1件作ります。

【読者は誰か・ここを外すと全部無駄になる】
読者は**AIリテラシーが低い中小企業の経営者**です。ITの専門家ではありません。
この原稿はLINEのチャットボット(Hermes)の接客で読まれます。以下を厳守すること:
- **専門用語をそのまま使わない。** CVR・プロンプト・OCR・API・CSV・SaaS等は、
  使うなら初出で必ず一言の言い換えを添える(例:「CSV(表計算ソフトで開ける一覧データ)」)。
  言い換えられないなら、その用語を使わずに書き直す。
- **マークダウンの装飾を一切使わない。** LINEでは `**太字**` は太字にならず、
  アスタリスクがそのまま画面に出て読者を混乱させる。`**` `##` `-` による箇条書き記号、
  リンク記法は禁止。強調したいときは語順と言い切りで表現する。
- 箇条書きが要るときは「1つ目は〜。2つ目は〜。」のように文章で列挙するか、
  行頭に全角の「・」を置く。それ以外の記号は使わない。
- **2〜3文ごとに改行して段落を分ける。** LINEの画面は狭く、改行のない長文は
  壁のように見えて読み飛ばされる。話題が変わる箇所で必ず空行を入れること。
- 一文を短くする。役員会の資料ではなく、スマホの画面で読まれる。
- 「まず何をすればいいか」を最初の1〜2文で言い切る。読者は結論だけ知りたい。

SHERPAは特定ベンダーから独立した中立メディアです。以下は絶対に守ること:
- **単一の製品を「最適」「最も適合」「一択」と断定しない。** 必ず2つ以上の選択肢を挙げ、
  「どういう条件ならどれを選ぶか」という判断軸を読者に渡す。読者の環境は千差万別であり、
  リサーチ結果だけで一社に決め打ちできる根拠はない。
- リサーチ結果の出典にはベンダー自身が自社製品を推した記事が混ざる。それを根拠に
  「この製品が最適」と書くと、SHERPAが宣伝媒体になる。推奨の断定には使わないこと。
- **source_url は、推薦したツールの提供元自身のサイトを避ける。** 公的機関(go.jp等)・
  中立メディア・公式ドキュメントを優先する。適切なものが無ければ空文字にしてよい。
  無理に埋めるより空の方が良い。
- 価格は変動する。書く場合は「2026年7月時点」等の但し書きか「月額数千円程度」の
  粒度に留め、確定的な金額の断言を避ける。

出力は次のキーを持つJSONオブジェクトのみ。前置き・後書き・コードフェンスは書かないこと。
{{
  "category": {CATEGORIES} のいずれか1つ,
  "question": "経営者が実際に口にしそうな自然な疑問文。40〜60字程度。専門用語を使わない",
  "answer": "300〜500字。装飾記号なしのプレーンテキスト。結論から書き、具体的なツール名と手順を含める。一般論で逃げない",
  "tools_recommended": ["answer内で挙げた製品・サービス名の配列。正式名称で。無ければ空配列"],
  "source_url": "answerの根拠として最も適切なURLを1つ。該当が無ければ空文字",
  "content_score": 0〜100の整数
}}

content_scoreは**中身の具体性だけ**を採点する（出典の信頼性は別途機械判定するので考慮不要）:
- 90以上: 具体的なツール名・実行手順・費用感が揃い、読者が明日試せる
- 70〜89: ツール名と手順はあるが、費用感か手順の粒度のどちらかが粗い
- 50〜69: 方向性は正しいが具体性に欠け、読者が次の一歩を踏み出せない
- 50未満: リサーチ結果が乏しく、一般論しか書けなかった

**必ず上下に振ること。** リサーチ結果の厚さは案件ごとに大きく違うのに全件同じ点数が
付くなら、それは採点を放棄している。素材が薄ければ迷わず50未満を付けよ。低いスコアは
後段のレビューで弾くための正しいシグナルであり、失点ではない。"""


def haiku_prompt(it, s1):
    parts = [f"【課題】{it['title']}"]
    for label, key in (("業種", "industry"), ("部署", "dept"),
                       ("具体シーン", "scene"), ("制約条件", "constraint_"),
                       ("痛みの深刻度", "severity"), ("痛みの頻度", "freq")):
        if it.get(key):
            parts.append(f"【{label}】{it[key]}")
    parts.append(f"\n【リサーチ結果】\n{s1['research']}")
    if s1.get("citations"):
        parts.append("\n【出典候補】\n" + "\n".join(f"- {u}" for u in s1["citations"][:8]))
    parts.append("\n上記からFAQを1件作り、JSONのみを出力してください。")
    return "\n".join(parts)


def run_stage2(client, model, it, s1):
    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=HAIKU_SYS,
        messages=[{"role": "user", "content": haiku_prompt(it, s1)}],
    )
    # content[0] を直接読まない。thinking を返すモデル(Sonnet 5等)では先頭が
    # ThinkingBlock になり .text が無い。type=="text" のブロックだけを拾う。
    text = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    if not text.strip():
        raise ValueError("テキストブロックが空")
    faq = extract_json(text)
    faq["id"] = it["id"]
    faq["source_title"] = it["title"]
    faq["notion_status"] = it.get("status") or ""
    if faq.get("category") not in CATEGORIES:
        faq["category"] = "業務効率化"

    try:
        content = max(0, min(100, int(faq.get("content_score", 0))))
    except (TypeError, ValueError):
        content = 0
    faq["content_score"] = content

    tools = faq.get("tools_recommended") or []
    if not isinstance(tools, list):
        tools = []
    faq["tools_recommended"] = tools
    tier, adj = classify_source(faq.get("source_url"), tools)
    faq["source_tier"] = tier
    faq["source_adjust"] = adj

    md = detect_markdown(faq.get("answer", ""))
    faq["markdown_leaks"] = md
    # LINEに装飾が漏れると読者の画面に記号が出る。1種類でも残っていれば要修正。
    md_adj = -10 if md else 0
    faq["markdown_adjust"] = md_adj

    # 最終スコア = 中身の具体性(モデル判定) + 出典の素性(コード判定) + 装飾漏れ(コード判定)。
    # コード側で持つことで、モデルが甘く付けても vendor_self や装飾漏れは必ず沈む。
    faq["quality_score"] = max(0, min(100, content + adj + md_adj))
    faq["_model"] = model
    faq["_usage"] = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
    return faq


# ---------------- pipeline ----------------

def process(it, outdir, pk, client, model, tag, retries=3):
    """1件を Stage1→Stage2 まで通す。完了済みはファイル存在でスキップ。

    Stage2 の出力は モデル別ディレクトリ に分ける。同じ場所に書くと、モデルを
    haiku→sonnet に切り替えた時にファイルの存在でスキップされ、新モデルが走らない。
    Stage1(Sonar)の結果はモデル非依存なので共有し、切替時に再課金しない。
    """
    s1p = outdir / "stage1" / f"{it['id']}.json"
    s2p = outdir / "stage2" / tag / f"{it['id']}.json"
    if s2p.is_file():
        return "skip", json.loads(s2p.read_text(encoding="utf-8"))

    last = None
    for attempt in range(retries):
        try:
            if s1p.is_file():
                s1 = json.loads(s1p.read_text(encoding="utf-8"))
            else:
                s1 = run_sonar(it, pk)
                s1p.write_text(json.dumps(s1, ensure_ascii=False, indent=2), encoding="utf-8")
            faq = run_stage2(client, model, it, s1)
            s2p.write_text(json.dumps(faq, ensure_ascii=False, indent=2), encoding="utf-8")
            return "ok", faq
        except Exception as e:  # noqa: BLE001 — 1件の失敗で全体を止めない
            last = e
            time.sleep(2 ** attempt * 3)
    say(f"  NG [{it['id']}] {it['title'][:30]} — {type(last).__name__}: {last}")
    return "fail", {"id": it["id"], "title": it["title"], "error": f"{type(last).__name__}: {last}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=str(pathlib.Path.home() / "Desktop" / "faq_candidates"))
    ap.add_argument("--limit", type=int, default=0, help="先頭N件だけ処理（0=全件）")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default="haiku", choices=sorted(MODELS),
                    help="Stage2のモデル。出力は stage2/<model>/ に分かれる")
    ap.add_argument("--dry-run", action="store_true", help="APIを叩かず対象件数のみ表示")
    args = ap.parse_args()
    tag, model = args.model, MODELS[args.model]

    load_env()
    pk = os.environ.get("PERPLEXITY_API_KEY")
    ak = os.environ.get("ANTHROPIC_API_KEY")
    outdir = pathlib.Path(args.outdir)
    items = json.loads((outdir / "_input_issues.json").read_text(encoding="utf-8"))
    if args.limit:
        items = items[:args.limit]

    if args.dry_run:
        done = sum(1 for it in items if (outdir / "stage2" / tag / f"{it['id']}.json").is_file())
        say(f"対象 {len(items)}件 / 処理済み {done}件 / 残り {len(items) - done}件")
        say(f"推定コスト: 約 ${(len(items) - done) * 0.013:.2f}")
        return 0
    if not pk:
        say("PERPLEXITY_API_KEY が未設定（~/.hermes/.env を確認）"); return 2
    if not ak:
        say("ANTHROPIC_API_KEY が未設定（~/.hermes/.env を確認）"); return 2

    (outdir / "stage1").mkdir(parents=True, exist_ok=True)
    (outdir / "stage2" / tag).mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic(api_key=ak)
    say(f"Stage2モデル: {model} / 対象 {len(items)}件 / 並列 {args.workers}")

    results, counts = [], {"ok": 0, "skip": 0, "fail": 0}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process, it, outdir, pk, client, model, tag): it for it in items}
        for i, f in enumerate(as_completed(futs), 1):
            status, faq = f.result()
            counts[status] += 1
            if status != "fail":
                results.append(faq)
            if i % 10 == 0 or i == len(items):
                el = time.time() - t0
                say(f"  {i}/{len(items)} 完了 — ok={counts['ok']} skip={counts['skip']} "
                    f"fail={counts['fail']} / {el/60:.1f}分経過")

    results.sort(key=lambda x: -x.get("quality_score", 0))
    final = outdir / f"faq_candidates_{tag}.json"
    final.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    say(f"\n生成 {len(results)}件 → {final}")
    say(f"内訳: 新規 {counts['ok']} / スキップ {counts['skip']} / 失敗 {counts['fail']}")
    if results:
        scores = [r.get("quality_score", 0) for r in results]
        say(f"quality_score: 平均 {sum(scores)/len(scores):.1f} / "
            f"最高 {max(scores)} / 最低 {min(scores)}")
        for lo, hi in ((90, 101), (70, 90), (50, 70), (0, 50)):
            n = sum(1 for s in scores if lo <= s < hi)
            say(f"  {lo:3d}-{hi-1:3d}: {n:4d}件 {'#' * round(n / max(len(scores), 1) * 40)}")
        say("出典の素性:")
        for tier, n in Counter(r.get("source_tier", "?") for r in results).most_common():
            say(f"  {tier:12s}: {n:4d}件")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
