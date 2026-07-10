# JGI（ジャングルジム株式会社）— ミッション & インフラ設計思想

## ミッション
「気づきのきっかけを提供する」

## 事業
AIオンボーディング事業（組織のAIネイティブ化支援）
- Base44世界アンバサダー65名中の1人（国内初・V044 Ambassador）
- 対象顧客：SMB（中小企業）

### 2つの独立商品ライン
1. **組織向けAIオンボーディング（4層）**
   - High: Claude Code Edition（千葉さん・浅津さん担当）
   - Mid: Base44 Edition（HEY主導）
   - Low: WorkRun Edition（リセール10%）
   - Extra: 成功報酬型AI社員
2. **AI Worker Pass**（個人向けAIメンバーシップ、独立製品ライン）

## なぜこのインフラを作ったのか

### 原体験
2016〜17年、HDDのデータ破損で復旧に多大な時間とコストを失った。

### 設計思想の根底
- **共有可能であること**：ローカルに閉じる構成を嫌う
- **レジリエンス**：資産が失われないこと。誰が欠けても1日でリカバリできる組織
- 正本は常にクラウド（Notion/Box）に置く
- SOPはNotion集約。個人の記憶に依存しない

### 事業的文脈
自社でこのインフラを実践・証明することで「これが今後のスタンダード」として
AIオンボーディング事業の説得力にする。

## アカウント・環境情報

### デプロイ
- Vercel: dev.udlr.jp / ai.udlr.jp / lab.udlr.jp

### クラウド同期
- Box / Google Drive
- アカウント: hey@ / hello@ / a.egashira@ / egashira@deac

### Claudeアカウント
- メイン: hey@udlr.jp
- サブ: hello@udlr.jp

### Notion主要DB
- ハンドオフDB: 27e1a509-0fb5-4a07-824e-799985d70a3f
- TaskBoard: bb4246510e8747ca88df0c4de58aa98d
- Morning Vision: fb00fe5b8a494a5e83f17fad847a3445
- claudecode_devインデックス: 344505f6b5a580f99f4fea109de871ee
