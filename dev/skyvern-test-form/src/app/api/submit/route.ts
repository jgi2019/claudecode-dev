import { NextRequest, NextResponse } from 'next/server';
import { v4 as uuidv4 } from 'uuid';
import { saveLog } from '@/lib/storage';
import { PATTERNS, type CaptchaResult, type CaptchaType, type SubmissionLog, type SubmitRequest } from '@/lib/types';

export const runtime = 'nodejs';

async function verifyRecaptcha(token: string, secret: string): Promise<CaptchaResult> {
  const res = await fetch('https://www.google.com/recaptcha/api/siteverify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ secret, response: token }),
  });
  const json = (await res.json()) as { success: boolean; score?: number; 'error-codes'?: string[] };
  return {
    verified: json.success,
    score: json.score,
    error: json.success ? undefined : (json['error-codes']?.join(', ') ?? 'verification failed'),
  };
}

async function verifyRecaptchaV3(token: string, secret: string, threshold = 0.5): Promise<CaptchaResult> {
  const result = await verifyRecaptcha(token, secret);
  if (!result.verified) return result;
  const passed = (result.score ?? 0) >= threshold;
  return {
    verified: passed,
    score: result.score,
    error: passed ? undefined : `score ${result.score} below threshold ${threshold}`,
  };
}

async function verifyHcaptcha(token: string, secret: string): Promise<CaptchaResult> {
  const res = await fetch('https://hcaptcha.com/siteverify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ secret, response: token }),
  });
  const json = (await res.json()) as { success: boolean; 'error-codes'?: string[] };
  return {
    verified: json.success,
    error: json.success ? undefined : (json['error-codes']?.join(', ') ?? 'verification failed'),
  };
}

async function verifyCaptcha(type: CaptchaType, token?: string): Promise<CaptchaResult> {
  if (type === 'none') {
    return { verified: true };
  }
  if (!token) {
    return { verified: false, error: 'captcha token missing' };
  }

  switch (type) {
    case 'recaptcha-v2': {
      const secret = process.env.RECAPTCHA_V2_SECRET_KEY;
      if (!secret) return { verified: false, error: 'RECAPTCHA_V2_SECRET_KEY not set' };
      return verifyRecaptcha(token, secret);
    }
    case 'recaptcha-v3': {
      const secret = process.env.RECAPTCHA_V3_SECRET_KEY;
      if (!secret) return { verified: false, error: 'RECAPTCHA_V3_SECRET_KEY not set' };
      return verifyRecaptchaV3(token, secret);
    }
    case 'hcaptcha': {
      const secret = process.env.HCAPTCHA_SECRET_KEY;
      if (!secret) return { verified: false, error: 'HCAPTCHA_SECRET_KEY not set' };
      return verifyHcaptcha(token, secret);
    }
    default:
      return { verified: false, error: 'unknown captcha type' };
  }
}

export async function POST(req: NextRequest) {
  let body: SubmitRequest;
  try {
    body = (await req.json()) as SubmitRequest;
  } catch {
    return NextResponse.json({ success: false, error: 'invalid JSON' }, { status: 400 });
  }

  // 1. バリデーション
  const missing: string[] = [];
  if (!body.company?.trim()) missing.push('company');
  if (!body.name?.trim()) missing.push('name');
  if (!body.email?.trim()) missing.push('email');
  if (!body.category) missing.push('category');
  if (!body.message?.trim()) missing.push('message');
  if (!body.privacy) missing.push('privacy');

  if (missing.length > 0) {
    return NextResponse.json(
      { success: false, error: '必須項目が未入力です。', details: { missing } },
      { status: 400 },
    );
  }

  // 2. CAPTCHA検証
  const captchaResult = await verifyCaptcha(body.captchaType, body.captchaToken);

  // 3. ログ記録
  const pattern = PATTERNS.find((p) => p.id === body.patternId);
  const log: SubmissionLog = {
    id: uuidv4(),
    timestamp: new Date().toISOString(),
    patternId: body.patternId,
    captchaType: body.captchaType,
    hasConfirmScreen: pattern?.hasConfirmScreen ?? false,
    captchaResult,
    formData: {
      company: body.company ?? '',
      department: body.department ?? '',
      name: body.name ?? '',
      email: body.email ?? '',
      phone: body.phone ?? '',
      category: body.category ?? '',
      message: body.message ?? '',
    },
    userAgent: req.headers.get('user-agent') ?? '',
    ip:
      req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ??
      req.headers.get('x-real-ip') ??
      '',
  };
  await saveLog(log);

  // 4. レスポンス
  if (!captchaResult.verified) {
    return NextResponse.json(
      { success: false, error: 'CAPTCHA検証に失敗しました。', details: captchaResult },
      { status: 403 },
    );
  }

  return NextResponse.json({ success: true, logId: log.id });
}
