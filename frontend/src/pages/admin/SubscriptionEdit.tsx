import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getSubscription, updateSubscription, type Subscription } from '../../lib/adminApi';

const TIERS = ['basic', 'premium'];
const STATUSES = ['trialing', 'active', 'past_due', 'cancelled', 'expired'];
const RASTER_MODES = ['gee_mapid', 'maps_platform'];
const BILLING_INTERVALS = ['monthly', 'yearly', 'fixed_period'];

export default function SubscriptionEdit() {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [form, setForm] = useState<Partial<Subscription>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    getSubscription(Number(companyId)).then((s) => {
      setSub(s);
      setForm({
        tier: s.tier,
        status: s.status,
        billing_interval: s.billing_interval ?? undefined,
        subscription_starts_at: s.subscription_starts_at ?? undefined,
        subscription_ends_at: s.subscription_ends_at ?? undefined,
        timelapse_enabled: s.timelapse_enabled,
        timelapse_period_months: s.timelapse_period_months ?? undefined,
        raster_serving_mode: s.raster_serving_mode,
      });
    });
  }, [companyId]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await updateSubscription(Number(companyId), form);
      setSub(updated);
      setSuccess(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  function set<K extends keyof Subscription>(key: K, value: Subscription[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  if (!sub) return <div className="p-6 text-slate-400">Loading...</div>;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <button
        onClick={() => navigate(`/admin/companies/${companyId}`)}
        className="text-sm text-indigo-600 hover:text-indigo-800 mb-4 inline-block"
      >
        ← Back to Company
      </button>
      <h1 className="text-xl font-bold text-slate-800 mb-6">Edit Subscription</h1>
      <form onSubmit={handleSave} className="max-w-md space-y-4">
        <div>
          <label className="block text-sm text-slate-600 mb-1">Tier</label>
          <select
            value={form.tier}
            onChange={(e) => set('tier', e.target.value)}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            {TIERS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm text-slate-600 mb-1">Status</label>
          <select
            value={form.status}
            onChange={(e) => set('status', e.target.value)}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm text-slate-600 mb-1">Billing Interval</label>
          <select
            value={form.billing_interval ?? ''}
            onChange={(e) => set('billing_interval', e.target.value || null as any)}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            <option value="">— None —</option>
            {BILLING_INTERVALS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm text-slate-600 mb-1">Raster Serving Mode</label>
          <select
            value={form.raster_serving_mode}
            onChange={(e) => set('raster_serving_mode', e.target.value)}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            {RASTER_MODES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="timelapse"
            checked={form.timelapse_enabled ?? false}
            onChange={(e) => set('timelapse_enabled', e.target.checked)}
            className="rounded"
          />
          <label htmlFor="timelapse" className="text-sm text-slate-600">Timelapse Enabled</label>
        </div>
        {form.timelapse_enabled && (
          <div>
            <label className="block text-sm text-slate-600 mb-1">Timelapse Period (months)</label>
            <input
              type="number"
              min={1}
              value={form.timelapse_period_months ?? ''}
              onChange={(e) => set('timelapse_period_months', Number(e.target.value) || null as any)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
        )}
        <div>
          <label className="block text-sm text-slate-600 mb-1">Subscription Start</label>
          <input
            type="date"
            value={form.subscription_starts_at?.split('T')[0] ?? ''}
            onChange={(e) => set('subscription_starts_at', e.target.value || null as any)}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-600 mb-1">Subscription End</label>
          <input
            type="date"
            value={form.subscription_ends_at?.split('T')[0] ?? ''}
            onChange={(e) => set('subscription_ends_at', e.target.value || null as any)}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        {success && <p className="text-green-600 text-sm">Saved successfully.</p>}
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </form>
    </div>
  );
}
