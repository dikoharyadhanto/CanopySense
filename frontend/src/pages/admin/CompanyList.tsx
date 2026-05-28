import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listCompanies, createCompany, type Company } from '../../lib/adminApi';

export default function CompanyList() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  function fetchCompanies(q: string) {
    setLoading(true);
    listCompanies({ search: q || undefined, limit: 50 })
      .then((r) => {
        setCompanies(r.items);
        setTotal(r.total);
        setError(null);
      })
      .catch(() => setError('Failed to load companies'))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchCompanies('');
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    fetchCompanies(search);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await createCompany({ company_name: newName });
      setNewName('');
      setShowCreate(false);
      fetchCompanies(search);
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail ?? 'Failed to create company');
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800">Companies ({total})</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 transition-colors"
        >
          + New Company
        </button>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name..."
          className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
        <button
          type="submit"
          className="px-3 py-2 bg-slate-100 text-slate-700 text-sm rounded-md hover:bg-slate-200 transition-colors"
        >
          Search
        </button>
      </form>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-96">
            <h2 className="text-base font-semibold text-slate-800 mb-4">Create Company</h2>
            <form onSubmit={handleCreate}>
              <label className="block text-sm text-slate-600 mb-1">Company Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              {createError && <p className="text-red-500 text-xs mb-3">{createError}</p>}
              <div className="flex gap-2 justify-end">
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

      {/* Table */}
      {error && <div className="text-red-600 text-sm mb-4">{error}</div>}
      {loading ? (
        <div className="text-slate-400 text-sm">Loading...</div>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Company Name</th>
                <th className="px-4 py-3">UUID</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr key={c.id} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-500">{c.id}</td>
                  <td className="px-4 py-3 font-medium text-slate-800">{c.company_name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">{c.company_id}</td>
                  <td className="px-4 py-3 text-slate-400">{new Date(c.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => navigate(`/admin/companies/${c.id}`)}
                      className="text-indigo-600 hover:text-indigo-800 text-xs"
                    >
                      View →
                    </button>
                  </td>
                </tr>
              ))}
              {companies.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    No companies found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
