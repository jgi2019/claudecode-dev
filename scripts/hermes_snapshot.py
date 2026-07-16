#!/usr/bin/env python3
"""Hermes system_prompt 日次スナップショット

テナント別 system_prompt（AIWPの売り「学習データ継続保証」の実体＝知の資本）を
Supabase REST から取得し、リポ内 ops/snapshots/hermes/system_prompts.json に
書き出して git commit する。日次cron想定。

実行（VPS・cron）:
  python3 ~/aiwp/scripts/hermes_snapshot.py --repo <claudecode-devチェックアウト> --commit --push
実行（ローカル・手動確認）:
  python3 scripts/hermes_snapshot.py            # 取得と書き出しのみ（commitしない）

必要env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY（~/.hermes/.env から自動読込。値はログに出さない）
出力: <repo>/ops/snapshots/hermes/system_prompts.json（履歴はgitが持つ。ファイルは常に1本）
安全策:
  - テナント数が前回スナップショットより減った場合は上書きせず異常終了（--force で解除）。
    本体DBが壊れた日に、正常なバックアップまで壊れた内容で上書きする事故を防ぐ。
  - 差分がなければ commit しない（冪等）。
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

SNAPSHOT_REL = "ops/snapshots/hermes/system_prompts.json"


def load_env(path=None):
    """~/.hermes/.env から KEY=VALUE を読む。値はログに出さない。"""
    p = pathlib.Path(path or (pathlib.Path.home() / ".hermes" / ".env"))
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def fetch_tenants(url, key):
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/tenants"
        "?select=id,name,system_prompt,created_at&order=created_at.asc",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("REST応答がリストでない")
    for row in data:
        if not row.get("id") or not (row.get("system_prompt") or "").strip():
            raise ValueError(f"system_prompt欠落テナントあり: id={row.get('id')}")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(pathlib.Path(__file__).resolve().parent.parent),
                    help="スナップショットを置くgitリポ（既定: このスクリプトのあるリポ）")
    ap.add_argument("--commit", action="store_true", help="差分があればgit commitする")
    ap.add_argument("--push", action="store_true", help="commit後にorigin mainへpushする")
    ap.add_argument("--force", action="store_true", help="テナント数減少時も上書きを許可")
    args = ap.parse_args()

    load_env()
    url = os.environ.get("SUPABASE_URL") or ""
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 未設定（~/.hermes/.env を確認）")
        return 1

    tenants = fetch_tenants(url, key)
    out = pathlib.Path(args.repo) / SNAPSHOT_REL

    if out.exists() and not args.force:
        prev = json.loads(out.read_text())
        if len(tenants) < len(prev.get("tenants", [])):
            print(f"ERROR: テナント数減少 {len(prev['tenants'])}→{len(tenants)}。"
                  "本体DB異常の疑い。上書きしない（意図的なら --force）")
            return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": "supabase:tenants", "count": len(tenants), "tenants": tenants}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"OK: {len(tenants)}テナント → {out}")

    if args.commit:
        def git(*a, check=True):
            return subprocess.run(["git", "-C", args.repo, *a],
                                  capture_output=True, text=True, check=check)
        if not git("status", "--porcelain", SNAPSHOT_REL).stdout.strip():
            print("差分なし: commitしない")
            return 0
        git("add", SNAPSHOT_REL)
        from datetime import date
        git("commit", "-m",
            f"ops(snapshot): hermes system_prompts {date.today().isoformat()} ({len(tenants)} tenants)")
        print("commit完了")
        if args.push:
            git("push", "origin", "main")
            print("push完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
