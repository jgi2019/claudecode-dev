'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useGoogleReCaptcha } from 'react-google-recaptcha-v3';
import { CATEGORIES, type CaptchaType, type FormData, type SubmitResponse } from '@/lib/types';
import ConfirmScreen from './ConfirmScreen';
import RecaptchaV2Widget from './RecaptchaV2Widget';
import HcaptchaWidget from './HcaptchaWidget';

interface ContactFormProps {
  captchaType: CaptchaType;
  hasConfirmScreen: boolean;
  patternId: string;
}

const EMPTY: FormData = {
  company: '',
  department: '',
  name: '',
  email: '',
  phone: '',
  category: '',
  message: '',
  privacy: false,
};

export default function ContactForm({ captchaType, hasConfirmScreen, patternId }: ContactFormProps) {
  const router = useRouter();
  // provider外でも安全に呼べる（executeRecaptcha は undefined になる）
  const { executeRecaptcha } = useGoogleReCaptcha();

  const [data, setData] = useState<FormData>(EMPTY);
  const [step, setStep] = useState<'input' | 'confirm'>('input');
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = useCallback(
    (key: keyof FormData, value: string | boolean) => {
      setData((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const validate = (): string | null => {
    if (!data.company.trim()) return '会社名を入力してください。';
    if (!data.name.trim()) return 'ご担当者名を入力してください。';
    if (!data.email.trim()) return 'メールアドレスを入力してください。';
    if (!data.category) return 'お問い合わせ種別を選択してください。';
    if (!data.message.trim()) return 'お問い合わせ内容を入力してください。';
    if (!data.privacy) return '個人情報の取り扱いについて同意してください。';
    return null;
  };

  // 実際の送信処理。CAPTCHAトークンを確定してAPIへPOST。
  const doSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      let token = captchaToken ?? undefined;

      if (captchaType === 'recaptcha-v3') {
        if (!executeRecaptcha) {
          setError('reCAPTCHA v3 が初期化されていません（サイトキー未設定の可能性）。');
          setSubmitting(false);
          return;
        }
        token = await executeRecaptcha('submit');
      }

      if (captchaType === 'recaptcha-v2' || captchaType === 'hcaptcha') {
        if (!token) {
          setError('CAPTCHA認証を完了してください。');
          setSubmitting(false);
          return;
        }
      }

      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patternId,
          captchaType,
          captchaToken: token,
          ...data,
        }),
      });

      const json: SubmitResponse = await res.json();

      if (!json.success) {
        setError(json.error ?? '送信に失敗しました。');
        setSubmitting(false);
        return;
      }

      router.push(`/complete?pattern=${encodeURIComponent(patternId)}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '送信中にエラーが発生しました。');
      setSubmitting(false);
    }
  };

  // 入力画面の「送信/確認」ボタン
  const handlePrimary = (e: React.FormEvent) => {
    e.preventDefault();
    const v = validate();
    if (v) {
      setError(v);
      return;
    }
    setError(null);
    if (hasConfirmScreen) {
      setStep('confirm');
    } else {
      void doSubmit();
    }
  };

  const captchaWidget =
    captchaType === 'recaptcha-v2' ? (
      <RecaptchaV2Widget onChange={(t) => setCaptchaToken(t)} />
    ) : captchaType === 'hcaptcha' ? (
      <HcaptchaWidget onVerify={(t) => setCaptchaToken(t)} onExpire={() => setCaptchaToken(null)} />
    ) : null;

  // 確認画面（同一URL・state切替でDOM差し替え）
  if (step === 'confirm') {
    return (
      <div>
        {error ? (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        <ConfirmScreen
          data={data}
          onBack={() => {
            setError(null);
            setStep('input');
          }}
          onSubmit={() => void doSubmit()}
          submitting={submitting}
        >
          {captchaWidget}
        </ConfirmScreen>
      </div>
    );
  }

  return (
    <form onSubmit={handlePrimary} className="space-y-5" noValidate>
      {error ? (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <Field label="会社名" required>
        <input
          type="text"
          name="company"
          value={data.company}
          onChange={(e) => update('company', e.target.value)}
          placeholder="株式会社サンプル"
          className={inputClass}
        />
      </Field>

      <Field label="部署名">
        <input
          type="text"
          name="department"
          value={data.department}
          onChange={(e) => update('department', e.target.value)}
          placeholder="営業部"
          className={inputClass}
        />
      </Field>

      <Field label="ご担当者名" required>
        <input
          type="text"
          name="name"
          value={data.name}
          onChange={(e) => update('name', e.target.value)}
          placeholder="山田 太郎"
          className={inputClass}
        />
      </Field>

      <Field label="メールアドレス" required>
        <input
          type="email"
          name="email"
          value={data.email}
          onChange={(e) => update('email', e.target.value)}
          placeholder="taro@example.com"
          className={inputClass}
        />
      </Field>

      <Field label="電話番号">
        <input
          type="tel"
          name="phone"
          value={data.phone}
          onChange={(e) => update('phone', e.target.value)}
          placeholder="03-1234-5678"
          className={inputClass}
        />
      </Field>

      <Field label="お問い合わせ種別" required>
        <select
          name="category"
          value={data.category}
          onChange={(e) => update('category', e.target.value)}
          className={inputClass}
        >
          <option value="">選択してください</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </Field>

      <Field label="お問い合わせ内容" required>
        <textarea
          name="message"
          value={data.message}
          onChange={(e) => update('message', e.target.value)}
          rows={5}
          placeholder="お問い合わせ内容をご記入ください。"
          className={inputClass}
        />
      </Field>

      <div className="flex items-start gap-2">
        <input
          type="checkbox"
          id="privacy"
          name="privacy"
          checked={data.privacy}
          onChange={(e) => update('privacy', e.target.checked)}
          className="mt-1"
        />
        <label htmlFor="privacy" className="text-sm text-gray-700">
          個人情報の取り扱いについて同意する
          <span className="ml-1 text-red-600">*</span>
        </label>
      </div>

      {captchaType !== 'none' && !hasConfirmScreen ? (
        <div>{captchaWidget}</div>
      ) : null}

      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {hasConfirmScreen ? '内容を確認する' : submitting ? '送信中…' : '送信する'}
      </button>
    </form>
  );
}

const inputClass =
  'w-full rounded border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500';

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">
        {label}
        {required ? <span className="ml-1 text-red-600">*</span> : null}
      </label>
      {children}
    </div>
  );
}
