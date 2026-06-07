import Link from 'next/link';
import ContactForm from './ContactForm';
import RecaptchaV3Provider from './RecaptchaV3Provider';
import { PATTERNS } from '@/lib/types';

interface Props {
  patternId: string;
}

// 8パターン共通のフォームページ枠。patternId からCAPTCHA種別・確認画面有無を解決する。
export default function FormPage({ patternId }: Props) {
  const pattern = PATTERNS.find((p) => p.id === patternId);

  if (!pattern) {
    return <div className="p-8">不明なパターン: {patternId}</div>;
  }

  const form = (
    <ContactForm
      captchaType={pattern.captchaType}
      hasConfirmScreen={pattern.hasConfirmScreen}
      patternId={pattern.id}
    />
  );

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-10">
      <div className="mb-6">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← トップに戻る
        </Link>
      </div>

      <div className="mb-8">
        <div className="mb-2 flex flex-wrap gap-2 text-xs">
          <span className="rounded bg-gray-800 px-2 py-1 font-mono text-white">{pattern.id}</span>
          <span className="rounded bg-blue-100 px-2 py-1 text-blue-800">{pattern.captchaLabel}</span>
          <span className="rounded bg-amber-100 px-2 py-1 text-amber-800">
            確認画面: {pattern.hasConfirmScreen ? 'あり' : 'なし'}
          </span>
        </div>
        <h1 className="text-2xl font-bold text-gray-900">お問い合わせ</h1>
        <p className="mt-1 text-sm text-gray-600">{pattern.label}</p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        {pattern.captchaType === 'recaptcha-v3' ? (
          <RecaptchaV3Provider>{form}</RecaptchaV3Provider>
        ) : (
          form
        )}
      </div>
    </main>
  );
}
