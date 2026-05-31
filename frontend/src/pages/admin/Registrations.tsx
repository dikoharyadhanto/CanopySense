import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../../lib/api';

interface RegistrationItem {
  id: number;
  company_name: string;
  contact_name: string;
  email: string;
  phone: string | null;
  status: string;
  reject_reason: string | null;
  created_at: string;
}

type StatusFilter = 'ALL' | 'PENDING' | 'APPROVED' | 'REJECTED';

const STATUS_COLOR: Record<string, string> = {
  PENDING: 'bg-amber-100 text-amber-700',
  APPROVED: 'bg-green-100 text-green-700',
  REJECTED: 'bg-red-100 text-red-700',
};

export default function Registrations() {
  const { t } = useTranslation();
  const [items, setItems] = useState<RegistrationItem[]>([]);
  const [filter, setFilter] = useState<StatusFilter>('PENDING');
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const STATUS_LABEL: Record<string, string> = {
    PENDING: t('admin.registrations.filter.pending'),
    APPROVED: t('admin.registrations.filter.approved'),
    REJECTED: t('admin.registrations.filter.rejected'),
  };

  async function fetchItems() {
    setLoading(true);
    try {
      const params = filter !== 'ALL' ? `?status=${filter}` : '';
      const res = await api.get<{ items: RegistrationItem[] }>(`/api/admin/registrations${params}`);
      setItems(res.data.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, [filter]);

  async function handleApprove(id: number) {
    if (!confirm(t('admin.registrations.confirmApprove'))) return;
    try {
      await api.post(`/api/admin/registrations/${id}/approve`);
      setActionMsg(t('admin.registrations.successApprove'));
      fetchItems();
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? t('admin.registrations.errorApprove'));
    }
  }

  async function handleReject(id: number) {
    if (!rejectReason.trim()) {
      alert(t('admin.registrations.rejectModal.errorEmptyReason'));
      return;
    }
    try {
      await api.post(`/api/admin/registrations/${id}/reject`, { reason: rejectReason });
      setActionMsg(t('admin.registrations.successReject'));
      setRejectTarget(null);
      setRejectReason('');
      fetchItems();
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? t('admin.registrations.errorReject'));
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-xl font-bold text-slate-800 mb-6">{t('admin.registrations.title')}</h1>

      {actionMsg && (
        <div className="mb-4 rounded-lg bg-green-50 border border-green-200 px-3 py-2.5 text-sm text-green-700">
          {actionMsg}
          <button className="ml-3 underline" onClick={() => setActionMsg(null)}>
            {t('common.close')}
          </button>
        </div>
      )}

      <div className="flex gap-2 mb-5">
        {(['ALL', 'PENDING', 'APPROVED', 'REJECTED'] as StatusFilter[]).map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              filter === s
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {s === 'ALL' ? t('admin.registrations.filter.all') : STATUS_LABEL[s]}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-slate-400">{t('admin.registrations.loading')}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-400">{t('admin.registrations.noItems')}</p>
      ) : (
        <div className="overflow-x-auto bg-white rounded-xl shadow-sm border border-slate-200">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 text-slate-500 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">{t('admin.registrations.table.company')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.registrations.table.contact')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.registrations.table.email')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.registrations.table.status')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.registrations.table.submittedAt')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.registrations.table.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">{item.company_name}</td>
                  <td className="px-4 py-3 text-slate-600">{item.contact_name}</td>
                  <td className="px-4 py-3 text-slate-500">{item.email}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLOR[item.status] ?? 'bg-slate-100 text-slate-600'}`}>
                      {STATUS_LABEL[item.status] ?? item.status}
                    </span>
                    {item.reject_reason && (
                      <p className="text-xs text-red-500 mt-1">
                        {t('admin.registrations.rejectReason')} {item.reject_reason}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {new Date(item.created_at).toLocaleDateString('id-ID')}
                  </td>
                  <td className="px-4 py-3">
                    {item.status === 'PENDING' && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleApprove(item.id)}
                          className="text-xs bg-green-100 text-green-700 hover:bg-green-200 px-3 py-1 rounded-lg font-medium"
                        >
                          {t('admin.registrations.approveButton')}
                        </button>
                        <button
                          onClick={() => { setRejectTarget(item.id); setRejectReason(''); }}
                          className="text-xs bg-red-100 text-red-700 hover:bg-red-200 px-3 py-1 rounded-lg"
                        >
                          {t('admin.registrations.rejectButton')}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rejectTarget !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-base font-bold text-slate-800 mb-3">
              {t('admin.registrations.rejectModal.title')}
            </h3>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder={t('admin.registrations.rejectModal.reasonPlaceholder')}
              rows={3}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 mb-4"
            />
            <div className="flex gap-3 justify-end">
              <button onClick={() => setRejectTarget(null)}
                className="text-sm text-slate-600 border border-slate-300 px-4 py-2 rounded-lg">
                {t('admin.registrations.rejectModal.cancelButton')}
              </button>
              <button onClick={() => handleReject(rejectTarget!)}
                className="text-sm bg-red-500 hover:bg-red-600 text-white font-semibold px-4 py-2 rounded-lg">
                {t('admin.registrations.rejectModal.confirmButton')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
