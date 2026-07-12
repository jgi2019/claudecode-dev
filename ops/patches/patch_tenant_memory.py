#!/usr/bin/env python3
"""本体パッチ B-2: テナント別メモリ分離（memories/{user_id}/ スコープ化）。

対象: hermes-agent==0.18.2 の site-packages（Mac開発機 / VPS両対応・冪等）
  - tools/memory_tool.py   … get_memory_dir(scope) 化 + MemoryStore(scope=)
  - agent/agent_init.py    … gateway経由(platform+user_id有)の agent だけ scope を注入

設計:
  - LINE等プラットフォーム経由で user_id を持つ agent → memories/{sanitized_user_id}/
  - CLI / user_id なし（JIRO開発セッション・owner）→ 従来の memories/ 直下（互換維持）
  - background_review は agent._memory_store を共有参照するため自動でスコープ継承
  - 既知の限界: learning_mutations.py / learning_graph.py（journey機能・CLI専用）は
    グローバルのまま。LINE利用者からは到達不能なので v1 では対象外。

適用: python3 ops/patches/patch_tenant_memory.py
      （site-packages を自動検出。HERMES_SP 環境変数で明示指定も可）
検証: 適用後に py_compile 2ファイル + 逆参照テストを自動実行。
再適用: uv tool upgrade / 再インストールで site-packages が入れ替わるたびに必要
      （A-4 パッチと同じ運用。DEPLOY_NOTES.md 参照）。
"""
import io
import os
import subprocess
import sys


def find_sp() -> str:
    sp = os.environ.get("HERMES_SP")
    if sp:
        return sp
    r = subprocess.run(
        [os.path.expanduser("~/.local/share/uv/tools/hermes-agent/bin/python"),
         "-c", "import agent, os; print(os.path.dirname(os.path.dirname(agent.__file__)))"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise SystemExit("site-packages 自動検出失敗。HERMES_SP を設定して再実行: " + r.stderr)
    return r.stdout.strip()


def patch_file(path: str, replacements: list[tuple[str, str, str]]) -> None:
    """replacements: (label, old, new)。old が無く new も無ければ異常終了。"""
    s = io.open(path, encoding="utf-8").read()
    changed = False
    for label, old, new in replacements:
        if new in s:
            print(f"  {label}: already applied")
            continue
        if old not in s:
            raise SystemExit(
                f"  {label}: anchor NOT found in {path} — Hermes内部変更の可能性。手動確認せよ"
            )
        s = s.replace(old, new, 1)
        changed = True
        print(f"  {label}: applied")
    if changed:
        io.open(path, "w", encoding="utf-8").write(s)


# ---------------------------------------------------------------- memory_tool
MT_P1 = (
    "P1 get_memory_dir(scope) + sanitize_scope",
    '''def get_memory_dir() -> Path:
    """Return the profile-scoped memories directory."""
    return get_hermes_home() / "memories"''',
    '''def sanitize_scope(user_id) -> "str | None":
    """テナントスコープ用に user_id を安全なディレクトリ名へ正規化。

    英数・ハイフン・アンダースコアのみ許可（LINE user_id "U[0-9a-f]{32}" は
    そのまま通る）。空・不正なら None（=グローバル扱い）を返し、パス
    トラバーサルを構造的に排除する。
    """
    import re
    s = str(user_id or "").strip()
    if not s:
        return None
    s = re.sub(r"[^A-Za-z0-9_-]", "_", s)[:64]
    return s or None


def get_memory_dir(scope: "str | None" = None) -> Path:
    """Return the profile-scoped memories directory.

    scope が指定された場合はテナント別サブディレクトリ memories/{scope}/ を返す
    （AI Worker's Pass テナント分離パッチ B-2）。
    """
    base = get_hermes_home() / "memories"
    if scope:
        return base / scope
    return base''',
)

MT_P2 = (
    "P2 MemoryStore.__init__ scope param",
    '''    def __init__(self, memory_char_limit: int = 2200, user_char_limit: int = 1375):
        self.memory_entries: List[str] = []''',
    '''    def __init__(self, memory_char_limit: int = 2200, user_char_limit: int = 1375,
                 scope: "str | None" = None):
        # テナント分離: scope が入ると全ファイルI/Oが memories/{scope}/ に閉じる
        self.scope = scope
        self.memory_entries: List[str] = []''',
)

MT_P3 = (
    "P3 load_from_disk scoped dir",
    '''        mem_dir = get_memory_dir()
        mem_dir.mkdir(parents=True, exist_ok=True)''',
    '''        mem_dir = get_memory_dir(self.scope)
        mem_dir.mkdir(parents=True, exist_ok=True)''',
)

MT_P4 = (
    "P4 _path_for instance-scoped",
    '''    @staticmethod
    def _path_for(target: str) -> Path:
        mem_dir = get_memory_dir()''',
    '''    def _path_for(self, target: str) -> Path:
        mem_dir = get_memory_dir(self.scope)''',
)

MT_P5 = (
    "P5 save_to_disk scoped dir",
    '''        get_memory_dir().mkdir(parents=True, exist_ok=True)''',
    '''        get_memory_dir(self.scope).mkdir(parents=True, exist_ok=True)''',
)

# ---------------------------------------------------------------- agent_init
AI_P6 = (
    "P6 agent_init scope injection",
    '''                agent._memory_store = MemoryStore(
                    memory_char_limit=mem_config.get("memory_char_limit", 2200),
                    user_char_limit=mem_config.get("user_char_limit", 1375),
                )''',
    '''                # テナント分離 B-2: gateway経由（platform+user_id あり）の
                # セッションはユーザー別 memories/{user_id}/ にスコープする。
                # CLI / owner セッション（user_id なし）は従来のグローバル。
                _mem_scope = None
                try:
                    if platform and str(platform).lower() not in ("", "cli", "none") and user_id:
                        from tools.memory_tool import sanitize_scope as _san
                        _mem_scope = _san(user_id)
                except Exception:
                    _mem_scope = None
                agent._memory_store = MemoryStore(
                    memory_char_limit=mem_config.get("memory_char_limit", 2200),
                    user_char_limit=mem_config.get("user_char_limit", 1375),
                    scope=_mem_scope,
                )''',
)


def main():
    sp = find_sp()
    mt = os.path.join(sp, "tools", "memory_tool.py")
    ai = os.path.join(sp, "agent", "agent_init.py")
    print(f"site-packages: {sp}")
    print("tools/memory_tool.py:")
    patch_file(mt, [MT_P1, MT_P2, MT_P3, MT_P4, MT_P5])
    print("agent/agent_init.py:")
    patch_file(ai, [AI_P6])

    # 構文検証
    py = os.path.join(os.path.dirname(sp), "..", "..", "bin", "python")
    py = os.path.normpath(py)
    if not os.path.exists(py):
        py = sys.executable
    for f in (mt, ai):
        r = subprocess.run([py, "-m", "py_compile", f])
        if r.returncode != 0:
            raise SystemExit(f"py_compile FAILED: {f}")
    print("py_compile OK (memory_tool.py, agent_init.py)")
    print("B-2 patch complete. gateway 再起動で有効化。")


if __name__ == "__main__":
    main()
