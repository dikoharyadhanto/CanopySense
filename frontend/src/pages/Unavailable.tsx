import { useNavigate } from 'react-router-dom';

export default function Unavailable() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="bg-white border-b border-gray-100 px-6 py-3 flex-shrink-0">
        <h1 className="text-base font-bold text-gray-800">Fitur Fase 2</h1>
        <p className="text-xs text-gray-500">Belum tersedia di Phase 1</p>
      </div>
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="max-w-sm text-center">
          <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-5">
            <svg className="w-7 h-7 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </div>
          <h2 className="text-lg font-bold text-gray-700 mb-2">Fitur Belum Tersedia</h2>
          <p className="text-sm text-gray-500 leading-relaxed mb-8">
            Fitur ini direncanakan untuk Phase 2 dan akan diaktifkan pada tahap
            pengembangan berikutnya.
          </p>
          <button
            onClick={() => navigate('/dashboard')}
            className="text-sm text-green-700 font-semibold hover:underline"
          >
            ← Kembali ke Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
