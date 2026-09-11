"""Static contract check for JIRO AIOS session commands.

Run from repository root:
    python3 scripts/check_aios_session_contract.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "start": ROOT / ".claude/commands/start-session.md",
    "end": ROOT / ".claude/commands/end-session.md",
    "pj": ROOT / ".claude/commands/pj.md",
    "template": ROOT / ".claude/templates/aios-handoff-v0.2.yaml",
}

REQUIRED = {
    "start": [
        "project_id", "session_id", "operation_id", "read_versions",
        "approval", "last_edited_time", "Draft",
    ],
    "end": [
        "operation_id", "notification_receipts", "attempt_log",
        "failed_steps", "partial", "unknown", "simulation",
        "保存をやり直さず",
    ],
    "pj": ["AIOS開始契約", "project_id", "operation_id", "read_versions"],
    "template": [
        'schema_version: "0.2"', "handoff_id", "project_id",
        "operation_id", "attempt_log", "notification_receipts",
        "approval", "visibility",
    ],
}


def main() -> None:
    failures = []
    for name, path in FILES.items():
        if not path.exists():
            failures.append(f"{name}: missing {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [token for token in REQUIRED[name] if token not in text]
        if missing:
            failures.append(f"{name}: missing {', '.join(missing)}")

    if failures:
        raise SystemExit("\n".join(failures))

    print("AIOS session contract: OK")
    for name, path in FILES.items():
        print(f"- {name}: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
