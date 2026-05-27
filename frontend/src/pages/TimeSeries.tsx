import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../lib/api';
import TimeSeriesChart, { type IndexRow } from '../components/TimeSeriesChart';
import type { Block } from '../components/MapView';

const INDEX_TOGGLES = [
  { key: 'showEvi',   label: 'EVI',   color: 'accent-blue-600',   dot: 'bg-blue-500' },
  { key: 'showNdre',  label: 'NDRE',  color: 'accent-amber-600',  dot: 'bg-amber-500' },
  { key: 'showSavi',  label: 'SAVI',  color: 'accent-purple-600', dot: 'bg-purple-500' },
  { key: 'showGndvi', label: 'GNDVI', color: 'accent-teal-600',   dot: 'bg-teal-500' },
] as const;

type ToggleKey = typeof INDEX_TOGGLES[number]['key'];

export default function TimeSeries() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialBlockId = searchParams.get('block_id') ? Number(searchParams.get('block_id')) : null;

  const [blocks, setBlocks] = useState<Block[]>([]);
  const [selectedBlockId, setSelectedBlockId] = useState<number | null>(initialBlockId);
  const [chartData, setChartData] = useState<IndexRow[]>([]);
  const [toggles, setToggles] = useState<Record<ToggleKey, boolean>>({
    showEvi: false, showNdre: false, showSavi: false, showGndvi: false,
  });
  const [loadingBlocks, setLoadingBlocks] = useState(true);
  const [loadingChart, setLoadingChart] = useState(false);
  const [blockError, setBlockError] = useState('');

  useEffect(() => {
    api.get('/api/blocks')
      .then((r) => {
        setBlocks(r.data);
        if (!selectedBlockId && r.data.length > 0) setSelectedBlockId(r.data[0].block_id);
      })
      .catch(() => setBlockError('Gagal memuat daftar blok.'))
      .finally(() => setLoadingBlocks(false));
  }, []);

  useEffect(() => {
    if (!selectedBlockId) return;
    setLoadingChart(true);
    api.get(`/api/blocks/${selectedBlockId}/indices`)
      .then((r) => setChartData(r.data))
      .catch(() => setChartData([]))
      .finally(() => setLoadingChart(false));
  }, [selectedBlockId]);

  const selectedBlock = blocks.find((b) => b.block_id === selectedBlockId);

  function toggle(key: ToggleKey) {
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Page header */}
      <div className="bg-white border-b border-gray-100 px-6 py-3 flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-xs text-green-700 font-semibold hover:underline flex items-center gap-1"
          >
            ← Dashboard
          </button>
          <span className="text-gray-300">|</span>
          <div>
            <h1 className="text-base font-bold text-gray-800 leading-tight">Time-Series Analyzer</h1>
            <p className="text-xs text-gray-500">Tren indeks vegetasi per blok dari data satelit historis</p>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left controls panel */}
        <aside className="w-56 bg-white border-r border-gray-100 flex flex-col overflow-hidden flex-shrink-0">
          {/* Block selector */}
          <div className="p-4 border-b border-gray-100">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Pilih Blok
            </label>
            {loadingBlocks ? (
              <div className="text-xs text-gray-400">Memuat blok...</div>
            ) : blockError ? (
              <div className="text-xs text-red-500">{blockError}</div>
            ) : (
              <select
                value={selectedBlockId ?? ''}
                onChange={(e) => setSelectedBlockId(Number(e.target.value))}
                className="w-full text-sm border border-gray-200 rounded-lg px-2.5 py-2
                           focus:outline-none focus:ring-2 focus:ring-green-500 bg-gray-50"
              >
                {blocks.map((b) => (
                  <option key={b.block_id} value={b.block_id}>
                    {b.name} — {b.code}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Selected block metadata */}
          {selectedBlock && (
            <div className="p-4 border-b border-gray-100 space-y-2">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                Info Blok
              </div>
              {[
                ['Afdeling', selectedBlock.afdeling_name],
                ['Estate',   selectedBlock.estate_name],
                ['NDVI',     selectedBlock.latest_ndvi?.toFixed(4) ?? 'N/A'],
                ['Tanggal',  selectedBlock.acquisition_date ?? '-'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-gray-500">{k}</span>
                  <span className="font-semibold text-gray-800 text-right">{v}</span>
                </div>
              ))}
            </div>
          )}

          {/* Index toggles */}
          <div className="p-4 flex-1">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Tampilkan Indeks
            </div>
            <div className="space-y-2.5">
              {/* NDVI always on */}
              <div className="flex items-center gap-2.5">
                <div className="w-3 h-3 rounded-full bg-green-500 flex-shrink-0" />
                <span className="text-sm font-semibold text-green-700">NDVI</span>
                <span className="text-xs text-gray-400 ml-auto">selalu aktif</span>
              </div>
              {INDEX_TOGGLES.map(({ key, label, color, dot }) => (
                <label key={key} className="flex items-center gap-2.5 cursor-pointer group">
                  <div className={`w-3 h-3 rounded-full flex-shrink-0 ${toggles[key] ? dot : 'bg-gray-200'}`} />
                  <input
                    type="checkbox"
                    checked={toggles[key]}
                    onChange={() => toggle(key)}
                    className={`sr-only ${color}`}
                  />
                  <span className={`text-sm ${toggles[key] ? 'text-gray-800 font-medium' : 'text-gray-400'}`}>
                    {label}
                  </span>
                  <div className={`ml-auto w-8 h-4 rounded-full transition-colors flex-shrink-0
                                  ${toggles[key] ? 'bg-green-500' : 'bg-gray-200'}`}>
                    <div className={`w-3 h-3 rounded-full bg-white mt-0.5 transition-transform shadow-sm
                                    ${toggles[key] ? 'translate-x-4' : 'translate-x-0.5'}`} />
                  </div>
                </label>
              ))}
            </div>

            {/* Cloud cover cue */}
            <div className="mt-6 rounded-lg bg-amber-50 border border-amber-200 p-3">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 mb-1">
                <span>☁</span> Tutupan Awan
              </div>
              <p className="text-xs text-amber-600 leading-relaxed">
                Garis merah putus-putus = cloud cover &gt; 30%. Titik data tersebut
                mungkin kurang akurat.
              </p>
            </div>
          </div>
        </aside>

        {/* Chart area */}
        <main className="flex-1 p-5 overflow-hidden flex flex-col gap-3">
          {chartData.length > 0 && (
            <div className="text-xs text-gray-400">
              {chartData.length} titik akuisisi ditemukan
              {selectedBlock ? ` · Blok ${selectedBlock.name}` : ''}
            </div>
          )}
          <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-100 p-4 overflow-hidden">
            {loadingChart ? (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                Memuat data indeks...
              </div>
            ) : chartData.length === 0 && !loadingChart ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="text-3xl mb-3">📊</div>
                <div className="text-sm font-semibold text-gray-600 mb-1">
                  Tidak ada data untuk blok ini
                </div>
                <div className="text-xs text-gray-400">
                  Pilih blok lain atau periksa status akuisisi data.
                </div>
              </div>
            ) : (
              <TimeSeriesChart
                data={chartData}
                showEvi={toggles.showEvi}
                showNdre={toggles.showNdre}
                showSavi={toggles.showSavi}
                showGndvi={toggles.showGndvi}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
