import { NextRequest, NextResponse } from 'next/server';
import { getLogs } from '@/lib/storage';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const pattern = req.nextUrl.searchParams.get('pattern') ?? undefined;
  const logs = await getLogs(pattern);
  return NextResponse.json(logs);
}
