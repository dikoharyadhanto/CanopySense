import { useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../lib/api';

export default function Register() {
  const [form, setForm] = useState({
    company_name: '', contact_name: '', email: '', phone: '',
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.post('/auth/register', form);
      setSuccess(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Gagal mengirim pendaftaran. Coba lagi.');
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F4FAF6] px-4">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 w-full max-w-md text-center">
          <div className="w-14 h-14 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-lg font-bold text-slate-800 mb-2">Pendaftaran Terkirim</h2>
          <p className="text-sm text-slate-500 mb-6">
            Pendaftaran Anda sedang ditinjau oleh administrator. Anda akan mendapat email konfirmasi setelah diproses.
          </p>
          <Link to="/login" className="text-sm text-green-700 hover:text-green-900 underline">
            Kembali ke Login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F4FAF6] px-4">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 w-full max-w-md">
        <div className="flex items-center gap-2.5 mb-7">
          <div className="w-8 h-8 rounded-md bg-[#19C853] flex items-center justify-center
                          text-white text-sm font-bold select-none">
            C
          </div>
          <div>
            <div className="text-sm font-bold text-slate-800">CanopySense</div>
            <div className="text-[10px] text-slate-400">Daftarkan Perusahaan Anda</div>
          </div>
        </div>

        <h1 className="text-xl font-bold text-slate-800 mb-1">Daftar Perusahaan</h1>
        <p className="text-sm text-slate-500 mb-6">
          Isi formulir di bawah untuk mendaftarkan perusahaan Anda. Administrator akan meninjau pendaftaran Anda.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Nama Perusahaan</label>
            <input
              type="text"
              name="company_name"
              value={form.company_name}
              onChange={handleChange}
              required
              placeholder="PT. Contoh Perkebunan"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Nama Kontak</label>
            <input
              type="text"
              name="contact_name"
              value={form.contact_name}
              onChange={handleChange}
              required
              placeholder="Nama lengkap"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              required
              placeholder="email@perusahaan.com"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Nomor Telepon <span className="text-slate-400 font-normal">(opsional)</span>
            </label>
            <input
              type="tel"
              name="phone"
              value={form.phone}
              onChange={handleChange}
              placeholder="+62..."
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
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
            {loading ? 'Mengirim...' : 'Kirim Pendaftaran'}
          </button>

          <div className="text-center">
            <Link to="/login" className="text-sm text-slate-500 hover:text-slate-700 underline">
              Sudah punya akun? Masuk
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
