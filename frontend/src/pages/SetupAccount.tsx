import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import api from '../lib/api';

const PASSWORD_RE = /^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9!@#$%^&*()\-_=+\[\]{};:'",.<>/?\\|`~]).{12,}$/;

function EyeIcon({ open }: { open: boolean }) {
  return open ? (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.477 0-8.268-2.943-9.542-7a9.956 9.956 0 012.223-3.592M6.53 6.533A9.956 9.956 0 0112 5c4.478 0 8.268 2.943 9.542 7a9.978 9.978 0 01-4.293 5.23M3 3l18 18" />
    </svg>
  );
}

export default function SetupAccount() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Token can be pre-filled from URL ?token=... (admin sends link with token)
  const [token, setToken] = useState(searchParams.get('token') ?? '');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError('Password dan konfirmasi tidak cocok');
      return;
    }
    if (!PASSWORD_RE.test(password)) {
      setError('Password harus minimal 12 karakter, mengandung huruf besar, huruf kecil, dan angka atau karakter spesial');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.post('/auth/setup', {
        token,
        new_password: password,
        full_name: fullName,
        username,
      });
      setDone(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Setup failed. Token may be invalid or expired.');
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm text-center">
          <div className="text-green-600 text-3xl mb-3">✓</div>
          <h1 className="text-lg font-bold text-slate-800 mb-2">Account Setup Complete</h1>
          <p className="text-sm text-slate-500 mb-5">
            Your credentials have been saved. You can now log in.
          </p>
          <button
            onClick={() => navigate('/login')}
            className="w-full py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="w-10 h-10 rounded-xl bg-indigo-500 flex items-center justify-center
                          text-white text-lg font-bold mx-auto mb-3">
            C
          </div>
          <h1 className="text-lg font-bold text-slate-800">Set Up Your Account</h1>
          <p className="text-xs text-slate-500 mt-1">
            Enter the setup token provided by your admin to activate your account.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">Setup Token</label>
            <input
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
              placeholder="Paste the token from your admin"
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Full Name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full border border-slate-300 rounded-md px-3 py-2 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                tabIndex={-1}
              >
                <EyeIcon open={showPassword} />
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Min. 12 karakter · huruf besar · huruf kecil · angka atau simbol
            </p>
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Confirm Password</label>
            <div className="relative">
              <input
                type={showConfirm ? 'text' : 'password'}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                className="w-full border border-slate-300 rounded-md px-3 py-2 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              <button
                type="button"
                onClick={() => setShowConfirm((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                tabIndex={-1}
              >
                <EyeIcon open={showConfirm} />
              </button>
            </div>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50 font-medium mt-2"
          >
            {submitting ? 'Setting up...' : 'Activate Account'}
          </button>
        </form>
      </div>
    </div>
  );
}
