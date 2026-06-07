'use client';

import type { FormData } from '@/lib/types';

interface Props {
  data: FormData;
  onBack: () => void;
  onSubmit: () => void;
  submitting: boolean;
  children?: React.ReactNode; // 確認画面に出すCAPTCHA（v2/hCaptcha）
}

const ROWS: { label: string; key: keyof FormData }[] = [
  { label: '会社名', key: 'company' },
  { label: '部署名', key: 'department' },
  { label: 'ご担当者名', key: 'name' },
  { label: 'メールアドレス', key: 'email' },
  { label: '電話番号', key: 'phone' },
  { label: 'お問い合わせ種別', key: 'category' },
  { label: 'お問い合わせ内容', key: 'message' },
];

export default function ConfirmScreen({ data, onBack, onSubmit, submitting, children }: Props) {
  return (
    <div>
      <h2 className="mb-4 text-lg font-bold text-gray-900">入力内容の確認</h2>
      <p className="mb-6 text-sm text-gray-600">
        以下の内容で送信します。よろしければ「送信する」を押してください。
      </p>

      <dl className="mb-6 divide-y divide-gray-200 border-y border-gray-200">
        {ROWS.map((row) => (
          <div key={row.key} className="grid grid-cols-3 gap-2 py-3">
            <dt className="text-sm font-medium text-gray-500">{row.label}</dt>
            <dd className="col-span-2 whitespace-pre-wrap text-sm text-gray-900">
              {String(data[row.key]) || '（未入力）'}
            </dd>
          </div>
        ))}
        <div className="grid grid-cols-3 gap-2 py-3">
          <dt className="text-sm font-medium text-gray-500">個人情報の取り扱い</dt>
          <dd className="col-span-2 text-sm text-gray-900">
            {data.privacy ? '同意済み' : '未同意'}
          </dd>
        </div>
      </dl>

      {children ? <div className="mb-6">{children}</div> : null}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={submitting}
          className="rounded border border-gray-300 bg-white px-6 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          修正する
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={submitting}
          className="rounded bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? '送信中…' : '送信する'}
        </button>
      </div>
    </div>
  );
}
