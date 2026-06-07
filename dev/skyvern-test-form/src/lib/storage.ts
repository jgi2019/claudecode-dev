import { promises as fs } from 'fs';
import path from 'path';
import type { SubmissionLog } from './types';

// 開発/検証用のシンプルなログ保存。
// Vercel serverless では /tmp が唯一の書き込み可能領域（揮発する）。
// ローカル開発でも /tmp を使う。本番用途ではない。
const LOG_FILE = path.join('/tmp', 'submission-logs.json');

// メモリ内フォールバック（/tmp が読めない場合の保険）
let memoryLogs: SubmissionLog[] = [];

async function readFromFile(): Promise<SubmissionLog[]> {
  try {
    const raw = await fs.readFile(LOG_FILE, 'utf-8');
    return JSON.parse(raw) as SubmissionLog[];
  } catch {
    return [];
  }
}

async function writeToFile(logs: SubmissionLog[]): Promise<void> {
  await fs.writeFile(LOG_FILE, JSON.stringify(logs, null, 2), 'utf-8');
}

export async function saveLog(log: SubmissionLog): Promise<void> {
  try {
    const logs = await readFromFile();
    logs.push(log);
    await writeToFile(logs);
    memoryLogs = logs;
  } catch {
    memoryLogs.push(log);
  }
}

export async function getLogs(patternId?: string): Promise<SubmissionLog[]> {
  let logs: SubmissionLog[];
  try {
    logs = await readFromFile();
    if (logs.length === 0 && memoryLogs.length > 0) {
      logs = memoryLogs;
    }
  } catch {
    logs = memoryLogs;
  }
  const sorted = [...logs].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  if (patternId) {
    return sorted.filter((l) => l.patternId === patternId);
  }
  return sorted;
}
