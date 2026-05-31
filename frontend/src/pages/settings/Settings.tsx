import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api, { API_BASE } from '../../lib/api';
import { getStoredUser } from '../../lib/auth';

interface BrandingData {
  company_name: string | null;
  logo_path: string | null;
  show_name_in_header: boolean;
  show_logo_in_header: boolean;
}

interface SettingsData {
  timezone: string;
  notify_pipeline_failure: boolean;
  notify_pipeline_success: boolean;
}

type Tab = 'branding' | 'estate' | 'notifikasi';

function TabBranding({ companyId }: { companyId: number }) {
  const { t } = useTranslation();
  const [data, setData] = useState<BrandingData>({
    company_name: null, logo_path: null, show_name_in_header: false, show_logo_in_header: false,
  });
  const [loading, setLoading] = useState(true);
  const [nameInput, setNameInput] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [nameMsg, setNameMsg] = useState<string | null>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoMsg, setLogoMsg] = useState<string | null>(null);
  const [logoTs, setLogoTs] = useState(Date.now());
  const fileRef = useRef<HTMLInputElement>(null);

  async function fetchBranding() {
    try {
      const res = await api.get<BrandingData & { canonical_name?: string }>(
        `/api/companies/${companyId}/branding`
      );
      setData(res.data);
      setNameInput(res.data.company_name || '');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchBranding(); }, []);

  async function handleSaveName(e: React.FormEvent) {
    e.preventDefault();
    setNameSaving(true);
    setNameMsg(null);
    try {
      await api.patch(`/api/companies/${companyId}`, { company_name: nameInput });
      setData((d) => ({ ...d, company_name: nameInput }));
      setNameMsg(t('settings.branding.nameSaved'));
    } catch (err: any) {
      setNameMsg(err?.response?.data?.detail ?? t('settings.branding.errorSaveName'));
    } finally {
      setNameSaving(false);
    }
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    setLogoUploading(true);
    setLogoMsg(null);
    try {
      await api.post(`/api/companies/${companyId}/logo`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setData((d) => ({ ...d, logo_path: 'set' }));
      setLogoTs(Date.now());
      setLogoMsg(t('settings.branding.logoUploaded'));
    } catch (err: any) {
      setLogoMsg(err?.response?.data?.detail ?? t('settings.branding.errorUploadLogo'));
    } finally {
      setLogoUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function handleLogoDelete() {
    if (!confirm(t('settings.branding.confirmDeleteLogo'))) return;
    try {
      await api.delete(`/api/companies/${companyId}/logo`);
      setData((d) => ({ ...d, logo_path: null }));
      setLogoTs(Date.now());
      setLogoMsg(t('settings.branding.logoDeleted'));
    } catch (err: any) {
      setLogoMsg(err?.response?.data?.detail ?? t('settings.branding.errorDeleteLogo'));
    }
  }

  async function handleToggleHeader(field: 'show_name_in_header' | 'show_logo_in_header') {
    const newVal = !data[field];
    try {
      await api.patch(`/api/companies/${companyId}`, { [field]: newVal });
      setData((d) => ({ ...d, [field]: newVal }));
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? t('settings.branding.errorToggleHeader'));
    }
  }

  if (loading) return <p className="text-sm text-slate-400">{t('common.loading')}</p>;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('settings.branding.companyNameSection')}
        </h2>
        <form onSubmit={handleSaveName} className="flex gap-3">
          <input
            type="text"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            required
            placeholder={t('settings.branding.companyNamePlaceholder')}
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
          />
          <button type="submit" disabled={nameSaving}
            className="bg-[#19C853] hover:bg-green-500 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors whitespace-nowrap">
            {nameSaving ? t('settings.branding.saving') : t('settings.branding.saveButton')}
          </button>
        </form>
        {nameMsg && <p className="text-sm mt-2 text-slate-600">{nameMsg}</p>}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('settings.branding.logoSection')}
        </h2>
        {data.logo_path && (
          <div className="mb-4 flex items-center gap-4">
            <img
              src={`${API_BASE}/api/companies/${companyId}/logo?t=${logoTs}`}
              alt={t('settings.branding.logoAlt')}
              style={{ maxHeight: 48, maxWidth: 200 }}
              className="object-contain border border-slate-200 rounded p-1"
            />
            <button onClick={handleLogoDelete}
              className="text-sm text-red-600 hover:text-red-800 underline">
              {t('settings.branding.deleteLogoButton')}
            </button>
          </div>
        )}
        <div className="flex items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept=".png,.jpg,.jpeg,.svg,image/png,image/jpeg,image/svg+xml"
            onChange={handleLogoUpload}
            className="text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-4 file:rounded-lg file:border-0 file:bg-slate-100 file:text-slate-700 file:text-sm file:font-medium hover:file:bg-slate-200"
          />
          {logoUploading && <span className="text-sm text-slate-400">{t('settings.branding.logoUploading')}</span>}
        </div>
        <div className="mt-3 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5 space-y-1">
          <p className="text-xs font-medium text-slate-600">{t('settings.branding.logoGuidelines')}</p>
          <ul className="text-xs text-slate-500 space-y-0.5 list-disc list-inside">
            <li>{t('settings.branding.logoGuidelineFormat')}</li>
            <li>{t('settings.branding.logoGuidelineSize')}</li>
            <li>{t('settings.branding.logoGuidelineResize')}</li>
            <li>{t('settings.branding.logoGuidelineTransparent')}</li>
            <li>{t('settings.branding.logoGuidelineText')}</li>
          </ul>
        </div>
        {logoMsg && <p className="text-sm mt-2 text-slate-600">{logoMsg}</p>}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('settings.branding.headerVisibilitySection')}
        </h2>
        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={data.show_name_in_header}
              onChange={() => handleToggleHeader('show_name_in_header')}
              className="w-4 h-4 accent-green-600"
            />
            <span className="text-sm text-slate-700">{t('settings.branding.showNameInHeader')}</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={data.show_logo_in_header}
              onChange={() => handleToggleHeader('show_logo_in_header')}
              className="w-4 h-4 accent-green-600"
            />
            <span className="text-sm text-slate-700">{t('settings.branding.showLogoInHeader')}</span>
          </label>
        </div>
      </div>
    </div>
  );
}

