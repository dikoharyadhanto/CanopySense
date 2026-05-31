import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getCompanyDetail,
  updateManagerStatus,
  resendManagerSetupToken,
  deletePendingManager,
  type CompanyDetail as CompanyDetailData,
} from '../../lib/adminApi';

export default function CompanyDetail() {
  const { t } = useTranslation();
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<CompanyDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [tokenModal, setTokenModal] = useState<{
    username: string;
    token: string;
    expires: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  function load() {
    if (!companyId) return;
    getCompanyDetail(Number(companyId))
      .then(setData)
      .catch(() => setError('Failed to load company'));
  }

  useEffect(() => { load(); }, [companyId]);

  async function handleToggleManager(userId: number, currentActive: boolean) {
    await updateManagerStatus(userId, !currentActive);
    load();
  }

  async function handleResendToken(userId: number, username: string) {
    setActionLoading(userId);
    try {
      const res = await resendManagerSetupToken(userId);
      setTokenModal({ username, token: res.setup_token, expires: res.setup_token_expires_at });
      setCopied(false);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDeleteManager(userId: number, username: string) {
    if (!confirm(`Hapus manajer "${username}"? Tindakan ini tidak dapat dibatalkan.`)) return;
    setActionLoading(userId);
    try {
      await deletePendingManager(userId);
      load();
    } finally {
      setActionLoading(null);
    }
  }

  function handleCopyToken(token: string) {
    navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (error) return <div className="p-6 text-red-600">{error}</div>;
  if (!data) return <div className="p-6 text-slate-400">{t('admin.companies.loading')}</div>;

  const { company, readiness, subscription, managers } = data;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <button
        onClick={() => navigate('/admin/companies')}
        className="text-sm text-indigo-600 hover:text-indigo-800 mb-4 inline-block"
      >
        ← Back to Companies
      </button>

      <h1 className="text-xl font-bold text-slate-800 mb-1">{company.company_name}</h1>
      <div className="text-xs text-slate-400 font-mono mb-6">{company.company_id}</div>

      {/* Readiness */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Estates', value: readiness.estates },
          { label: 'Blocks', value: readiness.blocks },
          { label: 'Satellite Records', value: readiness.satellite_records },
          { label: 'Subscription', value: readiness.has_subscription ? 'Yes' : 'No' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white border border-slate-200 rounded-lg p-3">
            <div className="text-lg font-bold text-slate-800">{value}</div>
            <div className="text-xs text-slate-500">{label}</div>
          </div>
        ))}
      </div>

      {/* Subscription */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700">Subscription</h2>
          {subscription && (
            <button
              onClick={() => navigate(`/admin/companies/${companyId}/subscription`)}
              className="text-xs text-indigo-600 hover:text-indigo-800"
            >
              Edit →
            </button>
          )}
        </div>
        {subscription ? (
          <div className="grid grid-cols-3 gap-2 text-sm">
            {[
              ['Tier', subscription.tier],
              ['Status', subscription.status],
              ['Billing', subscription.billing_interval ?? '—'],
              ['Timelapse', subscription.timelapse_enabled ? `${subscription.timelapse_period_months}mo` : 'Off'],
              ['Raster Mode', subscription.raster_serving_mode],
              ['Ends', subscription.subscription_ends_at
                ? new Date(subscription.subscription_ends_at).toLocaleDateString()
                : '—'],
            ].map(([k, v]) => (
              <div key={k}>
                <div className="text-xs text-slate-400">{k}</div>
                <div className="text-slate-700 capitalize">{v}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-slate-400">No subscription record</div>
        )}
      </div>

      {/* Setup Token Modal */}
      {tokenModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
            <h2 className="text-base font-semibold text-slate-800 mb-1">Setup Token</h2>
            <p className="text-xs text-slate-500 mb-4">
              Token baru untuk <span className="font-mono font-medium">{tokenModal.username}</span>.
              Salin sekarang — token tidak akan ditampilkan lagi.
            </p>
            <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 font-mono text-xs text-slate-800 break-all mb-2">
              {tokenModal.token}
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Berlaku hingga: {new Date(tokenModal.expires).toLocaleString('id-ID')}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => handleCopyToken(tokenModal.token)}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2 rounded-lg transition-colors"
              >
                {copied ? 'Tersalin!' : 'Salin Token'}
              </button>
              <button
                onClick={() => setTokenModal(null)}
                className="flex-1 border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm font-medium py-2 rounded-lg transition-colors"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Managers */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700">Managers ({managers.length})</h2>
          <button
            onClick={() => navigate(`/admin/companies/${companyId}/invite`)}
            className="text-xs text-indigo-600 hover:text-indigo-800"
          >
            + Invite Manager
          </button>
        </div>
        {managers.length === 0 ? (
          <div className="text-sm text-slate-400">No managers assigned</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                <th className="py-2">Username</th>
                <th className="py-2">Name</th>
                <th className="py-2">Email</th>
                <th className="py-2">Status</th>
                <th className="py-2">Setup</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {managers.map((m) => (
                <tr key={m.id} className="border-b border-slate-50">
                  <td className="py-2 font-mono text-xs text-slate-600">{m.username}</td>
                  <td className="py-2 text-slate-700">{m.full_name ?? <span className="text-slate-400 italic">Not set</span>}</td>
                  <td className="py-2 text-slate-500">{m.email}</td>
                  <td className="py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      m.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
                    }`}>
                      {m.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-2">
                    {m.setup_required && (
                      <span className="text-xs px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full">
                        Pending Setup
                      </span>
                    )}
                  </td>
                  <td className="py-2 flex items-center gap-2 flex-wrap">
                    {m.setup_required && (
                      <>
                        <button
                          onClick={() => handleResendToken(m.id, m.username)}
                          disabled={actionLoading === m.id}
                          className="text-xs text-indigo-600 hover:text-indigo-800 disabled:opacity-50 transition-colors"
                        >
                          {actionLoading === m.id ? '...' : 'Token'}
                        </button>
                        <span className="text-slate-300">·</span>
                        <button
                          onClick={() => handleDeleteManager(m.id, m.username)}
                          disabled={actionLoading === m.id}
                          className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50 transition-colors"
                        >
                          Remove
                        </button>
                        <span className="text-slate-300">·</span>
                      </>
                    )}
                    <button
                      onClick={() => handleToggleManager(m.id, m.is_active)}
                      className="text-xs text-slate-500 hover:text-red-600 transition-colors"
                    >
                      {m.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
