#!/usr/bin/env python3
"""既存オンボ完了テナントの system_prompt を、現行 wizard.build_system_prompt で再生成して更新する。

persona 更新（wizard.py の静的文言変更）を既存テナントへ反映するための保守スクリプト。
新規オンボは完了時に system_prompt を自動生成するため対象外。既存テナントは prompt が
tenants.system_prompt に凍結保存されているので、onboarding_answers から冪等に再生成する。

使い方（VPS上）:
  set -a; . ~/.hermes/.env; set +a
  python3 ~/aiwp/scripts/regen_system_prompts.py           # ドライラン（差分表示のみ・無変更）
  python3 ~/aiwp/scripts/regen_system_prompts.py --apply   # 実更新（更新前を backup_*.json に退避）

必要env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
出力先: --apply 時、更新前 system_prompt を ~/aiwp/scripts/backup_system_prompts_<epoch>.json に退避
安全策: 生成結果に MARKER（現行personaの目印）が無ければ異常としてスキップ、既存と同一なら無更新。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

PLUGIN_DIR = os.path.expanduser("~/aiwp/hermes-plugins/aiworkerpass-wizard")
sys.path.insert(0, PLUGIN_DIR)
import wizard  # noqa: E402  build_system_prompt を借りる

URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
APPLY = "--apply" in sys.argv
MARKER = "分岐1"  # 現行 persona（3分岐化）の目印。生成物の健全性チェックに使う。


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        URL + path,
        data=data,
        method=method,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode()
        return resp.status, (json.loads(raw) if raw else None)


def main():
    if not URL or not KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 未設定")
        sys.exit(1)
    _, rows = _req(
        "GET",
        "/rest/v1/tenants?select=line_user_id,name,onboarding_answers,onboarding_complete,system_prompt"
        "&onboarding_complete=eq.true",
    )
    rows = rows or []
    print(f"対象（オンボ完了）テナント: {len(rows)}件 / apply={APPLY}")
    backup, updated, skipped = [], 0, 0
    for t in rows:
        lid = t.get("line_user_id")
        nm = t.get("name") or "?"
        ans = t.get("onboarding_answers") or {}
        old = t.get("system_prompt") or ""
        try:
            new = wizard.build_system_prompt(ans)
        except Exception as e:  # noqa: BLE001
            print(f"  SKIP {nm}: build失敗 {e}")
            skipped += 1
            continue
        if not new or MARKER not in new:
            print(f"  SKIP {nm}: 生成結果に'{MARKER}'無し(異常)・len={len(new)}")
            skipped += 1
            continue
        if new == old:
            print(f"  = {nm}: 変化なし")
            continue
        print(f"  ~ {nm}: {len(old)}→{len(new)}字 更新{'(予定)' if not APPLY else ''}")
        backup.append({"line_user_id": lid, "name": nm, "system_prompt": old})
        if APPLY:
            q = urllib.parse.urlencode({"line_user_id": f"eq.{lid}"})
            s, _ = _req("PATCH", f"/rest/v1/tenants?{q}", {"system_prompt": new})
            if s in (200, 204):
                updated += 1
            else:
                print(f"    !! PATCH 失敗 status={s}")
                skipped += 1
    if APPLY and backup:
        bpath = os.path.expanduser(f"~/aiwp/scripts/backup_system_prompts_{int(time.time())}.json")
        with open(bpath, "w") as f:
            f.write(json.dumps(backup, ensure_ascii=False, indent=2))
        print(f"バックアップ: {bpath}")
    print(f"完了: 更新{updated} / スキップ{skipped}")


if __name__ == "__main__":
    main()
