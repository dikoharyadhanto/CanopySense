import { useEffect, useState } from 'react';
import type { Feature } from 'geojson';
import { useTranslation } from 'react-i18next';
import api from '../../lib/api';
import BlockImportMap from '../../components/BlockImportMap';

interface RequestItem {
  company_id: number;
  company_name: string;
  estate_change_status: string;
  estate_change_requested_at: string | null;
  estate_change_reject_reason: string | null;
}

type StatusFilter = 'ALL' | 'PENDING' | 'APPROVED' | 'REJECTED';

const STATUS_COLOR: Record<string, string> = {
  PENDING: 'bg-amber-100 text-amber-700',
  APPROVED: 'bg-green-100 text-green-700',
  REJECTED: 'bg-red-100 text-red-700',
};

export default function EstateChangeRequests() {
  const { t } = useTranslation();
  const [items, setItems] = useState<RequestItem[]>([]);
  const [filter, setFilter] = useState<StatusFilter>('PENDING');
  const [loading, setLoading] = useState(true);

  const [preview, setPreview] = useState<{ companyId: number; features: Feature[] } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [rejectTarget, setRejectTarget] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const STATUS_LABEL: Record<string, string> = {
    PENDING: t('admin.estateChange.filter.pending'),
    APPROVED: t('admin.estateChange.filter.approved'),
    REJECTED: t('admin.estateChange.filter.rejected'),
  };

  async function fetchItems() {
    setLoading(true);
    try {
      const params = filter !== 'ALL' ? `?status=${filter}` : '';
      const res = await api.get<{ items: RequestItem[] }>(`/api/admin/estate-change-requests${params}`);
      setItems(res.data.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, [filter]);

  async function handlePreview(companyId: number) {
    setPreview(null);
    setPreviewLoading(true);
    try {
      const res = await api.get<{ features: Feature[] }>(
        `/api/admin/estate-change-requests/${companyId}/preview`
      );
      setPreview({ companyId, features: res.data.features });
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? t('admin.estateChange.preview.errorLoad'));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleApprove(companyId: number) {
    if (!confirm(t('admin.estateChange.confirmApprove'))) return;
    try {
      await api.post(`/api/admin/estate-change-requests/${companyId}/approve`);
      setActionMsg(t('admin.estateChange.successApprove'));
      setPreview(null);
      fetchItems();
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? t('admin.estateChange.errorApprove'));
    }
  }

  async function handleReject(companyId: number) {
    if (!rejectReason.trim()) {
      alert(t('admin.estateChange.rejectModal.errorEmptyReason'));
      return;
    }
    try {
      await api.post(`/api/admin/estate-change-requests/${companyId}/reject`, { reason: rejectReason });
      setActionMsg(t('admin.estateChange.successReject'));
      setRejectTarget(null);
      setRejectReason('');
      fetchItems();
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? t('admin.estateChange.errorReject'));
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-xl font-bold text-slate-800 mb-6">{t('admin.estateChange.title')}</h1>

      {actionMsg && (
        <div className="mb-4 rounded-lg bg-green-50 border border-green-200 px-3 py-2.5 text-sm text-green-700">
          {actionMsg}
          <button className="ml-3 underline text-green-700" onClick={() => setActionMsg(null)}>
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
            {s === 'ALL' ? t('admin.estateChange.filter.all') : STATUS_LABEL[s]}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-slate-400">{t('admin.estateChange.loading')}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-400">{t('admin.estateChange.noItems')}</p>
      ) : (
        <div className="overflow-x-auto bg-white rounded-xl shadow-sm border border-slate-200">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 text-slate-500 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">{t('admin.estateChange.table.company')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.estateChange.table.status')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.estateChange.table.submittedAt')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.estateChange.table.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.company_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">{item.company_name}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLOR[item.estate_change_status] ?? 'bg-slate-100 text-slate-600'}`}>
                      {STATUS_LABEL[item.estate_change_status] ?? item.estate_change_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {item.estate_change_requested_at
                      ? new Date(item.estate_change_requested_at).toLocaleString('id-ID')
                      : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2 flex-wrap">
                      <button
                        onClick={() => handlePreview(item.company_id)}
                        className="text-xs bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-3 py-1 rounded-lg"
                      >
                        {previewLoading ? t('admin.estateChange.previewLoading') : t('admin.estateChange.previewButton')}
                      </button>
                      {item.estate_change_status === 'PENDING' && (
                        <>
                          <button
                            onClick={() => handleApprove(item.company_id)}
                            className="text-xs bg-green-100 text-green-700 hover:bg-green-200 px-3 py-1 rounded-lg font-medium"
                          >
                            {t('admin.estateChange.approveButton')}
                          </button>
                          <button
                            onClick={() => { setRejectTarget(item.company_id); setRejectReason(''); }}
                            className="text-xs bg-red-100 text-red-700 hover:bg-red-200 px-3 py-1 rounded-lg"
                          >
                            {t('admin.estateChange.rejectButton')}
                          </button>
                        </>
                      )}
                    </div>
                    {item.estate_change_reject_reason && (
                      <p className="text-xs text-red-500 mt-1">
                        {t('admin.estateChange.rejectReason')} {item.estate_change_reject_reason}
                      </p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {preview && (
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-700">
              {t('admin.estateChange.preview.title', { companyId: preview.companyId })}
            </h2>
            <button onClick={() => setPreview(null)} className="text-xs text-slate-400 hover:text-slate-600 underline">
              {t('admin.estateChange.preview.closeButton')}
            </button>
          </div>
          {preview.features.length > 0 ? (
            <div className="h-80 rounded-lg overflow-hidden">
              <BlockImportMap features={preview.features} />
            </div>
          ) : (
            <p className="text-sm text-slate-400">{t('admin.estateChange.preview.noFeatures')}</p>
          )}
        </div>
      )}

      {rejectTarget !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-base font-bold text-slate-800 mb-3">
              {t('admin.estateChange.rejectModal.title')}
            </h3>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder={t('admin.estateChange.rejectModal.reasonPlaceholder')}
              rows={3}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 mb-4"
            />
            <div className="flex gap-3 justify-end">
              <button onClick={() => setRejectTarget(null)}
                className="text-sm text-slate-600 border border-slate-300 px-4 py-2 rounded-lg">
                {t('admin.estateChange.rejectModal.cancelButton')}
              </button>
              <button onClick={() => handleReject(rejectTarget!)}
                className="text-sm bg-red-500 hover:bg-red-600 text-white font-semibold px-4 py-2 rounded-lg">
                {t('admin.estateChange.rejectModal.confirmButton')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
