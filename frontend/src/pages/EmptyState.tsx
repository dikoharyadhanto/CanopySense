import { useTranslation } from 'react-i18next';
import { clearToken } from '../lib/auth';
import { useNavigate } from 'react-router-dom';

export default function EmptyState() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  function handleLogout() {
    clearToken();
    navigate('/login');
  }

  return (
    <div className="min-h-screen bg-[#F4FAF6] flex items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow-md p-10 w-full max-w-md text-center">
        <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-5">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-7 h-7 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
        </div>
        <h1 className="text-lg font-bold text-slate-800 mb-2">{t('emptyState.title')}</h1>
        <p className="text-sm text-slate-500 leading-relaxed mb-8">
          {t('emptyState.description')}
        </p>
        <button
          onClick={handleLogout}
          className="text-sm text-slate-500 hover:text-slate-700 underline"
        >
          {t('emptyState.logoutButton')}
        </button>
      </div>
    </div>
  );
}
