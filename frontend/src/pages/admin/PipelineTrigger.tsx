import { useEffect, useState } from 'react';
import {
  listCompanies,
  listEstatesForCompany,
  listAfdelingsForEstate,
  triggerPipeline,
  getPipelineRun,
  type Company,
  type PipelineEstate,
  type PipelineAfdeling,
  type PipelineRun,
} from '../../lib/adminApi';

type Mode = 'scheduled' | 'backfill';

const STATUS_COLOR: Record<string, string> = {
  pending:   'bg-slate-100 text-slate-600',
  running:   'bg-blue-100 text-blue-700',
  succeeded: 'bg-green-100 text-green-700',
  failed:    'bg-red-100 text-red-700',
};

export default function PipelineTrigger() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [estates, setEstates] = useState<PipelineEstate[]>([]);
  const [afdelings, setAfdelings] = useState<PipelineAfdeling[]>([]);

  const [mode, setMode] = useState<Mode>('scheduled');
  const [companyId, setCompanyId] = useState<number | ''>('');
  const [estateId, setEstateId] = useState<number | ''>('');
  const [afdelingId, setAfdelingId] = useState<number | ''>('');
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');

  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<PipelineRun | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    listCompanies({ limit: 100 }).then((r) => setCompanies(r.items));
  }, []);

  useEffect(() => {
    if (companyId !== '') {
      listEstatesForCompany(Number(companyId)).then(setEstates);
      setEstateId('');
      setAfdelings([]);
      setAfdelingId('');
    }
  }, [companyId]);

  useEffect(() => {
    if (estateId !== '') {
      listAfdelingsForEstate(Number(estateId)).then(setAfdelings);
      setAfdelingId('');
    }
  }, [estateId]);

  // Poll for run status every 8 seconds while running/pending
  useEffect(() => {
    if (!activeRun || !polling) return;
    if (activeRun.status === 'succeeded' || activeRun.status === 'failed') {
      setPolling(false);
      return;
    }
    const timer = setInterval(async () => {
      try {
        const detail = await getPipelineRun(activeRun.run_id);
        setActiveRun(detail.run);
        if (detail.run.status === 'succeeded' || detail.run.status === 'failed') {
          setPolling(false);
          clearInterval(timer);
        }
      } catch {
        // ignore transient poll errors
      }
    }, 8000);
    return () => clearInterval(timer);
  }, [activeRun, polling]);

  function canSubmit() {
    if (companyId === '' || estateId === '') return false;
    if (mode === 'backfill' && (!dateStart || !dateEnd)) return false;
    return true;
  }

  async function handleConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await triggerPipeline({
        mode,
        company_id: Number(companyId),
        estate_id: Number(estateId),
        afdeling_id: afdelingId !== '' ? Number(afdelingId) : null,
        date_start: mode === 'backfill' ? dateStart : null,
        date_end: mode === 'backfill' ? dateEnd : null,
      });
      const detail = await getPipelineRun(res.run_id);
      setActiveRun(detail.run);
      setPolling(true);
      setConfirming(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Trigger failed');
      setConfirming(false);
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setActiveRun(null);
    setPolling(false);
    setError(null);
    setConfirming(false);
  }

  if (activeRun) {
    const elapsed =
      activeRun.started_at && activeRun.finished_at
        ? ((new Date(activeRun.finished_at).getTime() - new Date(activeRun.started_at).getTime()) / 1000).toFixed(0) + 's'
        : activeRun.started_at
        ? 'running…'
        : '—';

    return (
      <div className="flex-1 overflow-y-auto p-6 max-w-2xl">
        <h1 className="text-xl font-bold text-slate-800 mb-6">Pipeline Run Status</h1>
        <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
          <div className="flex items-center gap-3">
            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${STATUS_COLOR[activeRun.status]}`}>
              {activeRun.status.toUpperCase()}
              {polling && activeRun.status === 'running' && ' ↻'}
            </span>
            <span className="text-sm text-slate-500 font-mono">{activeRun.run_id}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm text-slate-600">
            <span className="font-medium">Mode</span><span>{activeRun.mode}</span>
            <span className="font-medium">Estate ID</span><span>{activeRun.estate_id ?? '—'}</span>
            {activeRun.afdeling_id && <><span className="font-medium">Afdeling ID</span><span>{activeRun.afdeling_id}</span></>}
            {activeRun.date_start && <><span className="font-medium">Date range</span><span>{activeRun.date_start} → {activeRun.date_end}</span></>}
            <span className="font-medium">Elapsed</span><span>{elapsed}</span>
          </div>
          {activeRun.sanitized_error && (
            <div className="bg-red-50 border border-red-200 rounded p-3 font-mono text-xs text-red-700 whitespace-pre-wrap break-all">
              {activeRun.sanitized_error}
            </div>
          )}
          {polling && (
            <p className="text-xs text-slate-400">Polling for updates every 8 seconds…</p>
          )}
        </div>
        <button
          onClick={handleReset}
          className="mt-4 px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
        >
          Trigger Another Run
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-2xl">
      <h1 className="text-xl font-bold text-slate-800 mb-2">Trigger Pipeline Run</h1>
      <p className="text-sm text-slate-500 mb-6">
        Manually start an approved pipeline operation for a company estate.
        Only <strong>scheduled</strong> (weekly update) and <strong>backfill</strong> (historical) modes are available.
      </p>

      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-5">

        {/* Mode */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Mode</label>
          <div className="flex gap-3">
            {(['scheduled', 'backfill'] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-4 py-2 rounded-md text-sm font-medium border transition-colors ${
                  mode === m
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-slate-600 border-slate-300 hover:border-indigo-400'
                }`}
              >
                {m === 'scheduled' ? 'Scheduled (weekly update)' : 'Backfill (historical)'}
              </button>
            ))}
          </div>
          {mode === 'backfill' && (
            <p className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-2 mt-2">
              Backfill runs can take a long time. A date range is required. Max 48 months.
            </p>
          )}
        </div>

        {/* Company */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Company</label>
          <select
            value={companyId}
            onChange={(e) => setCompanyId(e.target.value === '' ? '' : Number(e.target.value))}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            <option value="">— select company —</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>{c.company_name}</option>
            ))}
          </select>
        </div>

        {/* Estate */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Estate</label>
          <select
            value={estateId}
            onChange={(e) => setEstateId(e.target.value === '' ? '' : Number(e.target.value))}
            disabled={companyId === '' || estates.length === 0}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:bg-slate-50 disabled:text-slate-400"
          >
            <option value="">— select estate —</option>
            {estates.map((e) => (
              <option key={e.id} value={e.id}>{e.name} ({e.code})</option>
            ))}
          </select>
        </div>

        {/* Afdeling (optional) */}
        {afdelings.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Afdeling <span className="text-slate-400 font-normal">(optional — leave blank for whole estate)</span>
            </label>
            <select
              value={afdelingId}
              onChange={(e) => setAfdelingId(e.target.value === '' ? '' : Number(e.target.value))}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option value="">— whole estate —</option>
              {afdelings.map((a) => (
                <option key={a.id} value={a.id}>{a.name} ({a.code})</option>
              ))}
            </select>
          </div>
        )}

        {/* Date range (backfill only) */}
        {mode === 'backfill' && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Date Start (YYYY-MM)</label>
              <input
                type="text"
                value={dateStart}
                onChange={(e) => setDateStart(e.target.value)}
                placeholder="e.g. 2023-01"
                className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Date End (YYYY-MM)</label>
              <input
                type="text"
                value={dateEnd}
                onChange={(e) => setDateEnd(e.target.value)}
                placeholder="e.g. 2026-04"
                className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
          </div>
        )}

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <div className="flex gap-3 pt-1">
          <button
            disabled={!canSubmit()}
            onClick={() => { setError(null); setConfirming(true); }}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-40"
          >
            Review &amp; Confirm
          </button>
        </div>
      </div>

      {/* Confirm dialog */}
      {confirming && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-base font-bold text-slate-800 mb-3">Confirm Pipeline Trigger</h2>
            <div className="text-sm text-slate-600 space-y-1 mb-5">
              <p><span className="font-medium">Mode:</span> {mode}</p>
              <p><span className="font-medium">Company ID:</span> {companyId}</p>
              <p><span className="font-medium">Estate ID:</span> {estateId}</p>
              {afdelingId !== '' && <p><span className="font-medium">Afdeling ID:</span> {afdelingId}</p>}
              {mode === 'backfill' && (
                <p><span className="font-medium">Date range:</span> {dateStart} → {dateEnd}</p>
              )}
            </div>
            <p className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-2 mb-5">
              This will immediately start a pipeline run. Backfill runs may take a long time to complete.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleConfirm}
                disabled={submitting}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? 'Launching…' : 'Start Run'}
              </button>
              <button
                onClick={() => setConfirming(false)}
                disabled={submitting}
                className="flex-1 px-4 py-2 bg-white text-slate-600 text-sm rounded-md border border-slate-300 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
