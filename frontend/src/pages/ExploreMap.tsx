export default function ExploreMap() {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Page header */}
      <div className="bg-white border-b border-gray-100 px-6 py-3 flex-shrink-0">
        <h1 className="text-base font-bold text-gray-800">Explore Map</h1>
        <p className="text-xs text-gray-500">
          Peta multi-layer berbasis Earth Engine — raster engine dalam pengembangan
        </p>
      </div>

      {/* Pending state content */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 flex items-center
                          justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15M14.25 3.104c.251.023.501.05.75.082M19.8 15l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.607L5 14.5m14.8.5l-1.57.393M5 14.5l-1.57.393" />
            </svg>
          </div>

          <h2 className="text-xl font-bold text-gray-800 mb-2">
            Raster Engine dalam Pengembangan
          </h2>
          <p className="text-sm text-gray-500 leading-relaxed mb-6">
            Explore Map akan menjadi tampilan peta piksel-level dari output Earth Engine —
            berbeda dari Dashboard yang menampilkan ringkasan nilai per blok.
          </p>

          <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 text-left space-y-3 mb-6">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Yang direncanakan
            </div>
            {[
              'Peta raster GCC / indeks vegetasi per piksel dari Earth Engine',
              'Overlay batas blok estate opsional',
              'Selector layer: NDVI, EVI, GCC, dan indeks lainnya',
              'Filter tanggal dan sensor',
            ].map((item) => (
              <div key={item} className="flex items-start gap-2 text-sm text-gray-600">
                <span className="text-amber-400 mt-0.5 flex-shrink-0">○</span>
                <span>{item}</span>
              </div>
            ))}
          </div>

          <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-xs text-blue-700 text-left">
            <span className="font-semibold">Catatan teknis:</span> Implementasi membutuhkan
            raster core script Earth Engine dan data contract yang akan direncanakan dalam
            Technical Plan Doc terpisah. Explore Map final akan dibangun setelah raster engine
            tersedia dan memiliki bukti data nyata.
          </div>
        </div>
      </div>
    </div>
  );
}
