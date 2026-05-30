import { useState, useEffect } from 'react';
import api from '../lib/api';
import { PASSWORD_RE, PASSWORD_HINT } from '../lib/passwordPolicy';

interface ProfileData {
  id: number;
  username: string;
  full_name: string | null;
  email: string;
  role: string | null;
  company_id: number | null;
}

export default function Profile() {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [profileMsg, setProfileMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [profileSaving, setProfileSaving] = useState(false);

  const [showPasswordSection, setShowPasswordSection] = useState(false);
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwMsg, setPwMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [pwSaving, setPwSaving] = useState(false);

  useEffect(() => {
    api.get<ProfileData>('/auth/profile').then((r) => {
      setProfile(r.data);
      setFullName(r.data.full_name ?? '');
      setEmail(r.data.email ?? '');
      setUsername(r.data.username ?? '');
    });
  }, []);

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMsg(null);
    try {
      const res = await api.patch<ProfileData>('/auth/profile', { full_name: fullName, email, username });
      setProfile(res.data);
      setProfileMsg({ type: 'success', text: 'Profil berhasil diperbarui.' });
    } catch (err: any) {
      setProfileMsg({ type: 'error', text: err?.response?.data?.detail ?? 'Gagal menyimpan profil.' });
    } finally {
      setProfileSaving(false);
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      setPwMsg({ type: 'error', text: 'Password baru dan konfirmasi tidak cocok.' });
      return;
    }
    if (!PASSWORD_RE.test(newPw)) {
      setPwMsg({ type: 'error', text: PASSWORD_HINT });
      return;
    }
    setPwSaving(true);
    setPwMsg(null);
    try {
      await api.post('/auth/change-password', { current_password: currentPw, new_password: newPw });
      setPwMsg({ type: 'success', text: 'Password berhasil diubah.' });
      setCurrentPw(''); setNewPw(''); setConfirmPw('');
    } catch (err: any) {
      setPwMsg({ type: 'error', text: err?.response?.data?.detail ?? 'Gagal mengubah password.' });
    } finally {
      setPwSaving(false);
    }
  }

  if (!profile) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400 text-sm">Memuat profil...</p>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto py-10 px-4">
      <h1 className="text-xl font-bold text-slate-800 mb-6">Profil Saya</h1>

      {/* Profile info */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">Informasi Akun</h2>
        <form onSubmit={handleProfileSave} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">Nama Lengkap</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span>Role: <strong className="text-slate-700">{profile.role ?? '—'}</strong></span>
          </div>
          {profileMsg && (
            <p className={`text-sm ${profileMsg.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
              {profileMsg.text}
            </p>
          )}
          <button
            type="submit"
            disabled={profileSaving}
            className="bg-[#19C853] hover:bg-green-500 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors"
          >
            {profileSaving ? 'Menyimpan...' : 'Simpan Perubahan'}
          </button>
        </form>
      </div>

      {/* Change password */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <button
          type="button"
          className="flex items-center justify-between w-full text-sm font-semibold text-slate-600 uppercase tracking-wide mb-1"
          onClick={() => setShowPasswordSection((v) => !v)}
        >
          <span>Ganti Password</span>
          <span className="text-slate-400 text-xs">{showPasswordSection ? '▲' : '▼'}</span>
        </button>
        {showPasswordSection && (
          <form onSubmit={handlePasswordChange} className="space-y-4 mt-4">
            <div>
              <label className="block text-sm text-slate-600 mb-1">Password Saat Ini</label>
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                required
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Password Baru</label>
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                required
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
              <p className="text-xs text-slate-400 mt-1">{PASSWORD_HINT}</p>
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Konfirmasi Password Baru</label>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                required
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>
            {pwMsg && (
              <p className={`text-sm ${pwMsg.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                {pwMsg.text}
              </p>
            )}
            <button
              type="submit"
              disabled={pwSaving}
              className="bg-slate-700 hover:bg-slate-800 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors"
            >
              {pwSaving ? 'Menyimpan...' : 'Ubah Password'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
