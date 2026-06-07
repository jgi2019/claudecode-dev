'use client';

import { GoogleReCaptchaProvider } from 'react-google-recaptcha-v3';

interface Props {
  children: React.ReactNode;
}

export default function RecaptchaV3Provider({ children }: Props) {
  const siteKey = process.env.NEXT_PUBLIC_RECAPTCHA_V3_SITE_KEY;

  if (!siteKey) {
    return (
      <>
        <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          reCAPTCHA v3 のサイトキー（NEXT_PUBLIC_RECAPTCHA_V3_SITE_KEY）が未設定です。
          .env.local または Vercel に設定してください。送信は失敗します。
        </div>
        {children}
      </>
    );
  }

  return (
    <GoogleReCaptchaProvider reCaptchaKey={siteKey}>
      {children}
    </GoogleReCaptchaProvider>
  );
}
