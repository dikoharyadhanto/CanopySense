import { useEffect, useState } from 'react';
import {
  listInternalAdmins,
  createInternalAdmin,
  updateInternalAdminStatus,
  getMe,
  type InternalAdmin,
} from '../../lib/adminApi';

export default function UserManagement() {
  const [admins, setAdmins] = useState<InternalAdmin[]>([]);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ email: '', full_name: '', username: '', password: '' });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  function loadAdmins() {
    listInternalAdmins()
      .then(setAdmins)
      .catch(() => setError('Failed to load admins'));
  }

  useEffect(() => {
    getMe().then((me) => setIsSuperAdmin(me.is_global_admin));
    loadAdmins();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await createInternalAdmin(form);
      setShowCreate(false);
      setForm({ email: '', full_name: '', username: '', password: '' });
      loadAdmins();
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail ?? 'Failed to create admin');
    } finally {
      setCreating(false);
    }
  }

  async function handleToggle(userId: number, currentActive: boolean) {
    await updateInternalAdminStatus(userId, !currentActive);
    loadAdmins();
  }

  if (!isSuperAdmin) {
    return (
      <div className="flex-1 p-6">
        <div className="text-red-600 font-semibold">Super-admin access required.</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800">Internal Admin Users</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
        >
          + New Admin
        </button>
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-96">
            <h2 className="text-base font-semibold text-slate-800 mb-4">Create Internal Admin</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              {(['email', 'full_name', 'username'] as const).map((field) => (
                <div key={field}>
                  <label className="block text-sm text-slate-600 mb-1 capitalize">
                    {field.replace('_', ' ')}
                  </label>
                  <input
                    type={field === 'email' ? 'email' : 'text'}
                    value={form[field]}
                    onChange={(e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))}
                    required
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  />
                </div>
              ))}
              <div>
                <label className="block text-sm text-slate-600 mb-1">Password</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                  required
                  minLength={8}
                  className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
              {createError && <p className="text-red-500 text-xs">{createError}</p>}
              <div className="flex gap-2 justify-end pt-1">
                <button
                  type="button"
                  onClick={() => { setShowCreate(false); setCreateError(null); }}
                  className="px-3 py-2 text-sm text-slate-600 hover:text-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {error && <div className="text-red-600 text-sm mb-4">{error}</div>}
      <div className="bg-white rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
              <th className="px-4 py-3">Username</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {admins.map((a) => (
              <tr key={a.id} className="border-b border-slate-50 hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-600">{a.username}</td>
                <td className="px-4 py-3 text-slate-700">{a.full_name}</td>
                <td className="px-4 py-3 text-slate-500">{a.email}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    a.is_global_admin ? 'bg-purple-100 text-purple-700' : 'bg-indigo-100 text-indigo-600'
                  }`}>
                    {a.is_global_admin ? 'Super Admin' : 'Admin'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    a.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
                  }`}>
                    {a.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {!a.is_global_admin && (
                    <button
                      onClick={() => handleToggle(a.id, a.is_active)}
                      className="text-xs text-slate-500 hover:text-red-600"
                    >
                      {a.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {admins.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  No internal admins found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
