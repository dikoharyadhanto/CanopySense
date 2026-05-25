import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../lib/api';
import TimeSeriesChart, { type IndexRow } from '../components/TimeSeriesChart';
import type { Block } from '../components/MapView';

export default function TimeSeries() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialBlockId = searchParams.get('block_id') ? Number(searchParams.get('block_id')) : null;

  const [blocks, setBlocks] = useState<Block[]>([]);
  const [selectedBlockId, setSelectedBlockId] = useState<number | null>(initialBlockId);
  const [chartData, setChartData] = useState<IndexRow[]>([]);
  const [showEvi, setShowEvi] = useState(false);
  const [showNdre, setShowNdre] = useState(false);
  const [loadingChart, setLoadingChart] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem('token')) { navigate('/login'); return; }
    api.get('/api/blocks').then((r) => {
      setBlocks(r.data);
      if (!selectedBlockId && r.data.length > 0) setSelectedBlockId(r.data[0].block_id);
    }).catch(() => navigate('/login'));
  }, [navigate, selectedBlockId]);

  useEffect(() => {
    if (!selectedBlockId) return;
    setLoadingChart(true);
    api.get(`/api/blocks/${selectedBlockId}/indices`)
      .then((r) => setChartData(r.data))
      .catch(() => setChartData([]))
      .finally(() => setLoadingChart(false));
  }, [selectedBlockId]);

  const selectedBlock = blocks.find((b) => b.block_id === selectedBlockId);

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <header className="bg-white border-b px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-sm text-green-700 font-medium hover:underline"
          >
            ← Peta Estate
          </button>
          <h1 className="text-lg font-semibold text-gray-800">Time-Series Analyzer</h1>
        </div>
        <button
          onClick={() => { localStorage.removeItem('token'); navigate('/login'); }}
          className="text-sm text-red-600 hover:text-red-800"
        >
          Logout
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-64 bg-white border-r p-4 flex flex-col gap-4 overflow-y-auto">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Pilih Blok</label>
            <select
              value={selectedBlockId ?? ''}
              onChange={(e) => setSelectedBlockId(Number(e.target.value))}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              {blocks.map((b) => (
                <option key={b.block_id} value={b.block_id}>
                  {b.name} ({b.code})
                </option>
              ))}
            </select>
          </div>

          {selectedBlock && (
            <div className="text-xs text-gray-500 space-y-1">
              <div><span className="font-medium">Afdeling:</span> {selectedBlock.afdeling_name}</div>
              <div><span className="font-medium">Estate:</span> {selectedBlock.estate_name}</div>
              <div><span className="font-medium">NDVI terakhir:</span> {selectedBlock.latest_ndvi?.toFixed(4) ?? 'N/A'}</div>
              <div><span className="font-medium">Tanggal:</span> {selectedBlock.acquisition_date ?? '-'}</div>
            </div>
          )}

          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase mb-2">Tampilkan Indeks</div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm cursor-default">
                <input type="checkbox" checked disabled className="accent-green-600" />
                <span className="text-green-700 font-medium">NDVI</span>
                <span className="text-xs text-gray-400">(selalu aktif)</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={showEvi}
                  onChange={(e) => setShowEvi(e.target.checked)}
                  className="accent-blue-600"
                />
                <span>EVI</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={showNdre}
                  onChange={(e) => setShowNdre(e.target.checked)}
                  className="accent-amber-600"
                />
                <span>NDRE</span>
              </label>
            </div>
            <p className="text-xs text-gray-400 mt-3">
              Garis merah putus-putus = tutupan awan &gt; 30%
            </p>
          </div>
        </aside>

        <main className="flex-1 p-6 overflow-hidden flex flex-col gap-2">
          <div className="text-sm text-gray-500">
            {chartData.length > 0 ? `${chartData.length} akuisisi ditemukan` : ''}
          </div>
          <div className="flex-1 bg-white rounded-lg shadow-sm border p-4">
            {loadingChart ? (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">Memuat data...</div>
            ) : (
              <TimeSeriesChart data={chartData} showEvi={showEvi} showNdre={showNdre} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
