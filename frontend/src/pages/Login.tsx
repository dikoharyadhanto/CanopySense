import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../lib/api';
import { getMe } from '../lib/adminApi';

type Step = 'credentials' | 'otp';

export default function Login() {
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
        // Device OTP challenge — show OTP step
        setPendingToken(response.data.pending_token);
        setStep('otp');
        return;
      }

      localStorage.setItem('token', response.data.access_token);
      const me = await getMe();
      navigate(me.is_global_admin || me.is_admin ? '/admin' : '/dashboard');
    } catch {
      setError('Username atau password salah. Silakan coba lagi.');
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
      setError('Kode verifikasi salah atau kadaluarsa. Silakan coba lagi.');
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
      setError('');
    } catch {
      setError('Gagal mengirim ulang kode. Coba lagi dalam beberapa saat.');
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
            Data satelit real-time<br />untuk perkebunan<br />yang lebih cerdas.
          </h2>
          <p className="text-green-300/80 text-sm leading-relaxed">
            Pantau kesehatan kanopi, tren indeks vegetasi, dan status blok estate
            Anda langsung dari citra satelit terkini.
          </p>
        </div>
        <div className="text-green-400/50 text-xs">
          CanopySense v1.5 · Phase 1 Manager Portal
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
              <h1 className="text-2xl font-bold text-gray-800 mb-1">Masuk</h1>
              <p className="text-sm text-gray-500 mb-8">
                Masuk ke Manager Portal untuk melanjutkan.
              </p>
              <form onSubmit={handleLogin} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Username
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
                    placeholder="Masukkan username"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Password
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
                    placeholder="Masukkan password"
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
                  {loading ? 'Memproses...' : 'Masuk'}
                </button>
                <div className="text-center">
                  <Link to="/forgot-password" className="text-sm text-slate-500 hover:text-slate-700 underline">
                    Lupa password?
                  </Link>
                </div>
              </form>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-gray-800 mb-1">Verifikasi Perangkat</h1>
              <p className="text-sm text-gray-500 mb-8">
                Kode verifikasi 6 digit telah dikirim ke email Anda. Masukkan kode tersebut untuk melanjutkan.
              </p>
              <form onSubmit={handleVerifyOtp} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Kode Verifikasi
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
                  {loading ? 'Memverifikasi...' : 'Verifikasi'}
                </button>
                <div className="text-center">
                  <button
                    type="button"
                    onClick={handleResendOtp}
                    className="text-sm text-green-700 hover:text-green-900 underline"
                  >
                    Kirim ulang kode
                  </button>
                  <span className="mx-2 text-gray-300">·</span>
                  <button
                    type="button"
                    onClick={() => { setStep('credentials'); setError(''); setOtp(''); }}
                    className="text-sm text-gray-500 hover:text-gray-700 underline"
                  >
                    Kembali
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
