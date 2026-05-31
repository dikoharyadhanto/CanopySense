import { useEffect, useState } from 'react';
import api from '../../lib/api';

interface SettingsResponse {
  settings: Record<string, string>;
}

export default function SystemSettings() {
  const [data, setData] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<SettingsResponse>('/api/admin/system-settings')
      .then((r) => setData(r.data.settings))
      .catch(() => setError('Gagal memuat pengaturan sistem.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-slate-800 mb-6">Pengaturan Sistem</h1>

      {loading ? (
        <p className="text-sm text-slate-400">Memuat...</p>
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-4 py-3 font-medium w-1/2">Konfigurasi</th>
                <th className="px-4 py-3 font-medium">Nilai</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data).map(([key, value]) => (
                <tr key={key} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{key}</td>
                  <td className="px-4 py-3 text-slate-800 break-all">{value || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-4 py-3 text-xs text-slate-400">
            Hanya menampilkan nilai non-sensitif. Secret dan password tidak ditampilkan.
          </p>
        </div>
      )}
    </div>
  );
}
