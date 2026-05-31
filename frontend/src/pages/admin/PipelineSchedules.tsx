import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import {
  listCompanies,
  listEstatesForCompany,
  listPipelineSchedules,
  createPipelineSchedule,
  updatePipelineSchedule,
  getMe,
  type Company,
  type PipelineEstate,
  type PipelineSchedule,
} from '../../lib/adminApi';

const CADENCES = ['daily', 'weekly', 'monthly'];
const MODES = ['scheduled', 'backfill'];

export default function PipelineSchedules() {
  const { t } = useTranslation();
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [schedules, setSchedules] = useState<PipelineSchedule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [estates, setEstates] = useState<PipelineEstate[]>([]);
  const [form, setForm] = useState({
    mode: 'scheduled',
    company_id: '' as number | '',
    estate_id: '' as number | '',
    afdeling_id: '' as number | '',
    cadence: 'weekly',
    timezone: 'UTC',
    date_start: '',
    date_end: '',
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    getMe().then((me) => setIsSuperAdmin(me.is_global_admin));
    load();
  }, []);

  useEffect(() => {
    if (showCreate) listCompanies({ limit: 100 }).then((r) => setCompanies(r.items));
  }, [showCreate]);

  useEffect(() => {
    if (form.company_id !== '') {
      listEstatesForCompany(Number(form.company_id)).then(setEstates);
      setForm((f) => ({ ...f, estate_id: '' }));
    }
  }, [form.company_id]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listPipelineSchedules();
      setSchedules(data.items);
    } catch {
      setError('Failed to load schedules');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await createPipelineSchedule({
        mode: form.mode,
        company_id: Number(form.company_id),
        estate_id: Number(form.estate_id),
        afdeling_id: form.afdeling_id !== '' ? Number(form.afdeling_id) : null,
        cadence: form.cadence,
        timezone: form.timezone,
        date_start: form.mode === 'backfill' && form.date_start ? form.date_start : null,
        date_end: form.mode === 'backfill' && form.date_end ? form.date_end : null,
      });
      setShowCreate(false);
      await load();
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail ?? 'Failed to create schedule');
    } finally {
      setCreating(false);
    }
  }

  async function handleToggle(sched: PipelineSchedule) {
    try {
      await updatePipelineSchedule(sched.id, { enabled: !sched.enabled });
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Update failed');
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-slate-800">{t('admin.pipeline.schedulesTitle')}</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Schedules fire while the server is running (staging scheduler).
            {!isSuperAdmin && ' View only — schedule management requires super-admin.'}
          </p>
        </div>
        {isSuperAdmin && (
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            + New Schedule
          </button>
        )}
      </div>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Mode</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Scope</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Cadence</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Next Run</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Last Run</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Created By</th>
              {isSuperAdmin && <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr><td colSpan={8} className="px-4 py-6 text-center text-slate-400 text-sm">{t('admin.pipeline.loading')}</td></tr>
            )}
            {!loading && schedules.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-6 text-center text-slate-400 text-sm">{t('admin.pipeline.noSchedules')}</td></tr>
            )}
            {!loading && schedules.map((s) => (
              <tr key={s.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    s.enabled ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
                  }`}>
                    {s.enabled ? 'ENABLED' : 'DISABLED'}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-700">{s.mode}</td>
                <td className="px-4 py-3 text-slate-600">
                  estate {s.estate_id}
                  {s.afdeling_id ? ` / afd ${s.afdeling_id}` : ''}
                  {s.date_start ? ` (${s.date_start}→${s.date_end})` : ''}
                </td>
                <td className="px-4 py-3 text-slate-600">{s.cadence} <span className="text-slate-400">({s.timezone})</span></td>
                <td className="px-4 py-3 text-slate-500">
                  {s.next_run ? new Date(s.next_run).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {s.last_run ? new Date(s.last_run).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-3 text-slate-500">{s.created_by_username}</td>
                {isSuperAdmin && (
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggle(s)}
                      className={`px-2 py-1 text-xs rounded border transition-colors ${
                        s.enabled
                          ? 'border-red-300 text-red-600 hover:bg-red-50'
                          : 'border-green-300 text-green-700 hover:bg-green-50'
                      }`}
                    >
                      {s.enabled ? 'Disable' : 'Enable'}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create modal — super-admin only */}
      {showCreate && isSuperAdmin && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 overflow-y-auto py-8">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-lg w-full mx-4">
            <h2 className="text-base font-bold text-slate-800 mb-4">New Pipeline Schedule</h2>
            <form onSubmit={handleCreate} className="space-y-4">

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Mode</label>
                <select
                  value={form.mode}
                  onChange={(e) => setForm((f) => ({ ...f, mode: e.target.value }))}
                  className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                >
                  {MODES.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Company</label>
                <select
                  value={form.company_id}
                  onChange={(e) => setForm((f) => ({ ...f, company_id: e.target.value === '' ? '' : Number(e.target.value) }))}
                  required
                  className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                >
                  <option value="">— select company —</option>
                  {companies.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Estate</label>
                <select
                  value={form.estate_id}
                  onChange={(e) => setForm((f) => ({ ...f, estate_id: e.target.value === '' ? '' : Number(e.target.value) }))}
                  required
                  disabled={form.company_id === '' || estates.length === 0}
                  className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm disabled:bg-slate-50"
                >
                  <option value="">— select estate —</option>
                  {estates.map((e) => <option key={e.id} value={e.id}>{e.name} ({e.code})</option>)}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Cadence</label>
                  <select
                    value={form.cadence}
                    onChange={(e) => setForm((f) => ({ ...f, cadence: e.target.value }))}
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                  >
                    {CADENCES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Timezone</label>
                  <input
                    type="text"
                    value={form.timezone}
                    onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
                    placeholder="UTC"
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {form.mode === 'backfill' && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Date Start (YYYY-MM)</label>
                    <input
                      type="text"
                      value={form.date_start}
                      onChange={(e) => setForm((f) => ({ ...f, date_start: e.target.value }))}
                      required
                      placeholder="e.g. 2023-01"
                      className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Date End (YYYY-MM)</label>
                    <input
                      type="text"
                      value={form.date_end}
                      onChange={(e) => setForm((f) => ({ ...f, date_end: e.target.value }))}
                      required
                      placeholder="e.g. 2026-04"
                      className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              )}

              {createError && <p className="text-red-500 text-sm">{createError}</p>}

              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  {creating ? 'Creating…' : 'Create Schedule'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="flex-1 px-4 py-2 bg-white text-slate-600 text-sm rounded-md border border-slate-300 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
