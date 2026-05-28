import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listPipelineRuns, type PipelineRun } from '../../lib/adminApi';

const STATUS_COLOR: Record<string, string> = {
  pending:   'bg-slate-100 text-slate-600',
  running:   'bg-blue-100 text-blue-700',
  succeeded: 'bg-green-100 text-green-700',
  failed:    'bg-red-100 text-red-700',
};

function duration(run: PipelineRun): string {
  if (!run.started_at) return '—';
  const end = run.finished_at ? new Date(run.finished_at) : new Date();
  const secs = Math.round((end.getTime() - new Date(run.started_at).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

export default function PipelineRunHistory() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const PAGE_SIZE = 20;

  async function load(p: number) {
    setLoading(true);
    setError(null);
    try {
      const data = await listPipelineRuns({ page: p, page_size: PAGE_SIZE });
      setRuns(data.items);
      setTotal(data.total);
      setPage(p);
    } catch {
      setError('Failed to load run history');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(1); }, []);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-slate-800">Pipeline Run History</h1>
          <p className="text-sm text-slate-500 mt-0.5">{total} total runs</p>
        </div>
        <button
          onClick={() => load(page)}
          className="px-3 py-1.5 text-sm border border-slate-300 rounded-md text-slate-600 hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Mode</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Scope</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Actor</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Started</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Duration</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Run ID</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400 text-sm">Loading…</td></tr>
            )}
            {!loading && runs.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400 text-sm">No runs yet.</td></tr>
            )}
            {!loading && runs.map((r) => (
              <tr
                key={r.id}
                className="hover:bg-slate-50 cursor-pointer"
                onClick={() => navigate(`/admin/pipeline/runs/${r.run_id}`)}
              >
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${STATUS_COLOR[r.status]}`}>
                    {r.status.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-700">{r.mode}</td>
                <td className="px-4 py-3 text-slate-600">
                  estate {r.estate_id}
                  {r.afdeling_id ? ` / afd ${r.afdeling_id}` : ''}
                  {r.date_start ? ` (${r.date_start}→${r.date_end})` : ''}
                </td>
                <td className="px-4 py-3 text-slate-600">{r.actor_username}</td>
                <td className="px-4 py-3 text-slate-500">
                  {r.started_at ? new Date(r.started_at).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-3 text-slate-500">{duration(r)}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-400">{r.run_id.slice(0, 8)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm text-slate-600">
          <span>Page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              onClick={() => load(page - 1)}
              disabled={page === 1}
              className="px-3 py-1.5 border border-slate-300 rounded-md disabled:opacity-40 hover:bg-slate-50"
            >
              Previous
            </button>
            <button
              onClick={() => load(page + 1)}
              disabled={page === totalPages}
              className="px-3 py-1.5 border border-slate-300 rounded-md disabled:opacity-40 hover:bg-slate-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
