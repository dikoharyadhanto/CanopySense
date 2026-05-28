import { useEffect, useState } from 'react';
import { listAuditLog, type AuditEntry } from '../../lib/adminApi';

const PAGE_SIZE = 25;

export default function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    listAuditLog({ limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((r) => {
        setEntries(r.items);
        setTotal(r.total);
        setError(null);
      })
      .catch(() => setError('Failed to load audit log'))
      .finally(() => setLoading(false));
  }, [page]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="text-xl font-bold text-slate-800 mb-6">Audit Log ({total})</h1>
      {error && <div className="text-red-600 text-sm mb-4">{error}</div>}
      {loading ? (
        <div className="text-slate-400 text-sm">Loading...</div>
      ) : (
        <>
          <div className="bg-white rounded-lg border border-slate-200 mb-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Target</th>
                  <th className="px-4 py-3">Metadata</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{e.actor_username}</td>
                    <td className="px-4 py-3 font-mono text-xs text-indigo-600">{e.action}</td>
                    <td className="px-4 py-3 text-slate-500">
                      {e.target_type}{e.target_id ? ` #${e.target_id}` : ''}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400 max-w-xs truncate">
                      {Object.keys(e.metadata).length > 0
                        ? JSON.stringify(e.metadata)
                        : '—'}
                    </td>
                  </tr>
                ))}
                {entries.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                      No audit entries
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center gap-3 text-sm text-slate-500">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1 border border-slate-200 rounded-md hover:bg-slate-100 disabled:opacity-40"
              >
                ← Prev
              </button>
              <span>Page {page + 1} of {totalPages}</span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 border border-slate-200 rounded-md hover:bg-slate-100 disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
