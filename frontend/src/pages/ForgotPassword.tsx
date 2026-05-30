import { useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../lib/api';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post('/auth/forgot-password', { email });
    } catch {
      // intentionally swallow — always show confirmation (anti-enumeration)
    } finally {
      setLoading(false);
      setSubmitted(true);
    }
  }

  return (
    <div className="min-h-screen bg-[#F4FAF6] flex items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow-md p-8 w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="w-10 h-10 rounded-xl bg-[#19C853] flex items-center justify-center text-white text-lg font-bold mx-auto mb-3">
            C
          </div>
          <h1 className="text-lg font-bold text-slate-800">Lupa Password</h1>
          <p className="text-xs text-slate-500 mt-1">
            Masukkan email terdaftar Anda. Kami akan mengirimkan tautan reset password.
          </p>
        </div>

        {submitted ? (
          <div className="text-center">
            <div className="text-green-600 text-3xl mb-3">✓</div>
            <p className="text-sm text-slate-700 mb-5">
              Jika email tersebut terdaftar, tautan reset password telah dikirimkan. Periksa kotak masuk Anda.
            </p>
            <Link to="/login" className="text-sm text-green-700 hover:text-green-900 underline">
              Kembali ke login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-slate-600 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="nama@perusahaan.com"
                className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#19C853] hover:bg-green-500 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg text-sm transition-colors"
            >
              {loading ? 'Mengirim...' : 'Kirim Tautan Reset'}
            </button>
            <div className="text-center">
              <Link to="/login" className="text-sm text-slate-500 hover:text-slate-700 underline">
                Kembali ke login
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
