import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api from '../lib/api';
import { PASSWORD_RE, PASSWORD_HINT_KEY } from '../lib/passwordPolicy';

export default function ResetPassword() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPw !== confirmPw) {
      setError(t('auth.resetPassword.errorMismatch'));
      return;
    }
    if (!PASSWORD_RE.test(newPw)) {
      setError(t(PASSWORD_HINT_KEY));
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/reset-password', { token, new_password: newPw });
      setDone(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t('auth.resetPassword.errorExpired'));
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-[#F4FAF6] flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm text-center">
          <p className="text-red-600 text-sm">{t('auth.resetPassword.invalidToken')}</p>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="min-h-screen bg-[#F4FAF6] flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm text-center">
          <div className="text-green-600 text-3xl mb-3">✓</div>
          <h1 className="text-lg font-bold text-slate-800 mb-2">{t('auth.resetPassword.successTitle')}</h1>
          <p className="text-sm text-slate-500 mb-5">{t('auth.resetPassword.successMessage')}</p>
          <button
            onClick={() => navigate('/login')}
            className="w-full py-2 bg-[#19C853] text-white text-sm rounded-lg hover:bg-green-500 font-semibold"
          >
            {t('auth.resetPassword.goToLoginButton')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F4FAF6] flex items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="w-10 h-10 rounded-xl bg-[#19C853] flex items-center justify-center text-white text-lg font-bold mx-auto mb-3">
            C
          </div>
          <h1 className="text-lg font-bold text-slate-800">{t('auth.resetPassword.title')}</h1>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">
              {t('auth.resetPassword.newPasswordLabel')}
            </label>
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <p className="text-xs text-slate-400 mt-1">{t(PASSWORD_HINT_KEY)}</p>
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">
              {t('auth.resetPassword.confirmPasswordLabel')}
            </label>
            <input
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#19C853] hover:bg-green-500 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg text-sm transition-colors"
          >
            {loading ? t('auth.resetPassword.submitting') : t('auth.resetPassword.submitButton')}
          </button>
        </form>
      </div>
    </div>
  );
}
