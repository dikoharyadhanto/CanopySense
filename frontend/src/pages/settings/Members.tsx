import { useState, useEffect } from 'react';
import { getStoredUser } from '../../lib/auth';
import api from '../../lib/api';

interface Member {
  id: number;
  username: string;
  full_name: string | null;
  email: string;
  role: string;
  joined_at: string;
  leave_request_status: string | null;
}

export default function Members() {
  const me = getStoredUser();
  const companyId = me?.company_id;

  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteMsg, setInviteMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  async function fetchMembers() {
    if (!companyId) return;
    try {
      const res = await api.get<{ members: Member[] }>(`/api/companies/${companyId}/members`);
      setMembers(res.data.members);
    } catch {
      setError('Gagal memuat daftar anggota.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchMembers(); }, []);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviteLoading(true);
    setInviteMsg(null);
    try {
      await api.post(`/api/companies/${companyId}/members/invite`, { email: inviteEmail });
      setInviteMsg({ type: 'success', text: `Undangan dikirim ke ${inviteEmail}.` });
      setInviteEmail('');
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? 'Gagal mengirim undangan.';
      setInviteMsg({ type: 'error', text: detail });
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleRemove(userId: number) {
    if (!confirm('Hapus anggota ini dari perusahaan?')) return;
    try {
      await api.delete(`/api/companies/${companyId}/members/${userId}`);
      setMembers((prev) => prev.filter((m) => m.id !== userId));
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? 'Gagal menghapus anggota.');
    }
  }

  async function handleLeaveAction(userId: number, action: 'approve' | 'reject') {
    try {
      await api.post(`/api/companies/${companyId}/members/leave-approve/${userId}`, { action });
      fetchMembers();
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? 'Gagal memproses permintaan.');
    }
  }

  if (me?.role !== 'manager') {
    return (
      <div className="p-8 text-center text-slate-500 text-sm">
        Halaman ini hanya tersedia untuk Manager.
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto py-10 px-4">
      <h1 className="text-xl font-bold text-slate-800 mb-6">Manajemen Anggota</h1>

      {/* Invite form */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">Undang Viewer</h2>
        <form onSubmit={handleInvite} className="flex gap-3">
          <input
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            required
            placeholder="email@contoh.com"
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
          />
          <button
            type="submit"
            disabled={inviteLoading}
            className="bg-[#19C853] hover:bg-green-500 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors whitespace-nowrap"
          >
            {inviteLoading ? 'Mengirim...' : 'Kirim Undangan'}
          </button>
        </form>
        {inviteMsg && (
          <p className={`text-sm mt-2 ${inviteMsg.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
            {inviteMsg.text}
          </p>
        )}
      </div>

      {/* Member list */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">Daftar Anggota</h2>

        {loading ? (
          <p className="text-sm text-slate-400">Memuat...</p>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : members.length === 0 ? (
          <p className="text-sm text-slate-400">Belum ada anggota.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 text-left">
                  <th className="pb-2 font-medium">Nama</th>
                  <th className="pb-2 font-medium">Email</th>
                  <th className="pb-2 font-medium">Role</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="py-2.5 pr-4">{m.full_name || m.username}</td>
                    <td className="py-2.5 pr-4 text-slate-500">{m.email}</td>
                    <td className="py-2.5 pr-4">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        m.role === 'viewer' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'
                      }`}>
                        {m.role}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4">
                      {m.leave_request_status === 'PENDING' ? (
                        <div className="flex gap-1">
                          <button
                            onClick={() => handleLeaveAction(m.id, 'approve')}
                            className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded hover:bg-green-200"
                          >
                            Approve Leave
                          </button>
                          <button
                            onClick={() => handleLeaveAction(m.id, 'reject')}
                            className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded hover:bg-red-200"
                          >
                            Reject
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">{m.leave_request_status ?? '—'}</span>
                      )}
                    </td>
                    <td className="py-2.5">
                      {m.role === 'viewer' && (
                        <button
                          onClick={() => handleRemove(m.id)}
                          className="text-xs text-red-600 hover:text-red-800 underline"
                        >
                          Hapus
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
