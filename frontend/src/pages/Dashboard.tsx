import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import MapView, { type Block } from '../components/MapView';
import IndexSelector, { type IndexKey } from '../components/IndexSelector';

export default function Dashboard() {
  const navigate = useNavigate();
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<IndexKey>('ndvi');
  const [selectedBlock, setSelectedBlock] = useState<Block | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!localStorage.getItem('token')) { navigate('/login'); return; }
    api.get('/api/blocks')
      .then((r) => setBlocks(r.data))
      .catch(() => setError('Gagal memuat data blok. Periksa koneksi ke backend.'))
      .finally(() => setLoading(false));
  }, [navigate]);

  function handleBlockClick(block: Block) {
    setSelectedBlock(block);
  }

  function goToTimeSeries(blockId: number) {
    navigate(`/timeseries?block_id=${blockId}`);
  }

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <header className="bg-white border-b px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold text-gray-800">CanopySense — Peta Estate</h1>
          <IndexSelector value={selectedIndex} onChange={setSelectedIndex} />
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/timeseries')}
            className="text-sm text-green-700 font-medium hover:underline"
          >
            Time-Series Analyzer →
          </button>
          <button
            onClick={() => { localStorage.removeItem('token'); navigate('/login'); }}
            className="text-sm text-red-600 hover:text-red-800"
          >
            Logout
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {selectedBlock && (
          <aside className="w-64 bg-white border-r p-4 flex flex-col gap-3 overflow-y-auto">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-800 text-sm">Detail Blok</h2>
              <button onClick={() => setSelectedBlock(null)} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
            </div>
            <div className="space-y-1 text-sm">
              <div><span className="font-medium">Nama:</span> {selectedBlock.name}</div>
              <div><span className="font-medium">Kode:</span> {selectedBlock.code}</div>
              <div><span className="font-medium">Afdeling:</span> {selectedBlock.afdeling_name}</div>
              <div><span className="font-medium">Estate:</span> {selectedBlock.estate_name}</div>
            </div>
            <hr />
            <div className="space-y-1 text-sm">
              <div className="text-xs font-semibold text-gray-500 uppercase">Indeks Terbaru</div>
              {(['ndvi','evi','ndre','savi','gndvi'] as const).map((k) => {
                const val = selectedBlock[`latest_${k}` as keyof Block] as number | null;
                return (
                  <div key={k} className="flex justify-between">
                    <span className="uppercase text-xs text-gray-500">{k}</span>
                    <span className="font-medium text-xs">{val !== null && val !== undefined ? val.toFixed(4) : 'N/A'}</span>
                  </div>
                );
              })}
              <div className="text-xs text-gray-400 mt-1">
                Tanggal: {selectedBlock.acquisition_date ?? '-'}<br/>
                Cloud: {selectedBlock.cloud_cover !== null ? selectedBlock.cloud_cover + '%' : '-'}
              </div>
            </div>
            <button
              onClick={() => goToTimeSeries(selectedBlock.block_id)}
              className="w-full bg-green-600 text-white text-sm py-2 rounded hover:bg-green-700"
            >
              Lihat Time-Series
            </button>
          </aside>
        )}

        <main className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white z-10 text-gray-500 text-sm">
              Memuat data blok...
            </div>
          )}
          {error && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2 rounded z-10">
              {error}
            </div>
          )}
          <MapView
            blocks={blocks}
            selectedIndex={selectedIndex}
            onBlockClick={handleBlockClick}
          />
        </main>
      </div>
    </div>
  );
}
