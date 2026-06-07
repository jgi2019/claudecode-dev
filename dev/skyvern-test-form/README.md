# Skyvern CAPTCHA検証テストフォーム

ブラウザ自動化ツール（Skyvern / Claude Computer Use）のCAPTCHA突破力と、日本式の確認画面（同一URL・state切替）対応力を検証するための8パターンのテストフォームサイト。

## 8パターン

| # | path | CAPTCHA | 確認画面 |
|---|------|---------|---------|
| 1 | `/none-direct` | なし | なし |
| 2 | `/none-confirm` | なし | あり |
| 3 | `/v2-direct` | reCAPTCHA v2 | なし |
| 4 | `/v2-confirm` | reCAPTCHA v2 | あり |
| 5 | `/v3-direct` | reCAPTCHA v3 | なし |
| 6 | `/v3-confirm` | reCAPTCHA v3 | あり |
| 7 | `/hcaptcha-direct` | hCaptcha | なし |
| 8 | `/hcaptcha-confirm` | hCaptcha | あり |

- `/` : 8パターンへのリンク一覧
- `/logs` : 送信ログ閲覧（成功/失敗マトリクス＋テーブル、パターン絞り込み）
- `/complete` : 送信完了画面

確認画面は**同一URL内でReact stateによるDOM差し替え**で実装（ページ遷移・URL変更なし）。

## 技術スタック

- Next.js 16 (App Router) / TypeScript / Tailwind CSS v4
- `react-google-recaptcha` (v2) / `react-google-recaptcha-v3` (v3) / `@hcaptcha/react-hcaptcha`

## セットアップ

```bash
npm install
cp .env.example .env.local   # 各CAPTCHAのサイトキー/シークレットを記入
npm run dev
```

CAPTCHAのサイトキー（`NEXT_PUBLIC_*`）が未設定の場合、該当パターンのページにエラーメッセージを表示します（クラッシュしません）。

## 環境変数

`.env.example` 参照。値は `.env.local` および Vercelダッシュボードに手動設定すること（コードにハードコードしない）。

## ログ保存

開発/検証用途のため `/tmp/submission-logs.json` に保存（Vercel serverlessでは揮発）。メモリ内フォールバックあり。本番用途ではない。

## デプロイ

```bash
vercel --prod
# ドメインは Vercelダッシュボードで vibing.jp を紐付け
```
