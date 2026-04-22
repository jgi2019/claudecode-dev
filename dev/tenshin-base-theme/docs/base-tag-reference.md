# BASE テンプレートタグ チートシート

点心丹波篠山EC実装時の参照用。公式ドキュメント（https://docs.thebase.in/template/）から、本プロジェクトで使用する範囲を抜粋。

---

## 基本構文

BASEテンプレートは HTML + 独自タグの組み合わせ。独自タグには2種類ある：

- **変数タグ**：`{IndexPageURL}` のように単独で値を出力
- **ブロックタグ**：`{block:XXX}...{/block:XXX}` のように範囲を持つ（if文・ループ文の役割）

**重要な制約**：1つのテーマファイルで全ページを管理する。ページごとの出し分けは条件分岐タグで行う。

---

## 条件分岐タグ（if ページ）

### 本プロジェクトで使うもの

| タグ | 説明 | 本PJでの用途 |
|---|---|---|
| `{block:IndexPage}` | トップページ | LP本体を囲む |
| `{block:ItemPage}` | 商品詳細ページ | 商品詳細レイアウト |
| `{block:AboutPage}` | Aboutページ | ショップ説明ページ |
| `{block:NotIndexPage}` | トップページ以外 | 共通ヘッダー/フッター調整用 |

### 参考（今回使わないが存在するもの）

- `{block:ContactPage}` お問い合わせ
- `{block:PrivacyPage}` プライバシーポリシー
- `{block:LawPage}` 特定商取引法
- `{block:BlogPage}` Blogページ（Blog App必要）
- `{block:LoadItemsPage}` 商品一覧の追加ロード（ページング用）

---

## URL系変数タグ

### 必須タグ（非表示禁止）

フッターに必ず含めること。削除するとBASE規約違反。

| タグ | 説明 |
|---|---|
| `{ContactPageURL}` | **[必須]** お問い合わせページのURL |
| `{PrivacyPageURL}` | **[必須]** プライバシーポリシーページのURL |
| `{LawPageURL}` | **[必須]** 特定商取引法に基づく表記ページのURL |

### その他のURL

| タグ | 説明 |
|---|---|
| `{IndexPageURL}` | トップページのURL |
| `{ItemPageURL}` | 商品詳細ページのURL（商品ループ内で使う） |
| `{AboutPageURL}` | AboutページのURL |
| `{SearchPageURL}` | 検索フォームのURL |

---

## 商品タグ

### 商品ループ

```html
{block:Items}
  <!-- 商品1件ごとに繰り返される。最大24個 -->
  <a href="{ItemPageURL}">
    <img src="{ItemImage1URL-500}" alt="{ItemTitle}">
    <p>{ItemTitle}</p>
    <p>¥{ItemPrice}</p>
  </a>
{/block:Items}
```

### 本PJで使う商品情報変数

| タグ | 説明 |
|---|---|
| `{ItemId}` | 商品のID |
| `{ItemTitle}` | 商品の名前 |
| `{ItemPrice}` | 商品の価格 |
| `{ItemDetail}` | 商品の説明（改行brタグ変換あり） |
| `{ItemImage1URL-500}` | 商品画像1の500pxサイズ |
| `{ItemImage1URL-640}` | 商品画像1の640pxサイズ |
| `{ItemImage1URL-1280}` | 商品画像1の1280pxサイズ |
| `{ItemPageURL}` | その商品の詳細ページURL |

### 画像サイズの選択肢

`{ItemImage1URL-XXX}` の XXX に以下のサイズ指定可能：
`76 / 146 / 174 / 300 / 500 / 640 / 1280`

**本PJの推奨**：
- 商品詳細ページ：`1280` または `640`
- LP内の商品カード：`500`
- サムネ的な小さい表示：`300`

### 商品関連の条件分岐

| タグ | 説明 |
|---|---|
| `{block:HasItems}` | 商品がある |
| `{block:NoItems}` | 商品がない（空ショップ対策） |
| `{block:HasItemStock}` | 商品の在庫がある |
| `{block:NoItemStock}` | 商品の在庫がない（売り切れ表示用） |
| `{block:ItemImage1}` | 商品画像1がある |
| `{block:NoItemImage1}` | 商品画像1がない |

