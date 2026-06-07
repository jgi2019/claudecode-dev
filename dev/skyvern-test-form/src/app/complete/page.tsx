import Link from 'next/link';

export default async function CompletePage({
  searchParams,
}: {
  searchParams: Promise<{ pattern?: string }>;
}) {
  const { pattern } = await searchParams;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-xl flex-col items-center justify-center px-4 py-12 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
        <span className="text-3xl text-green-600">✓</span>
      </div>
      <h1 className="mb-2 text-2xl font-bold text-gray-900">送信が完了しました</h1>
      <p className="mb-1 text-sm text-gray-600">
        お問い合わせいただきありがとうございます。
      </p>
      {pattern ? (
        <p className="mb-8 text-xs text-gray-400">
          パターン: <span className="font-mono">{pattern}</span>
        </p>
      ) : (
        <div className="mb-8" />
      )}
      <div className="flex gap-3">
        <Link
          href="/"
          className="rounded border border-gray-300 bg-white px-5 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          トップに戻る
        </Link>
        <Link
          href="/logs"
          className="rounded bg-gray-900 px-5 py-2 text-sm font-medium text-white hover:bg-gray-700"
        >
          ログを見る
        </Link>
      </div>
    </main>
  );
}
