'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { PATTERNS, type SubmissionLog } from '@/lib/types';

export default function LogsPage() {
  const [logs, setLogs] = useState<SubmissionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('');

  const load = async () => {
    setLoading(true);
    try {
      const url = filter ? `/api/logs?pattern=${encodeURIComponent(filter)}` : '/api/logs';
      const res = await fetch(url, { cache: 'no-store' });
      const data = (await res.json()) as SubmissionLog[];
      setLogs(data);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  // パターン別の成功/失敗サマリー（全ログ基準なのでフィルタ非依存に別取得…ではなくlogsから集計）
  const summary = useMemo(() => {
    const map = new Map<string, { success: number; fail: number; total: number }>();
    for (const p of PATTERNS) map.set(p.id, { success: 0, fail: 0, total: 0 });
    for (const log of logs) {
      const s = map.get(log.patternId);
      if (!s) continue;
      s.total += 1;
      if (log.captchaResult.verified) s.success += 1;
      else s.fail += 1;
    }
    return map;
  }, [logs]);

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">送信ログ</h1>
        <div className="flex gap-2">
          <button
            onClick={() => void load()}
            className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            🔄 更新
          </button>
          <Link
            href="/"
            className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            ← トップ
          </Link>
        </div>
      </div>

      {/* サマリーマトリクス */}
      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">
          パターン別 成功/失敗マトリクス
          {filter ? '（※フィルタ適用中の集計）' : ''}
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {PATTERNS.map((p) => {
            const s = summary.get(p.id)!;
            const allOk = s.total > 0 && s.fail === 0;
            const anyFail = s.fail > 0;
            return (
              <div
                key={p.id}
                className={`rounded-lg border p-3 ${
                  s.total === 0
                    ? 'border-gray-200 bg-white'
                    : allOk
                      ? 'border-green-300 bg-green-50'
                      : anyFail
                        ? 'border-red-300 bg-red-50'
                        : 'border-gray-200 bg-white'
                }`}
              >
                <div className="mb-1 font-mono text-xs text-gray-600">{p.id}</div>
                <div className="text-xs text-gray-500">{p.captchaLabel}</div>
                <div className="mt-2 flex gap-3 text-sm">
                  <span className="text-green-700">✓ {s.success}</span>
                  <span className="text-red-700">✗ {s.fail}</span>
                  <span className="text-gray-400">計 {s.total}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* フィルタ */}
      <div className="mb-4 flex items-center gap-2">
        <label className="text-sm text-gray-700">パターンで絞り込み:</label>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        >
          <option value="">すべて</option>
          {PATTERNS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.id}
            </option>
          ))}
        </select>
      </div>

      {/* テーブル */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <Th>時刻</Th>
              <Th>パターン</Th>
              <Th>CAPTCHA</Th>
              <Th>確認画面</Th>
              <Th>結果</Th>
              <Th>スコア</Th>
              <Th>UA</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  読み込み中…
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  ログがありません。
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id} className={log.captchaResult.verified ? 'bg-green-50/40' : 'bg-red-50/40'}>
                  <Td className="whitespace-nowrap text-xs text-gray-600">
                    {new Date(log.timestamp).toLocaleString('ja-JP')}
                  </Td>
                  <Td className="whitespace-nowrap font-mono text-xs">{log.patternId}</Td>
                  <Td className="whitespace-nowrap text-xs">{log.captchaType}</Td>
                  <Td className="text-xs">{log.hasConfirmScreen ? 'あり' : 'なし'}</Td>
                  <Td>
                    {log.captchaResult.verified ? (
                      <span className="rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                        verified
                      </span>
                    ) : (
                      <span
                        className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800"
                        title={log.captchaResult.error}
                      >
                        failed
                      </span>
                    )}
                  </Td>
                  <Td className="text-xs">
                    {log.captchaResult.score !== undefined ? log.captchaResult.score : '—'}
                  </Td>
                  <Td className="text-xs text-gray-500">
                    <span className="block max-w-xs truncate" title={log.userAgent}>
                      {log.userAgent || '—'}
                    </span>
                  </Td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">{children}</th>
  );
}

function Td({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2 ${className}`}>{children}</td>;
}
