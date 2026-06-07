'use client';

import ReCAPTCHA from 'react-google-recaptcha';

interface Props {
  onChange: (token: string | null) => void;
}

export default function RecaptchaV2Widget({ onChange }: Props) {
  const siteKey = process.env.NEXT_PUBLIC_RECAPTCHA_V2_SITE_KEY;

  if (!siteKey) {
    return (
      <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
        reCAPTCHA v2 のサイトキー（NEXT_PUBLIC_RECAPTCHA_V2_SITE_KEY）が未設定です。
        .env.local または Vercel に設定してください。
      </div>
    );
  }

  return <ReCAPTCHA sitekey={siteKey} onChange={onChange} />;
}
