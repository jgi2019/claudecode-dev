import Link from 'next/link';
import { PATTERNS } from '@/lib/types';

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-12">
      <header className="mb-10">
        <h1 className="text-3xl font-bold text-gray-900">Skyvern CAPTCHA検証フォーム</h1>
        <p className="mt-2 text-sm text-gray-600">
          ブラウザ自動化ツール（Skyvern / Claude Computer Use）のCAPTCHA突破力と、
          日本式の確認画面（同一URL・state切替）対応力を検証する8パターンのテストフォームです。
        </p>
        <div className="mt-4">
          <Link
            href="/logs"
            className="inline-block rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
          >
            📊 送信ログを見る
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {PATTERNS.map((p, i) => (
          <Link
            key={p.id}
            href={p.path}
            className="block rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition hover:border-blue-400 hover:shadow-md"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
                {i + 1}
              </span>
              <span className="font-mono text-sm text-gray-500">{p.id}</span>
            </div>
            <h2 className="mb-3 text-base font-semibold text-gray-900">{p.label}</h2>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded bg-blue-100 px-2 py-1 text-blue-800">
                {p.captchaLabel}
              </span>
              <span className="rounded bg-amber-100 px-2 py-1 text-amber-800">
                確認画面: {p.hasConfirmScreen ? 'あり' : 'なし'}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