function TabEstateChange({ companyId }: { companyId: number }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<string>('NONE');
  const [rejectReason, setRejectReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showWarning, setShowWarning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function fetchStatus() {
    try {
      const res = await api.get<{ estate_change_status: string; estate_change_reject_reason: string | null }>(
        `/api/companies/${companyId}/estate-change/status`
      );
      setStatus(res.data.estate_change_status);
      setRejectReason(res.data.estate_change_reject_reason);
    } catch {
      setStatus('NONE');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchStatus(); }, []);

  async function handleUpload(file: File) {
    setUploading(true);
    setMsg(null);
    const form = new FormData();
    form.append('file', file);
    try {
      await api.post(`/api/companies/${companyId}/estate-change/request`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setStatus('PENDING');
      setMsg({ type: 'success', text: t('settings.estate.successSubmit') });
    } catch (err: any) {
      setMsg({ type: 'error', text: err?.response?.data?.detail ?? t('settings.estate.errorSubmit') });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function handleCancel() {
    if (!confirm(t('settings.estate.confirmCancel'))) return;
    try {
      await api.post(`/api/companies/${companyId}/estate-change/cancel`);
      setStatus('NONE');
      setMsg({ type: 'success', text: t('settings.estate.successCancel') });
    } catch (err: any) {
      setMsg({ type: 'error', text: err?.response?.data?.detail ?? t('settings.estate.errorCancel') });
    }
  }

  if (loading) return <p className="text-sm text-slate-400">{t('common.loading')}</p>;

  const statusLabel: Record<string, string> = {
    NONE: t('settings.estate.status.none'),
    PENDING: t('settings.estate.status.pending'),
    APPROVED: t('settings.estate.status.approved'),
    REJECTED: t('settings.estate.status.rejected'),
  };
  const statusColor: Record<string, string> = {
    NONE: 'text-slate-400', PENDING: 'text-amber-600', APPROVED: 'text-green-600', REJECTED: 'text-red-600',
  };

  return (
    <div className="space-y-6">
      {showWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-base font-bold text-slate-800 mb-3">{t('settings.estate.warningTitle')}</h3>
            <p className="text-sm text-slate-600 mb-6">{t('settings.estate.warningMessage')}</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setShowWarning(false)}
                className="text-sm text-slate-600 hover:text-slate-800 border border-slate-300 px-4 py-2 rounded-lg">
                {t('settings.estate.warningCancelButton')}
              </button>
              <button
                onClick={() => { setShowWarning(false); fileRef.current?.click(); }}
                className="text-sm bg-amber-500 hover:bg-amber-600 text-white font-semibold px-4 py-2 rounded-lg"
              >
                {t('settings.estate.warningContinueButton')}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('settings.estate.sectionTitle')}
        </h2>

        <div className="mb-4">
          <span className="text-sm text-slate-500">{t('settings.estate.currentStatus')} </span>
          <span className={`text-sm font-semibold ${statusColor[status] ?? 'text-slate-600'}`}>
            {statusLabel[status] ?? status}
          </span>
        </div>

        {status === 'REJECTED' && rejectReason && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
            <strong>{t('settings.estate.rejectReason')}</strong> {rejectReason}
          </div>
        )}

        {(status === 'NONE' || status === 'REJECTED') && (
          <>
            <input
              ref={fileRef}
              type="file"
              accept=".geojson,.zip,.kml,.kmz"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
            />
            <button
              onClick={() => setShowWarning(true)}
              disabled={uploading}
              className="bg-amber-500 hover:bg-amber-600 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors"
            >
              {uploading ? t('settings.estate.uploading') : t('settings.estate.submitButton')}
            </button>
            <p className="text-xs text-slate-400 mt-2">{t('settings.estate.fileFormat')}</p>
          </>
        )}

        {status === 'PENDING' && (
          <button
            onClick={handleCancel}
            className="text-sm text-red-600 hover:text-red-800 border border-red-300 px-4 py-2 rounded-lg"
          >
            {t('settings.estate.cancelButton')}
          </button>
        )}

        {msg && (
          <p className={`text-sm mt-3 ${msg.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
            {msg.text}
          </p>
        )}
      </div>
    </div>
  );
}

function TabNotifikasi({ companyId }: { companyId: number }) {
  const { t } = useTranslation();
  const [data, setData] = useState<SettingsData>({
    timezone: 'Asia/Jakarta', notify_pipeline_failure: true, notify_pipeline_success: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.get<SettingsData>(`/api/companies/${companyId}/settings`)
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    try {
      await api.patch(`/api/companies/${companyId}/settings`, data);
      setMsg(t('settings.notifications.successSave'));
    } catch (err: any) {
      setMsg(err?.response?.data?.detail ?? t('settings.notifications.errorSave'));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-slate-400">{t('common.loading')}</p>;

  return (
    <form onSubmit={handleSave} className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('settings.notifications.sectionTitle')}
        </h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t('settings.notifications.timezoneLabel')}
            </label>
            <select
              value={data.timezone}
              onChange={(e) => setData((d) => ({ ...d, timezone: e.target.value }))}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              <option value="Asia/Jakarta">Asia/Jakarta (WIB)</option>
              <option value="Asia/Makassar">Asia/Makassar (WITA)</option>
              <option value="Asia/Jayapura">Asia/Jayapura (WIT)</option>
              <option value="UTC">UTC</option>
            </select>
          </div>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={data.notify_pipeline_failure}
              onChange={(e) => setData((d) => ({ ...d, notify_pipeline_failure: e.target.checked }))}
              className="w-4 h-4 accent-green-600"
            />
            <span className="text-sm text-slate-700">{t('settings.notifications.notifyFailure')}</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={data.notify_pipeline_success}
              onChange={(e) => setData((d) => ({ ...d, notify_pipeline_success: e.target.checked }))}
              className="w-4 h-4 accent-green-600"
            />
            <span className="text-sm text-slate-700">{t('settings.notifications.notifySuccess')}</span>
          </label>
        </div>
        <button type="submit" disabled={saving}
          className="mt-5 bg-[#19C853] hover:bg-green-500 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors">
          {saving ? t('settings.notifications.saving') : t('settings.notifications.saveButton')}
        </button>
        {msg && <p className="text-sm mt-2 text-slate-600">{msg}</p>}
      </div>
    </form>
  );
}

export default function Settings() {
  const { t } = useTranslation();
  const me = getStoredUser();
  const companyId = me?.company_id;
  const [tab, setTab] = useState<Tab>('branding');

  if (me?.role !== 'manager') {
    return (
      <div className="p-8 text-center text-slate-500 text-sm">
        {t('settings.managerOnly')}
      </div>
    );
  }

  if (!companyId) {
    return <div className="p-8 text-center text-slate-500 text-sm">{t('settings.noCompany')}</div>;
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'branding', label: t('settings.tabs.branding') },
    { key: 'estate', label: t('settings.tabs.estate') },
    { key: 'notifikasi', label: t('settings.tabs.notifications') },
  ];

  return (
    <div className="max-w-3xl mx-auto py-10 px-4">
      <h1 className="text-xl font-bold text-slate-800 mb-6">{t('settings.pageTitle')}</h1>

      <div className="flex gap-1 mb-6 border-b border-slate-200">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === key
                ? 'border-green-500 text-green-700'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'branding' && <TabBranding companyId={companyId} />}
      {tab === 'estate' && <TabEstateChange companyId={companyId} />}
      {tab === 'notifikasi' && <TabNotifikasi companyId={companyId} />}
    </div>
  );
}
