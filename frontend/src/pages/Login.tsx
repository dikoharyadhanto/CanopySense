import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api from '../lib/api';
import { getMe } from '../lib/adminApi';

type Step = 'credentials' | 'otp';

export default function Login() {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [pendingToken, setPendingToken] = useState('');
  const [step, setStep] = useState<Step>('credentials');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      const response = await api.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      if (response.status === 202) {
        setPendingToken(response.data.pending_token);
        setStep('otp');
        return;
      }

      localStorage.setItem('token', response.data.access_token);
      const me = await getMe();
      navigate(me.is_global_admin || me.is_admin ? '/admin' : '/dashboard');
    } catch {
      setError(t('auth.login.errorInvalid'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const response = await api.post('/auth/verify-device', {
        pending_token: pendingToken,
        otp_code: otp,
      });
      localStorage.setItem('token', response.data.access_token);
      const me = await getMe();
      navigate(me.is_global_admin || me.is_admin ? '/admin' : '/dashboard');
    } catch {
      setError(t('auth.otp.errorInvalid'));
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setError('');
    try {
      const response = await api.post('/auth/resend-otp', {
        pending_token: pendingToken,
      });
      setPendingToken(response.data.pending_token);
    } catch {
      setError(t('auth.otp.errorResend'));
    }
  };

  return (
    <div className="flex h-screen">
      {/* Left — brand panel */}
      <div className="hidden lg:flex w-[480px] flex-shrink-0 flex-col justify-between bg-[#1B3A2D] px-12 py-10">
        <div>
          <div className="flex items-center gap-3 mb-12">
            <div className="w-9 h-9 rounded-lg bg-[#19C853] flex items-center justify-center text-white text-lg font-bold select-none">
              C
            </div>
            <div>
              <div className="text-white font-bold text-base leading-tight">CanopySense</div>
              <div className="text-green-300 text-xs">Monitoring Perkebunan Karet</div>
            </div>
          </div>
          <h2 className="text-white text-2xl font-bold leading-snug mb-4">
            {t('auth.brandPanel.tagline')}
          </h2>
          <p className="text-green-300/80 text-sm leading-relaxed">
            {t('auth.brandPanel.description')}
          </p>
        </div>
        <div className="text-green-400/50 text-xs">
          {t('auth.brandPanel.version')}
        </div>
      </div>

      {/* Right — form panel */}
      <div className="flex-1 flex flex-col items-center justify-center bg-[#F4FAF6] px-6">
        {/* Mobile brand header */}
        <div className="flex lg:hidden items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-lg bg-green-600 flex items-center justify-center text-white font-bold text-sm">
            C
          </div>
          <span className="font-bold text-gray-800">CanopySense</span>
        </div>

        <div className="w-full max-w-sm">
          {step === 'credentials' ? (
            <>
              <h1 className="text-2xl font-bold text-gray-800 mb-1">{t('auth.login.title')}</h1>
              <p className="text-sm text-gray-500 mb-8">{t('auth.login.subtitle')}</p>
              <form onSubmit={handleLogin} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    {t('auth.login.usernameLabel')}
                  </label>
                  <input
                    type="text"
                    autoComplete="username"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                               focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent
                               bg-white text-gray-900 placeholder-gray-400"
                    placeholder={t('auth.login.usernamePlaceholder')}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    {t('auth.login.passwordLabel')}
                  </label>
                  <input
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                               focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent
                               bg-white text-gray-900 placeholder-gray-400"
                    placeholder={t('auth.login.passwordPlaceholder')}
                  />
                </div>
                {error && (
                  <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
                    {error}
                  </div>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-[#19C853] hover:bg-green-500 disabled:opacity-60 disabled:cursor-not-allowed
                             text-white font-semibold py-2.5 rounded-lg text-sm transition-colors"
                >
                  {loading ? t('auth.login.submitting') : t('auth.login.submitButton')}
                </button>
                <div className="text-center space-y-1">
                  <Link to="/forgot-password" className="block text-sm text-slate-500 hover:text-slate-700 underline">
                    {t('auth.login.forgotPassword')}
                  </Link>
                  <Link to="/register" className="block text-sm text-green-700 hover:text-green-900 underline">
                    {t('auth.login.registerLink')}
                  </Link>
                </div>
              </form>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-gray-800 mb-1">{t('auth.otp.title')}</h1>
              <p className="text-sm text-gray-500 mb-8">{t('auth.otp.subtitle')}</p>
              <form onSubmit={handleVerifyOtp} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    {t('auth.otp.codeLabel')}
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    required
                    autoFocus
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                               focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent
                               bg-white text-gray-900 placeholder-gray-400 tracking-widest text-center text-lg"
                    placeholder="000000"
                  />
                </div>
                {error && (
                  <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
                    {error}
                  </div>
                )}
                <button
                  type="submit"
                  disabled={loading || otp.length !== 6}
                  className="w-full bg-[#19C853] hover:bg-green-500 disabled:opacity-60 disabled:cursor-not-allowed
                             text-white font-semibold py-2.5 rounded-lg text-sm transition-colors"
                >
                  {loading ? t('auth.otp.verifying') : t('auth.otp.verifyButton')}
                </button>
                <div className="text-center">
                  <button
                    type="button"
                    onClick={handleResendOtp}
                    className="text-sm text-green-700 hover:text-green-900 underline"
                  >
                    {t('auth.otp.resendButton')}
                  </button>
                  <span className="mx-2 text-gray-300">·</span>
                  <button
                    type="button"
                    onClick={() => { setStep('credentials'); setError(''); setOtp(''); }}
                    className="text-sm text-gray-500 hover:text-gray-700 underline"
                  >
                    {t('auth.otp.backButton')}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
