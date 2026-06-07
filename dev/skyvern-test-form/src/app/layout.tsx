import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Skyvern CAPTCHA検証フォーム",
  description: "ブラウザ自動化ツールのCAPTCHA突破力・確認画面対応力を検証するテストフォーム",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className="h-full antialiased">
      <body className="min-h-full bg-gray-50 text-gray-900">{children}</body>
    </html>
  );
}
