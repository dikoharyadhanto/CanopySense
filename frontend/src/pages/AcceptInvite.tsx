import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api from '../lib/api';

export default function AcceptInvite() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [companyName, setCompanyName] = useState<string | null>(null);

  async function handleAccept() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post<{
        message: string;
        company_name: string | null;
        needs_setup: boolean;
        setup_token?: string;
      }>('/auth/accept-viewer-invite', { token });
      setCompanyName(res.data.company_name);
      if (res.data.needs_setup && res.data.setup_token) {
        navigate(`/setup?token=${encodeURIComponent(res.data.setup_token)}`);
        return;
      }
      setDone(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t('auth.acceptInvite.errorExpired'));
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-[#F4FAF6] flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm text-center">
          <p className="text-red-600 text-sm">{t('auth.acceptInvite.invalidToken')}</p>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="min-h-screen bg-[#F4FAF6] flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm text-center">
          <div className="text-green-600 text-3xl mb-3">✓</div>
          <h1 className="text-lg font-bold text-slate-800 mb-2">{t('auth.acceptInvite.successTitle')}</h1>
          {companyName && (
            <p className="text-sm text-slate-500 mb-5">
              {t('auth.acceptInvite.successMessage', { companyName })}
            </p>
          )}
          <button
            onClick={() => navigate('/login')}
            className="w-full py-2 bg-[#19C853] text-white text-sm rounded-lg hover:bg-green-500 font-semibold"
          >
            {t('auth.acceptInvite.goToLoginButton')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F4FAF6] flex items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm text-center">
        <div className="w-10 h-10 rounded-xl bg-[#19C853] flex items-center justify-center text-white text-lg font-bold mx-auto mb-4">
          C
        </div>
        <h1 className="text-lg font-bold text-slate-800 mb-2">{t('auth.acceptInvite.title')}</h1>
        <p className="text-sm text-slate-500 mb-6">{t('auth.acceptInvite.subtitle')}</p>
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700 mb-4">
            {error}
          </div>
        )}
        <button
          onClick={handleAccept}
          disabled={loading}
          className="w-full bg-[#19C853] hover:bg-green-500 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg text-sm transition-colors"
        >
          {loading ? t('auth.acceptInvite.accepting') : t('auth.acceptInvite.acceptButton')}
        </button>
      </div>
    </div>
  );
}
