# claudecode-dev

このリポジトリは、江頭淳（JGI所属）のAI活用開発環境の正本です。ローカルは揮発前提、GitHubを真実の源（Single Source of Truth）として運用します。

---

## ローカル環境

### 正本フォルダ

作業ディレクトリは以下の場所に配置：
~/Desktop/**claudecode_dev/

先頭の `**`（アスタリスク2つ）はFinderで並び順を最上位にするためのプレフィックスです。**フォルダ名とGitHubのリポジトリ名（`claudecode-dev`、ハイフン）は一致していない**点に注意してください。

### このリポジトリを別環境で clone する時の注意

デフォルトのフォルダ名（`claudecode-dev`）ではなく、**必ず正本フォルダ名を指定して clone** してください：

```bash
cd ~/Desktop
git clone https://github.com/jgi2019/claudecode-dev.git "**claudecode_dev"
```

**間違った clone 方法**：

```bash
# ❌ これをやると ~/Desktop/claudecode-dev/ という別フォルダが作られ、
#   CLAUDE.md記載の正本（~/Desktop/**claudecode_dev/）と分離してしまう
git clone https://github.com/jgi2019/claudecode-dev.git
```

もし `~/Desktop/claudecode-dev/`（ハイフン版）が発生した場合、それは誤生成です。正本（`~/Desktop/**claudecode_dev/`）へ資産を統合してから削除してください。

---

## サブモジュール

このリポジトリは以下のサブモジュールを含みます：

- `mcp-servers/tldv-mcp-server/` — https://github.com/tldv-public/tldv-mcp-server

clone 時にサブモジュールも取得する場合：

```bash
git clone --recurse-submodules https://github.com/jgi2019/claudecode-dev.git "**claudecode_dev"
```

既に clone 済みの環境で後からサブモジュールを取得：

```bash
git submodule update --init --recursive
```

---

## 運用ルール

詳細は `CLAUDE.md` を参照してください。主なルール：

- ローカルは揮発前提、重要情報はGitHub or Notionへ
- 生成物は作成・編集のたびに `git add & commit & push`
- 作業は常に正本フォルダ（`~/Desktop/**claudecode_dev/`）配下で完結

---

## ディレクトリ構成
**claudecode_dev/
├── CLAUDE.md           # AIへの運用ルール
├── README.md           # このファイル
├── .gitmodules         # サブモジュール定義
├── ai/                 # AI関連の設計資料
│   └── blueprint/      # サービス設計図
├── dev/                # 開発プロジェクト群
│   └── tenshin-base-theme/  # 点心丹波篠山EC (BASE)
└── mcp-servers/        # MCPサーバー群
└── tldv-mcp-server/     # submodule: tl;dv連携