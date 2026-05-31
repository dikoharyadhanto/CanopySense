import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getDashboard, type DashboardData } from '../../lib/adminApi';

export default function AdminDashboard() {
  const { t } = useTranslation();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch(() => setError(t('admin.dashboard.errorLoad')));
  }, []);

  if (error) return <div className="p-6 text-red-600">{error}</div>;
  if (!data) return <div className="p-6 text-slate-500">{t('admin.dashboard.loading')}</div>;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="text-xl font-bold text-slate-800 mb-6">{t('admin.dashboard.title')}</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="text-2xl font-bold text-slate-800">{data.company_count}</div>
          <div className="text-sm text-slate-500 mt-1">{t('admin.dashboard.companies')}</div>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="text-2xl font-bold text-slate-800">{data.active_manager_count}</div>
          <div className="text-sm text-slate-500 mt-1">{t('admin.dashboard.activeManagers')}</div>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="text-sm font-semibold text-slate-600 mb-2">{t('admin.dashboard.subscriptions')}</div>
          {Object.entries(data.subscription_summary).map(([tier, count]) => (
            <div key={tier} className="flex justify-between text-sm">
              <span className="capitalize text-slate-500">{tier}</span>
              <span className="font-semibold text-slate-700">{count}</span>
            </div>
          ))}
          {Object.keys(data.subscription_summary).length === 0 && (
            <div className="text-sm text-slate-400">{t('admin.dashboard.noData')}</div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200">
        <div className="px-4 py-3 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">{t('admin.dashboard.recentActions')}</h2>
        </div>
        {data.recent_audit_actions.length === 0 ? (
          <div className="p-4 text-sm text-slate-400">{t('admin.dashboard.noRecentActions')}</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                <th className="px-4 py-2">{t('admin.dashboard.table.actor')}</th>
                <th className="px-4 py-2">{t('admin.dashboard.table.action')}</th>
                <th className="px-4 py-2">{t('admin.dashboard.table.target')}</th>
                <th className="px-4 py-2">{t('admin.dashboard.table.time')}</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_audit_actions.map((entry) => (
                <tr key={entry.id} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="px-4 py-2 text-slate-600">{entry.actor_username}</td>
                  <td className="px-4 py-2 font-mono text-xs text-indigo-600">{entry.action}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {entry.target_type}
                    {entry.target_id ? ` #${entry.target_id}` : ''}
                  </td>
                  <td className="px-4 py-2 text-slate-400 text-xs">
                    {new Date(entry.created_at).toLocaleString()}
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
