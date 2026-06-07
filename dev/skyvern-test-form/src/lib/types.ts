export type CaptchaType = 'none' | 'recaptcha-v2' | 'recaptcha-v3' | 'hcaptcha';

export interface FormData {
  company: string;
  department: string;
  name: string;
  email: string;
  phone: string;
  category: string;
  message: string;
  privacy: boolean;
}

export interface SubmitRequest extends FormData {
  patternId: string;
  captchaType: CaptchaType;
  captchaToken?: string;
}

export interface CaptchaResult {
  verified: boolean;
  score?: number;
  error?: string;
}

export interface SubmissionLog {
  id: string;
  timestamp: string;
  patternId: string;
  captchaType: string;
  hasConfirmScreen: boolean;
  captchaResult: CaptchaResult;
  formData: {
    company: string;
    department: string;
    name: string;
    email: string;
    phone: string;
    category: string;
    message: string;
  };
  userAgent: string;
  ip: string;
}

export interface SubmitResponse {
  success: boolean;
  logId?: string;
  error?: string;
  details?: unknown;
}

export const CATEGORIES = [
  '商品について',
  '取引について',
  'OEMについて',
  'その他',
] as const;

export interface PatternDef {
  id: string;
  path: string;
  label: string;
  captchaType: CaptchaType;
  captchaLabel: string;
  hasConfirmScreen: boolean;
}

export const PATTERNS: PatternDef[] = [
  { id: 'none-direct', path: '/none-direct', label: 'CAPTCHAなし・確認なし', captchaType: 'none', captchaLabel: 'なし', hasConfirmScreen: false },
  { id: 'none-confirm', path: '/none-confirm', label: 'CAPTCHAなし・確認あり', captchaType: 'none', captchaLabel: 'なし', hasConfirmScreen: true },
  { id: 'v2-direct', path: '/v2-direct', label: 'reCAPTCHA v2・確認なし', captchaType: 'recaptcha-v2', captchaLabel: 'reCAPTCHA v2', hasConfirmScreen: false },
  { id: 'v2-confirm', path: '/v2-confirm', label: 'reCAPTCHA v2・確認あり', captchaType: 'recaptcha-v2', captchaLabel: 'reCAPTCHA v2', hasConfirmScreen: true },
  { id: 'v3-direct', path: '/v3-direct', label: 'reCAPTCHA v3・確認なし', captchaType: 'recaptcha-v3', captchaLabel: 'reCAPTCHA v3', hasConfirmScreen: false },
  { id: 'v3-confirm', path: '/v3-confirm', label: 'reCAPTCHA v3・確認あり', captchaType: 'recaptcha-v3', captchaLabel: 'reCAPTCHA v3', hasConfirmScreen: true },
  { id: 'hcaptcha-direct', path: '/hcaptcha-direct', label: 'hCaptcha・確認なし', captchaType: 'hcaptcha', captchaLabel: 'hCaptcha', hasConfirmScreen: false },
  { id: 'hcaptcha-confirm', path: '/hcaptcha-confirm', label: 'hCaptcha・確認あり', captchaType: 'hcaptcha', captchaLabel: 'hCaptcha', hasConfirmScreen: true },
];