---

## イテレータ（ループ内の位置判定）

商品ループ内で、何番目の商品かによって出し分けができる。

| タグ | 説明 |
|---|---|
| `{block:Item1}` | 商品ループの1番目 |
| `{block:Item2}` | 商品ループの2番目 |
| `{block:Item3}` | 商品ループの3番目 |
| `{block:Odd}` | 奇数番目 |
| `{block:Even}` | 偶数番目 |

**本PJでの活用例**：「自宅で愉しむ」セクションで、最初の3商品だけ大きく表示したい場合。

```html
{block:Items}
  {block:Item1}<!-- 1番目だけ大きく --> <div class="featured">...</div>{/block:Item1}
  {block:Item2}<div class="normal">...</div>{/block:Item2}
  {block:Item3}<div class="normal">...</div>{/block:Item3}
{/block:Items}
```

---

## ショップ情報タグ（要別章確認）

以下は公式ドキュメントの「ショップ」章に詳細あり。実装時に必要になったら都度確認：

- ショップ名
- ロゴ画像
- ショップ説明
- 営業情報

**参照URL**：https://docs.thebase.in/template/syntax/shop

---

## ページ構成とURL

本プロジェクトで生成されるページのURL構造：

| ページ | URL |
|---|---|
| TOP | `https://tenshints.official.ec/` |
| 商品詳細 | `https://tenshints.official.ec/items/[商品ID]` |
| About | `https://tenshints.official.ec/about` |
| お問い合わせ | `https://thebase.in/inquiry/tenshints.official.ec` |
| プライバシーポリシー | `https://tenshints.official.ec/privacy` |
| 特定商取引法 | `https://tenshints.official.ec/law` |
| カート以降 | カスタマイズ不可 |

---

## 禁止事項（BASE公式）

1. 意図的にサーバーに負荷をかける編集
2. 必須タグを非表示にすること、およびタグの改変

---

## 本プロジェクト固有の実装方針

### テーマの骨組み

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <!-- 共通メタ情報 -->
</head>
<body>

  <!-- 全ページ共通ヘッダー -->
  <header>
    <a href="{IndexPageURL}">ロゴ</a>
  </header>

  {block:IndexPage}
    <!-- トップページ（LP）の中身 -->
    <!-- HERO / コピー / 商品写真 / 2カラム / 店舗情報 -->
    
    <!-- 商品一覧が必要な箇所 -->
    {block:Items}
      {block:Item1}...{/block:Item1}
      {block:Item2}...{/block:Item2}
      {block:Item3}...{/block:Item3}
    {/block:Items}
  {/block:IndexPage}

  {block:ItemPage}
    <!-- 商品詳細ページ -->
  {/block:ItemPage}

  {block:AboutPage}
    <!-- Aboutページ -->
  {/block:AboutPage}

  <!-- 全ページ共通フッター（必須タグ含む） -->
  <footer>
    <a href="{ContactPageURL}">お問い合わせ</a>
    <a href="{PrivacyPageURL}">プライバシーポリシー</a>
    <a href="{LawPageURL}">特定商取引法に基づく表記</a>
  </footer>

</body>
</html>
```

### 画像ファイルの扱い

- **テーマ用画像**（ロゴ、HERO背景、装飾など）→ BASE HTML編集Appの「ファイルアップローダー」にアップロード、独自タグでURL取得
- **商品画像** → 商品登録時にBASE管理画面からアップロード、`{ItemImage1URL-XXX}` で取得

### モバイル対応

- BASE設定「デフォルトのモバイルテーマを使用」を **OFF** にする
- これにより、PCとSPで同じHTMLが配信され、CSSのメディアクエリでレスポンシブ対応できる

---

## 参考リンク

- 公式ドキュメント入口：https://docs.thebase.in/template/
- ページ構成の仕様：https://docs.thebase.in/template/directory/page
- テンプレートタグ一覧：https://docs.thebase.in/template/syntax/disable
- ページ条件分岐：https://docs.thebase.in/template/syntax/page
- 商品タグ：https://docs.thebase.in/template/syntax/item
- イテレータ：https://docs.thebase.in/template/syntax/iterator
