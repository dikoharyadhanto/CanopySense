import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import MapView, { type Block } from '../components/MapView';
import IndexSelector, { type IndexKey } from '../components/IndexSelector';

function ndviColor(val: number | null): string {
  if (val === null) return 'text-gray-400';
  if (val >= 0.65) return 'text-green-600';
  if (val >= 0.45) return 'text-amber-600';
  return 'text-red-600';
}

function ndviBadgeBg(val: number | null): string {
  if (val === null) return 'bg-gray-100 text-gray-400 border-gray-200';
  if (val >= 0.65) return 'bg-green-50 text-green-700 border-green-200';
  if (val >= 0.45) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-red-50 text-red-700 border-red-200';
}

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  delta?: string;
  deltaColor?: string;
}

function StatCard({ label, value, sub, delta, deltaColor = 'text-gray-500' }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-4 min-w-0">
      <div className="text-xs text-gray-500 font-medium truncate mb-1">{label}</div>
      <div className="text-2xl font-bold text-gray-800 leading-tight">{value}</div>
      {(delta || sub) && (
        <div className="flex items-center gap-1.5 mt-2">
          {delta && (
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border border-gray-200 bg-white ${deltaColor}`}>
              {delta}
            </span>
          )}
          {sub && (
            <span className="text-[11px] text-gray-400">{sub}</span>
          )}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<IndexKey>('ndvi');
  const [selectedBlock, setSelectedBlock] = useState<Block | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/api/blocks')
      .then((r) => setBlocks(r.data))
      .catch(() => setError('Gagal memuat data blok. Periksa koneksi ke backend.'))
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    if (blocks.length === 0) return null;
    const withData = blocks.filter((b) => b.acquisition_date !== null);
    const ndviValues = blocks
      .map((b) => b.latest_ndvi)
      .filter((v): v is number => v !== null);
    const avgNdvi = ndviValues.length > 0
      ? (ndviValues.reduce((a, b) => a + b, 0) / ndviValues.length).toFixed(3)
      : 'N/A';
    const latestDate = withData.length > 0
      ? withData.sort((a, b) =>
          (b.acquisition_date ?? '').localeCompare(a.acquisition_date ?? ''),
        )[0].acquisition_date
      : null;
    const coveragePct = blocks.length > 0
      ? Math.round((withData.length / blocks.length) * 100)
      : 0;
    const avgNdviNum = ndviValues.length > 0
      ? ndviValues.reduce((a, b) => a + b, 0) / ndviValues.length
      : null;
    return { avgNdvi, avgNdviNum, latestDate, coveragePct, blockCount: blocks.length, withData: withData.length };
  }, [blocks]);

  const topBlocks = useMemo(() => {
    return [...blocks]
      .filter((b) => b.latest_ndvi !== null)
      .sort((a, b) => (b.latest_ndvi ?? 0) - (a.latest_ndvi ?? 0))
      .slice(0, 8);
  }, [blocks]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Page header */}
      <div className="bg-white border-b border-gray-100 px-6 py-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-bold text-gray-800">Dashboard Executive</h1>
            <p className="text-xs text-gray-500">
              Monitoring real-time kesehatan kanopi perkebunan karet
            </p>
          </div>
          <div className="flex items-center gap-3">
            {stats?.latestDate && (
              <span className="text-xs text-gray-400 hidden sm:block">
                Data: {stats.latestDate}
              </span>
            )}
            <IndexSelector value={selectedIndex} onChange={setSelectedIndex} />
          </div>
        </div>
      </div>

      {/* Summary stats */}
      {stats && (
        <div className="px-6 py-3 grid grid-cols-2 md:grid-cols-4 gap-3 flex-shrink-0">
          <StatCard
            label="Avg NDVI Estate"
            value={stats.avgNdvi}
            delta={stats.avgNdviNum !== null ? (stats.avgNdviNum >= 0.65 ? '↑ Baik' : stats.avgNdviNum >= 0.45 ? '→ Sedang' : '↓ Rendah') : undefined}
            deltaColor={ndviColor(stats.avgNdviNum)}
            sub={`dari ${stats.withData} blok`}
          />
          <StatCard
            label="Index Coverage"
            value={`${stats.coveragePct}%`}
            delta={stats.coveragePct === 100 ? '✓ Lengkap' : `${stats.withData}/${stats.blockCount}`}
            deltaColor={stats.coveragePct === 100 ? 'text-green-600' : 'text-amber-600'}
            sub="blok berdata"
          />
          <StatCard
            label="Akuisisi Terakhir"
            value={stats.latestDate ?? '—'}
            sub="tanggal data terbaru"
          />
          <StatCard
            label="Total Blok"
            value={String(stats.blockCount)}
            sub="blok di estate ini"
          />
        </div>
      )}

      {/* Map + side panels */}
      <div className="flex flex-1 overflow-hidden">
        {/* Block detail panel */}
        {selectedBlock && (
          <aside className="w-60 bg-white border-r border-gray-100 p-4 flex flex-col gap-3
                            overflow-y-auto flex-shrink-0">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-gray-800 text-sm">Detail Blok</h2>
              <button
                onClick={() => setSelectedBlock(null)}
                className="text-gray-400 hover:text-gray-600 text-lg leading-none"
                aria-label="Tutup detail blok"
              >
                &times;
              </button>
            </div>
            <div className="space-y-1.5 text-sm">
              <div><span className="font-medium text-gray-600">Nama:</span> {selectedBlock.name}</div>
              <div><span className="font-medium text-gray-600">Kode:</span> {selectedBlock.code}</div>
              <div><span className="font-medium text-gray-600">Afdeling:</span> {selectedBlock.afdeling_name}</div>
              <div><span className="font-medium text-gray-600">Estate:</span> {selectedBlock.estate_name}</div>
            </div>
            <hr className="border-gray-100" />
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                Indeks Terbaru
              </div>
              {(['ndvi', 'evi', 'ndre', 'savi', 'gndvi'] as const).map((k) => {
                const val = selectedBlock[`latest_${k}` as keyof Block] as number | null;
                return (
                  <div key={k} className="flex justify-between items-center">
                    <span className="uppercase text-xs text-gray-500 font-medium">{k}</span>
                    <span className={`text-xs font-bold ${ndviColor(k === 'ndvi' ? val : null)}`}>
                      {val !== null && val !== undefined ? val.toFixed(4) : 'N/A'}
                    </span>
                  </div>
                );
              })}
              <div className="text-xs text-gray-400 pt-1">
                <div>Tanggal: {selectedBlock.acquisition_date ?? '-'}</div>
                <div>Cloud: {selectedBlock.cloud_cover !== null ? selectedBlock.cloud_cover + '%' : '-'}</div>
              </div>
            </div>
            <button
              onClick={() => navigate(`/timeseries?block_id=${selectedBlock.block_id}`)}
              className="w-full bg-[#19C853] text-white text-sm py-2 rounded-lg
                         hover:bg-green-500 transition-colors font-semibold"
            >
              Lihat Time-Series →
            </button>
          </aside>
        )}

        {/* Map */}
        <main className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
              <div className="text-sm text-gray-500">Memuat data blok...</div>
            </div>
          )}
          {error && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10
                            bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2.5 rounded-lg">
              {error}
            </div>
          )}
          <MapView
            blocks={blocks}
            selectedIndex={selectedIndex}
            onBlockClick={setSelectedBlock}
          />
        </main>

        {/* Top blocks panel */}
        {topBlocks.length > 0 && !selectedBlock && (
          <aside className="w-56 bg-white border-l border-gray-100 flex flex-col overflow-hidden flex-shrink-0">
            <div className="px-4 py-3 border-b border-gray-100">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Top Blok — {selectedIndex.toUpperCase()}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto divide-y divide-gray-50">
              {topBlocks.map((b) => (
                <button
                  key={b.block_id}
                  onClick={() => setSelectedBlock(b)}
                  className="w-full text-left px-4 py-2.5 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-gray-800 truncate">{b.name}</div>
                      <div className="text-[11px] text-gray-400 truncate">{b.afdeling_name}</div>
                    </div>
                    <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border flex-shrink-0 ${ndviBadgeBg(b.latest_ndvi)}`}>
                      {b.latest_ndvi !== null ? b.latest_ndvi.toFixed(3) : 'N/A'}
                    </span>
                  </div>
                </button>
              ))}
            </div>
            <div className="px-4 py-3 border-t border-gray-100">
              <button
                onClick={() => navigate('/timeseries')}
                className="text-xs text-green-700 font-semibold hover:underline"
              >
                Lihat Semua Blok →
              </button>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
