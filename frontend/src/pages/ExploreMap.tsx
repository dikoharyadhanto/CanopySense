import { useState, useEffect, useCallback, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  fetchRasterMetadata,
  fetchRasterFrames,
  fetchUserContext,
  RasterApiError,
} from '../lib/rasterApi';
import type { RasterMetadata, RasterFrame, UserContext, FetchRasterParams } from '../lib/rasterApi';
import api from '../lib/api';
import { clearToken } from '../lib/auth';

const SUPPORTED_INDICES = ['ndvi', 'evi', 'savi', 'gndvi', 'ndre'] as const;
type SupportedIndex = (typeof SUPPORTED_INDICES)[number];

const BASEMAPS = {
  osm: {
    label: 'Peta',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    label: 'Satelit',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
  },
} as const;
type BasemapKey = keyof typeof BASEMAPS;

const BLOCK_OVERLAY_STYLE = { color: 'rgba(255,255,255,0.85)', weight: 1.5, fillOpacity: 0 };

function AutoFitBounds({ bounds }: { bounds: RasterMetadata['bounds'] }) {
  const map = useMap();
  const prevKey = useRef('');
  useEffect(() => {
    const key = `${bounds.south},${bounds.west},${bounds.north},${bounds.east}`;
    if (key === prevKey.current) return;
    prevKey.current = key;
    map.fitBounds([[bounds.south, bounds.west], [bounds.north, bounds.east]], { padding: [30, 30] });
  }, [bounds, map]);
  return null;
}

function errorLabel(status: number, message: string): { title: string; body: string } {
  switch (status) {
    case 402:
      return {
        title: 'Subscription Tidak Aktif',
        body: 'Akses raster engine membutuhkan subscription aktif. Hubungi administrator untuk informasi lebih lanjut.',
      };
    case 403:
      return {
        title: 'Akses Ditolak',
        body: message || 'Akses ke frame ini tidak diizinkan oleh subscription Anda.',
      };
    case 404:
      return {
        title: 'Tidak Ada Data Estate',
        body: 'Tidak ada blok estate yang terkonfigurasi untuk akun ini. Hubungi administrator.',
      };
    case 503:
      return {
        title: 'GEE Tidak Tersedia',
        body: message || 'Google Earth Engine tidak tersedia atau tidak ada citra untuk frame ini. Coba frame lain.',
      };
    default:
      return { title: `Gagal Memuat Raster (${status || 'Network'})`, body: message };
  }
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-gray-400 flex-shrink-0">{label}:</span>
      <span className="text-gray-700 font-medium break-all">{value}</span>
    </div>
  );
}

