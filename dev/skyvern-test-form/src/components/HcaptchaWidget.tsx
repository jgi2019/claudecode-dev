'use client';

import HCaptcha from '@hcaptcha/react-hcaptcha';

interface Props {
  onVerify: (token: string) => void;
  onExpire?: () => void;
}

export default function HcaptchaWidget({ onVerify, onExpire }: Props) {
  const siteKey = process.env.NEXT_PUBLIC_HCAPTCHA_SITE_KEY;

  if (!siteKey) {
    return (
      <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
        hCaptcha のサイトキー（NEXT_PUBLIC_HCAPTCHA_SITE_KEY）が未設定です。
        .env.local または Vercel に設定してください。
      </div>
    );
  }

  return <HCaptcha sitekey={siteKey} onVerify={onVerify} onExpire={onExpire} />;
}
