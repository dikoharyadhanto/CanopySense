import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { getStoredUser } from '../lib/auth';
import api from '../lib/api';
import { PASSWORD_RE, PASSWORD_HINT_KEY } from '../lib/passwordPolicy';

interface ProfileData {
  id: number;
  username: string;
  full_name: string | null;
  email: string;
  role: string | null;
  company_id: number | null;
  company_name: string | null;
}

interface Member {
  id: number;
  username: string;
  full_name: string | null;
  email: string;
  role: string;
  joined_at: string;
  leave_request_status: string | null;
}

type Tab = 'profil' | 'anggota';

function TabProfil() {
  const { t } = useTranslation();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [fullName, setFullName] = useState('');
  const [profileMsg, setProfileMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [profileSaving, setProfileSaving] = useState(false);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwMsg, setPwMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [pwSaving, setPwSaving] = useState(false);

  useEffect(() => {
    api.get<ProfileData>('/auth/profile').then((r) => {
      setProfile(r.data);
      setFullName(r.data.full_name ?? '');
    });
  }, []);

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMsg(null);
    try {
      const res = await api.patch<ProfileData>('/auth/profile', { full_name: fullName });
      setProfile(res.data);
      setProfileMsg({ type: 'success', text: t('profile.accountInfo.successSave') });
    } catch (err: any) {
      setProfileMsg({ type: 'error', text: err?.response?.data?.detail ?? t('profile.accountInfo.errorSave') });
    } finally {
      setProfileSaving(false);
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      setPwMsg({ type: 'error', text: t('profile.changePassword.errorMismatch') });
      return;
    }
    if (!PASSWORD_RE.test(newPw)) {
      setPwMsg({ type: 'error', text: t(PASSWORD_HINT_KEY) });
      return;
    }
    setPwSaving(true);
    setPwMsg(null);
    try {
      await api.post('/auth/change-password', { current_password: currentPw, new_password: newPw });
      setPwMsg({ type: 'success', text: t('profile.changePassword.successChange') });
      setCurrentPw(''); setNewPw(''); setConfirmPw('');
    } catch (err: any) {
      setPwMsg({ type: 'error', text: err?.response?.data?.detail ?? t('profile.changePassword.errorSave') });
    } finally {
      setPwSaving(false);
    }
  }

  if (!profile) {
    return <p className="text-slate-400 text-sm py-8 text-center">{t('profile.accountInfo.loadingProfile')}</p>;
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('profile.accountInfo.sectionTitle')}
        </h2>
        <form onSubmit={handleProfileSave} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">{t('profile.accountInfo.fullNameLabel')}</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">{t('profile.accountInfo.usernameLabel')}</label>
            <div className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 text-slate-500 select-all">
              {profile.username}
            </div>
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">{t('profile.accountInfo.emailLabel')}</label>
            <div className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 text-slate-500 select-all">
              {profile.email}
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span>{t('profile.accountInfo.roleLabel')} <strong className="text-slate-700">{profile.role ?? '—'}</strong></span>
          </div>
          <div className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${
            profile.company_name
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-slate-50 text-slate-400 border border-slate-200'
          }`}>
            <span>{profile.company_name
              ? t('profile.accountInfo.companyConnected', { companyName: profile.company_name })
              : t('profile.accountInfo.companyNotConnected')
            }</span>
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
            {profileSaving ? t('profile.accountInfo.saving') : t('profile.accountInfo.saveButton')}
          </button>
        </form>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('profile.changePassword.sectionTitle')}
        </h2>
        <form onSubmit={handlePasswordChange} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">{t('profile.changePassword.currentPasswordLabel')}</label>
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">{t('profile.changePassword.newPasswordLabel')}</label>
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <p className="text-xs text-slate-400 mt-1">{t(PASSWORD_HINT_KEY)}</p>
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">{t('profile.changePassword.confirmPasswordLabel')}</label>
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
            {pwSaving ? t('profile.changePassword.saving') : t('profile.changePassword.submitButton')}
          </button>
        </form>
      </div>
    </div>
  );
}

function TabAnggota() {
  const { t } = useTranslation();
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
      setError(t('profile.members.errorLoad'));
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
      setInviteMsg({ type: 'success', text: t('profile.members.inviteSuccess', { email: inviteEmail }) });
      setInviteEmail('');
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? t('profile.members.inviteError');
      setInviteMsg({ type: 'error', text: detail });
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleRemove(userId: number) {
    if (!confirm(t('profile.members.confirmRemove'))) return;
    try {
      await api.delete(`/api/companies/${companyId}/members/${userId}`);
      setMembers((prev) => prev.filter((m) => m.id !== userId));
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? t('profile.members.errorRemove'));
    }
  }

  async function handleLeaveAction(userId: number, action: 'approve' | 'reject') {
    try {
      await api.post(`/api/companies/${companyId}/members/leave-approve/${userId}`, { action });
      fetchMembers();
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? t('profile.members.errorLeaveAction'));
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('profile.members.inviteSection')}
        </h2>
        <form onSubmit={handleInvite} className="flex gap-3">
          <input
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            required
            placeholder={t('profile.members.invitePlaceholder')}
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
          />
          <button
            type="submit"
            disabled={inviteLoading}
            className="bg-[#19C853] hover:bg-green-500 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors whitespace-nowrap"
          >
            {inviteLoading ? t('profile.members.inviting') : t('profile.members.inviteButton')}
          </button>
        </form>
        {inviteMsg && (
          <p className={`text-sm mt-2 ${inviteMsg.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
            {inviteMsg.text}
          </p>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-4">
          {t('profile.members.membersSection')}
        </h2>
        {loading ? (
          <p className="text-sm text-slate-400">{t('profile.members.loading')}</p>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : members.length === 0 ? (
          <p className="text-sm text-slate-400">{t('profile.members.noMembers')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 text-left">
                  <th className="pb-2 font-medium">{t('profile.members.table.name')}</th>
                  <th className="pb-2 font-medium">{t('profile.members.table.email')}</th>
                  <th className="pb-2 font-medium">{t('profile.members.table.role')}</th>
                  <th className="pb-2 font-medium">{t('profile.members.table.status')}</th>
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
                            {t('profile.members.approveLeave')}
                          </button>
                          <button
                            onClick={() => handleLeaveAction(m.id, 'reject')}
                            className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded hover:bg-red-200"
                          >
                            {t('profile.members.rejectLeave')}
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
                          {t('profile.members.removeButton')}
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

export default function Profile() {
  const { t } = useTranslation();
  const me = getStoredUser();
  const isManager = me?.role === 'manager';
  const [activeTab, setActiveTab] = useState<Tab>('profil');

  const tabs: { key: Tab; label: string }[] = [
    { key: 'profil', label: t('profile.tabs.profile') },
    ...(isManager ? [{ key: 'anggota' as Tab, label: t('profile.tabs.members') }] : []),
  ];

  return (
    <div className="max-w-3xl mx-auto py-10 px-4">
      <h1 className="text-xl font-bold text-slate-800 mb-6">{t('profile.pageTitle')}</h1>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
              activeTab === key
                ? 'bg-white border border-b-white border-slate-200 text-green-700 -mb-px'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'profil' && <TabProfil />}
      {activeTab === 'anggota' && isManager && <TabAnggota />}
    </div>
  );
}