export default function ExploreMap() {
  const navigate = useNavigate();

  const [metadata, setMetadata] = useState<RasterMetadata | null>(null);
  const [userCtx, setUserCtx] = useState<UserContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [rasterError, setRasterError] = useState<{ status: number; message: string } | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<SupportedIndex>('ndvi');

  // Timelapse frame state (Premium only)
  const [frames, setFrames] = useState<RasterFrame[]>([]);
  const [frameIndex, setFrameIndex] = useState(0);
  const [framesLoading, setFramesLoading] = useState(false);
  const [framesError, setFramesError] = useState<string | null>(null);

  const [opacity, setOpacity] = useState(0.85);
  const [showBlockOverlay, setShowBlockOverlay] = useState(false);
  const [blockFeatures, setBlockFeatures] = useState<GeoJSON.FeatureCollection | null>(null);
  const [basemap, setBasemap] = useState<BasemapKey>('satellite');
  const [tileError, setTileError] = useState(false);
  const [legendOpen, setLegendOpen] = useState(true);

  const isPremium = userCtx?.subscription_tier === 'premium';

  // AbortController for in-flight raster fetch — cancels stale requests on rapid frame changes
  const abortRef = useRef<AbortController | null>(null);

  const doFetch = useCallback(async (index: string, frameId?: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setRasterError(null);
    setTileError(false);
    try {
      const params: FetchRasterParams = { index, signal: controller.signal };
      if (frameId) params.frame_id = frameId;
      const data = await fetchRasterMetadata(params);
      setMetadata(data);
    } catch (err) {
      if ((err as { code?: string }).code === 'ERR_CANCELED') return;
      if (err instanceof RasterApiError) {
        if (err.status === 401) {
          clearToken();
          navigate('/login');
          return;
        }
        setRasterError({ status: err.status, message: err.message });
        setMetadata(null);
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [navigate]);

  const loadFrames = useCallback(async (index: string) => {
    setFramesLoading(true);
    setFramesError(null);
    try {
      const data = await fetchRasterFrames(index);
      setFrames(data.frames);
      setFrameIndex(0);
      if (data.frames.length > 0) {
        doFetch(index, data.frames[0].frame_id);
      } else {
        // No satellite data for this company/index — honest empty state
        setLoading(false);
        setMetadata(null);
      }
    } catch (err) {
      if (err instanceof RasterApiError) {
        setFramesError(err.message);
      }
      setLoading(false);
    } finally {
      setFramesLoading(false);
    }
  }, [doFetch]);

  // Initial load: fetch user context; then load frames (Premium) or latest scene (Basic)
  useEffect(() => {
    fetchUserContext().then(ctx => {
      setUserCtx(ctx);
      if (ctx.subscription_tier === 'premium') {
        loadFrames('ndvi');
      } else {
        doFetch('ndvi');
      }
    }).catch(() => {
      doFetch('ndvi');
    });
  }, [doFetch, loadFrames]);

  // Load block geometries when overlay is first enabled (context-only, outline)
  useEffect(() => {
    if (!showBlockOverlay || blockFeatures) return;
    api.get('/api/blocks').then((res) => {
      const fc: GeoJSON.FeatureCollection = {
        type: 'FeatureCollection',
        features: (res.data as Array<{ geometry: GeoJSON.Geometry; name: string; code: string }>).map((b) => ({
          type: 'Feature' as const,
          geometry: b.geometry,
          properties: { name: b.name, code: b.code },
        })),
      };
      setBlockFeatures(fc);
    }).catch(() => {});
  }, [showBlockOverlay, blockFeatures]);

  const handleIndexChange = (idx: SupportedIndex) => {
    setSelectedIndex(idx);
    if (isPremium) {
      loadFrames(idx);
    } else {
      doFetch(idx);
    }
  };

  const handleFrameChange = (newIndex: number) => {
    setFrameIndex(newIndex);
    doFetch(selectedIndex, frames[newIndex].frame_id);
  };

  const handleRefresh = () => {
    if (isPremium && frames.length > 0) {
      doFetch(selectedIndex, frames[frameIndex].frame_id);
    } else if (isPremium) {
      loadFrames(selectedIndex);
    } else {
      doFetch(selectedIndex);
    }
  };

  const { t } = useTranslation();

  const subscriptionLabel = userCtx
    ? isPremium ? 'Premium — Timelapse' : 'Basic — Data Terbaru'
    : '';

  const currentFrame = frames[frameIndex] ?? null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 py-2 flex-shrink-0 flex items-center gap-3 flex-wrap">
        <h1 className="text-sm font-bold text-gray-800 flex-shrink-0">Explore Map</h1>

        {/* Index selector */}
        <div className="flex items-center gap-1">
          {SUPPORTED_INDICES.map((idx) => (
            <button
              key={idx}
              data-testid={`index-btn-${idx}`}
              onClick={() => handleIndexChange(idx)}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                selectedIndex === idx
                  ? 'bg-[#1B3A2D] text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {idx.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="flex-1" />

        {/* Subscription badge */}
        {subscriptionLabel && (
          <span
            data-testid="subscription-badge"
            className={`text-xs px-2.5 py-1 rounded-full font-medium ${
              isPremium
                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                : 'bg-gray-100 text-gray-500 border border-gray-200'
            }`}
          >
            {subscriptionLabel}
          </span>
        )}

        {/* Basemap toggle */}
        <div className="flex rounded-lg overflow-hidden border border-gray-200">
          {(Object.keys(BASEMAPS) as BasemapKey[]).map((key) => (
            <button
              key={key}
              onClick={() => setBasemap(key)}
              className={`px-2.5 py-1 text-xs font-semibold transition-colors ${
                basemap === key
                  ? 'bg-[#1B3A2D] text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              {BASEMAPS[key].label}
            </button>
          ))}
        </div>
      </div>

      {/* Timelapse controls — Premium only */}
      {isPremium && (
        <div
          data-testid="timelapse-controls"
          className="bg-gray-50 border-b border-gray-100 px-4 py-2 flex-shrink-0 flex items-center gap-3"
        >
          {framesLoading ? (
            <span className="text-xs text-gray-400">Memuat daftar citra...</span>
          ) : framesError ? (
            <span className="text-xs text-red-500">{framesError}</span>
          ) : frames.length === 0 ? (
            <span
              data-testid="no-frames-message"
              className="text-xs text-gray-500"
            >
              Tidak ada data satelit tersedia untuk estate ini. Data akan muncul setelah pipeline dijadwalkan berikutnya.
            </span>
          ) : (
            <>
              {/* Prev frame */}
              <button
                data-testid="prev-frame-btn"
                onClick={() => handleFrameChange(Math.min(frameIndex + 1, frames.length - 1))}
                disabled={frameIndex >= frames.length - 1}
                aria-label={t('exploreMap.prevFrameAriaLabel')}
                className="p-1 rounded text-gray-500 hover:text-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              {/* Timeline slider — each position is a valid acquisition date */}
              <div className="flex-1 flex flex-col gap-0.5">
                <input
                  data-testid="timelapse-slider"
                  type="range"
                  min={0}
                  max={Math.max(frames.length - 1, 0)}
                  value={frameIndex}
                  onChange={(e) => handleFrameChange(Number(e.target.value))}
                  className="w-full accent-[#1B3A2D]"
                  aria-label={t('exploreMap.selectFrameAriaLabel')}
                />
                <div className="flex justify-between text-[10px] text-gray-400 px-0.5">
                  <span>{frames[frames.length - 1]?.label ?? ''}</span>
                  <span>{frames[0]?.label ?? ''}</span>
                </div>
              </div>

              {/* Next frame */}
              <button
                data-testid="next-frame-btn"
                onClick={() => handleFrameChange(Math.max(frameIndex - 1, 0))}
                disabled={frameIndex <= 0}
                aria-label={t('exploreMap.nextFrameAriaLabel')}
                className="p-1 rounded text-gray-500 hover:text-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* Current frame label */}
              <span
                data-testid="frame-label"
                className="text-xs font-semibold text-gray-700 min-w-[88px] text-right"
              >
                {currentFrame?.label ?? '—'}
              </span>
            </>
          )}
        </div>
      )}

      {/* Map area */}
      <div className="flex-1 relative" style={{ minHeight: 0 }}>
        <MapContainer
          center={[-0.5, 117.0]}
          zoom={5}
          style={{ height: '100%', width: '100%' }}
        >
          {/* Basemap */}
          <TileLayer
            key={basemap}
            attribution={BASEMAPS[basemap].attribution}
            url={BASEMAPS[basemap].url}
          />

          {/* Raster tile layer from backend tile_url_format */}
          {metadata && (
            <>
              <AutoFitBounds bounds={metadata.bounds} />
              <TileLayer
                key={metadata.tile_url_format}
                url={metadata.tile_url_format}
                opacity={opacity}
                attribution="Google Earth Engine"
                maxZoom={18}
                eventHandlers={{
                  tileerror: () => setTileError(true),
                }}
              />
              {/* Test probe: identifies raster tile URL without passing data-testid to Leaflet */}
              <span
                style={{ display: 'none' }}
                data-testid="raster-tile-layer"
                data-url={metadata.tile_url_format}
              />
            </>
          )}

          {/* Block boundary overlay — context-only outline, no fill */}
          {showBlockOverlay && blockFeatures && (
            <GeoJSON
              key="block-overlay"
              data={blockFeatures}
              style={() => BLOCK_OVERLAY_STYLE}
            />
          )}
        </MapContainer>

        {/* Right-side controls */}
        <div
          style={{ position: 'absolute', top: 10, right: 10, zIndex: 1000 }}
          className="flex flex-col gap-2"
        >
          {/* Opacity slider */}
          <div className="bg-white rounded-lg shadow border border-gray-200 px-3 py-2">
            <div className="text-xs text-gray-500 font-medium mb-1">Opasitas Raster</div>
            <input
              data-testid="opacity-slider"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => setOpacity(parseFloat(e.target.value))}
              className="w-24"
            />
            <span className="text-[10px] text-gray-400 ml-1">{Math.round(opacity * 100)}%</span>
          </div>

          {/* Block overlay toggle */}
          <button
            data-testid="block-overlay-toggle"
            onClick={() => setShowBlockOverlay((v) => !v)}
            title="Batas Blok (kontekstual) — bukan data raster per blok"
            className={`flex items-center gap-1.5 shadow border rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors ${
              showBlockOverlay
                ? 'bg-[#1B3A2D] border-[#1B3A2D] text-white'
                : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
            </svg>
            Batas Blok (kontekstual)
          </button>

          {/* Refresh */}
          <button
            data-testid="refresh-btn"
            onClick={handleRefresh}
            className="flex items-center gap-1.5 bg-white shadow border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>

        {/* Metadata + legend panel — bottom left */}
        {metadata && !rasterError && (
          <div
            style={{ position: 'absolute', bottom: 28, left: 10, zIndex: 1000, maxWidth: 270 }}
            className="bg-white/92 backdrop-blur-sm rounded-xl shadow border border-gray-200 overflow-hidden"
            data-testid="metadata-panel"
          >
            <button
              onClick={() => setLegendOpen((v) => !v)}
              className="flex items-center gap-2 px-3 py-2 w-full text-left hover:bg-gray-50/80 transition-colors"
            >
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider flex-1">
                Per-piksel {metadata.index.toUpperCase()} · {metadata.sensor} · {metadata.date_acquired}
              </span>
              <svg
                className={`w-3 h-3 text-gray-400 transition-transform flex-shrink-0 ${legendOpen ? 'rotate-180' : ''}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {legendOpen && (
              <div className="px-3 pb-3 border-t border-gray-100 space-y-2" data-testid="legend-content">
                {/* Dynamic legend from metadata palette/viz_min/viz_max */}
                <div className="pt-2">
                  <div
                    className="h-3 rounded"
                    style={{
                      background: `linear-gradient(to right, ${metadata.palette.join(', ')})`,
                    }}
                    data-testid="legend-gradient"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                    <span>{metadata.viz_min.toFixed(2)}</span>
                    <span className="font-semibold text-gray-500">{metadata.index.toUpperCase()}</span>
                    <span>{metadata.viz_max.toFixed(2)}</span>
                  </div>
                </div>

                <div className="space-y-1 text-[11px]">
                  <MetaRow label={t('exploreMap.metaDate')} value={metadata.date_acquired} />
                  <MetaRow label={t('exploreMap.metaSensor')} value={metadata.sensor} />
                  <MetaRow label={t('exploreMap.metaResolution')} value={`${metadata.resolution_m}m/piksel`} />
                  <MetaRow
                    label={t('exploreMap.metaValidPixels')}
                    value={`${(metadata.valid_pixel_ratio * 100).toFixed(1)}%`}
                  />
                  <MetaRow
                    label={t('exploreMap.metaCreated')}
                    value={new Date(metadata.generated_at_utc).toLocaleString('id-ID', {
                      dateStyle: 'short',
                      timeStyle: 'short',
                    })}
                  />
                </div>

                {metadata.low_quality && (
                  <div className="rounded bg-amber-50 border border-amber-200 px-2 py-1 text-[10px] text-amber-700">
                    Kualitas rendah — citra Landsat dengan tutupan awan parsial.
                  </div>
                )}

                <p className="text-[10px] text-gray-400 leading-relaxed">
                  {metadata.cloud_nodata_note}
                </p>

                {/* Per-pixel raster explanation — not block average */}
                <p className="text-[10px] text-blue-500 leading-relaxed border-t border-gray-100 pt-1.5">
                  Nilai piksel mencerminkan reflektansi permukaan per piksel (cloud-masked). Bukan rata-rata nilai per blok.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Loading overlay */}
        {loading && (
          <div
            data-testid="loading-overlay"
            style={{ position: 'absolute', inset: 0, zIndex: 1001 }}
            className="bg-white/75 backdrop-blur-sm flex items-center justify-center"
          >
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-[#1B3A2D] border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-gray-600">Memuat data raster...</span>
            </div>
          </div>
        )}

        {/* Error overlay — honest states per HTTP status */}
        {!loading && rasterError && (
          <div
            data-testid="error-overlay"
            style={{ position: 'absolute', inset: 0, zIndex: 1001 }}
            className="bg-white/92 backdrop-blur-sm flex items-center justify-center"
          >
            <div className="max-w-sm text-center px-6">
              <div
                className={`w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 ${
                  rasterError.status === 503
                    ? 'bg-orange-50 border border-orange-200'
                    : 'bg-red-50 border border-red-200'
                }`}
              >
                <svg
                  className={`w-6 h-6 ${rasterError.status === 503 ? 'text-orange-500' : 'text-red-500'}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                </svg>
              </div>
              <h3 className="text-base font-bold text-gray-800 mb-2" data-testid="error-title">
                {errorLabel(rasterError.status, rasterError.message).title}
              </h3>
              <p className="text-sm text-gray-500 mb-4" data-testid="error-body">
                {errorLabel(rasterError.status, rasterError.message).body}
              </p>
              <button
                onClick={handleRefresh}
                className="px-4 py-2 bg-[#1B3A2D] text-white text-sm font-semibold rounded-lg hover:bg-[#264d3a] transition-colors"
              >
                Coba Lagi
              </button>
            </div>
          </div>
        )}

        {/* Tile expired guidance */}
        {tileError && !loading && !rasterError && (
          <div
            data-testid="tile-error-banner"
            style={{ position: 'absolute', bottom: 10, left: '50%', transform: 'translateX(-50%)', zIndex: 1000 }}
            className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2.5 text-xs text-amber-800 text-center shadow whitespace-nowrap"
          >
            <span className="font-semibold">Tile URL mungkin kedaluwarsa (~48 jam).</span>{' '}
            <button onClick={handleRefresh} className="underline font-semibold hover:text-amber-900">
              Klik Refresh
            </button>{' '}
            untuk memuat ulang.
          </div>
        )}
      </div>
    </div>
  );
}
