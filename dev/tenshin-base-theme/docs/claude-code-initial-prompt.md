# Claude Code 初回プロンプト

以下を Claude Code に投げてください。そのままコピペでOK。

---

```
点心丹波篠山のEC（BASE）向けのテーマを実装します。

【プロジェクト概要】
- クライアント：GIN株式会社
- 店舗：点心 丹波篠山（兵庫県丹波篠山市）
- デプロイ先：BASE（https://tenshints.official.ec）のHTML編集App
- 初期商品：豚まん1商品のみ

【前提資料】
すべて docs/ 配下にあります。以下を最初に全て読んでください：
- docs/base-tag-reference.md：BASEテンプレートタグのチートシート
- docs/implementation-notes.md：実装方針メモ（デザイン方針・技術方針・制約）
- docs/design-pc.png：PC版デザインカンプ
- docs/design-sp.png：SP版デザインカンプ

【技術方針（要旨）】
- 1枚のindex.htmlでBASEの全ページを条件分岐で扱う
- 開発中はsrc/配下で分割管理、最終統合は後工程
- 外部ライブラリ不使用（バニラJS）
- モバイルファースト、HEROパララックスはPCのみ

【今回のタスク】
以下を順に実装してください：

1. docs/を全て読んで、現状を理解
2. 実装計画を提示（私の承認を得てから着手）
3. src/index.html：トップページ（LP）の骨組みを {block:IndexPage} 内に実装
4. src/style.css：PC/SP両対応のレスポンシブ
5. src/script.js：HEROパララックスのみ（モバイル・reduced-motion除外）
6. mock/preview.html：BASEタグをダミーデータで置換したローカルプレビュー

【現時点で実装するのはトップページのみ】
商品詳細ページ、Aboutページは後工程で扱います。

【制約（重要）】
- BASE必須タグ（ContactPageURL、PrivacyPageURL、LawPageURL）をフッターに必ず含める
- 意図的にサーバー負荷をかける実装は不可
- 画像アセットはsrc/assets/配下を参照（現時点では空の可能性あり、その場合はプレースホルダーで進める）

まずdocs/を全て読んで、実装計画を提示してください。計画に私が承認したら着手してください。
```

---

## 備考

- 画像アセットは作業進行中に随時 `src/assets/` に追加してください
- Claude Code が質問してきたら、都度このチャットで相談してください
- 本番BASE投入前に、mock/preview.html で見た目の最終確認をします
