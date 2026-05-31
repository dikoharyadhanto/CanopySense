import { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import type { Layer, PathOptions } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { IndexKey } from './IndexSelector';

export interface Block {
  block_id: number;
  name: string;
  code: string;
  afdeling_name: string;
  estate_name: string;
  geometry: GeoJSON.Geometry;
  latest_ndvi: number | null;
  latest_evi: number | null;
  latest_ndre: number | null;
  latest_savi: number | null;
  latest_gndvi: number | null;
  acquisition_date: string | null;
  cloud_cover: number | null;
}

interface Props {
  blocks: Block[];
  selectedIndex: IndexKey;
  onBlockClick: (block: Block) => void;
}

// RdYlGn 7-step color ramp — perceptually distinct classes
const COLOR_STOPS: { max: number; color: string }[] = [
  { max: 0.20, color: '#d73027' },
  { max: 0.35, color: '#fc8d59' },
  { max: 0.45, color: '#fee08b' },
  { max: 0.55, color: '#d9ef8b' },
  { max: 0.65, color: '#91cf60' },
  { max: 0.75, color: '#1a9850' },
  { max: Infinity, color: '#006837' },
];

const LEGEND_STEPS = [
  { range: '> 0.75',      color: '#006837', label: 'Optimal' },
  { range: '0.65 – 0.75', color: '#1a9850', label: 'Sangat Baik' },
  { range: '0.55 – 0.65', color: '#91cf60', label: 'Baik' },
  { range: '0.45 – 0.55', color: '#d9ef8b', label: 'Cukup' },
  { range: '0.35 – 0.45', color: '#fee08b', label: 'Sedang' },
  { range: '0.20 – 0.35', color: '#fc8d59', label: 'Rendah' },
  { range: '< 0.20',      color: '#d73027', label: 'Sangat Rendah' },
];

// Zoom level at which block name labels appear
const LABEL_ZOOM_THRESHOLD = 14;

const BASEMAPS = {
  osm: {
    label: 'Peta',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    label: 'Satelit',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles © Esri — Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP',
  },
} as const;

type BasemapKey = keyof typeof BASEMAPS;

function getIndexValue(block: Block, idx: IndexKey): number | null {
  const map: Record<IndexKey, number | null> = {
    ndvi: block.latest_ndvi,
    evi: block.latest_evi,
    ndre: block.latest_ndre,
    savi: block.latest_savi,
    gndvi: block.latest_gndvi,
  };
  return map[idx];
}

function indexToColor(value: number | null): string {
  if (value === null || value === undefined) return '#9ca3af';
  for (const stop of COLOR_STOPS) {
    if (value < stop.max) return stop.color;
  }
  return COLOR_STOPS[COLOR_STOPS.length - 1].color;
}

function computeBlockBounds(blocks: Block[]): L.LatLngBounds | null {
  const lats: number[] = [];
  const lngs: number[] = [];
  blocks.forEach((b) => {
    const coords = (b.geometry as GeoJSON.Polygon).coordinates[0];
    coords.forEach(([lng, lat]) => { lngs.push(lng); lats.push(lat); });
  });
  if (!lats.length) return null;
  return L.latLngBounds(
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)],
  );
}

function polygonCentroid(geometry: GeoJSON.Geometry): [number, number] | null {
  if (geometry.type !== 'Polygon') return null;
  const coords = (geometry as GeoJSON.Polygon).coordinates[0];
  const lat = coords.reduce((s, [, y]) => s + y, 0) / coords.length;
  const lng = coords.reduce((s, [x]) => s + x, 0) / coords.length;
  return [lat, lng];
}

// Fits view on first load
function AutoFit({ blocks }: { blocks: Block[] }) {
  const map = useMap();
  const fitted = useRef(false);
  useEffect(() => {
    if (blocks.length === 0 || fitted.current) return;
    const bounds = computeBlockBounds(blocks);
    if (bounds) {
      map.fitBounds(bounds, { padding: [30, 30] });
      fitted.current = true;
    }
  }, [blocks, map]);
  return null;
}

// Fires fitBounds when trigger increments (zoom-to-estate button)
function ZoomToEstateControl({ blocks, trigger }: { blocks: Block[]; trigger: number }) {
  const map = useMap();
  useEffect(() => {
    if (trigger === 0 || blocks.length === 0) return;
    const bounds = computeBlockBounds(blocks);
    if (bounds) map.fitBounds(bounds, { padding: [30, 30] });
  }, [trigger, blocks, map]);
  return null;
}

// Block name labels — zoom-dependent + user-controlled toggle
function BlockLabels({ blocks, enabled }: { blocks: Block[]; enabled: boolean }) {
  const map = useMap();
  const groupRef = useRef<L.LayerGroup | null>(null);

  // Build label layer once when blocks load
  useEffect(() => {
    if (blocks.length === 0) return;
    groupRef.current?.remove();

    const group = L.layerGroup();
    blocks.forEach((block) => {
      const center = polygonCentroid(block.geometry);
      if (!center) return;
      L.marker(center, {
        interactive: false,
        icon: L.divIcon({
          className: '',
          iconSize: [0, 0],
          iconAnchor: [0, 0],
          html: `<div style="
            transform: translate(-50%, -50%);
            pointer-events: none;
            white-space: nowrap;
            font-size: 13px;
            font-weight: 800;
            color: #1B3A2D;
            text-shadow:
              0 0 3px rgba(255,255,255,0.9),
              0 0 6px rgba(255,255,255,0.7),
              1px 1px 0 rgba(255,255,255,0.8),
              -1px -1px 0 rgba(255,255,255,0.8),
              1px -1px 0 rgba(255,255,255,0.8),
              -1px 1px 0 rgba(255,255,255,0.8);
            letter-spacing: 0.04em;
            line-height: 1;
          ">${block.name}</div>`,
        }),
      }).addTo(group);
    });

    groupRef.current = group;
    if (enabled && map.getZoom() >= LABEL_ZOOM_THRESHOLD) group.addTo(map);

    return () => { group.remove(); groupRef.current = null; };
  }, [blocks, map]); // eslint-disable-line react-hooks/exhaustive-deps

  // React to user toggle
  useEffect(() => {
    const group = groupRef.current;
    if (!group) return;
    if (enabled && map.getZoom() >= LABEL_ZOOM_THRESHOLD) {
      group.addTo(map);
    } else {
      group.remove();
    }
  }, [enabled, map]);

  // React to zoom changes
  useMapEvents({
    zoomend: () => {
      const group = groupRef.current;
      if (!group) return;
      if (enabled && map.getZoom() >= LABEL_ZOOM_THRESHOLD) {
        group.addTo(map);
      } else {
        group.remove();
      }
    },
  });

  return null;
}

export default function MapView({ blocks, selectedIndex, onBlockClick }: Props) {
  const [basemap, setBasemap] = useState<BasemapKey>('osm');
  const [legendOpen, setLegendOpen] = useState(true);
  const [labelsVisible, setLabelsVisible] = useState(true);
  const [resetViewTrigger, setResetViewTrigger] = useState(0);

  // Include basemap in key so GeoJSON remounts when border style changes
  const geoJsonKey = `${selectedIndex}-${blocks.length}-${basemap}`;
  const fillOpacity = basemap === 'satellite' ? 0.62 : 0.72;

  const features: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: blocks.map((b) => ({
      type: 'Feature',
      geometry: b.geometry,
      properties: { ...b },
    })),
  };

  function styleFeature(feature?: GeoJSON.Feature): PathOptions {
    const value = feature ? getIndexValue(feature.properties as Block, selectedIndex) : null;
    return {
      fillColor: indexToColor(value),
      fillOpacity,
      color: basemap === 'satellite' ? 'rgba(255,255,255,0.7)' : '#374151',
      weight: basemap === 'satellite' ? 1.5 : 1,
    };
  }

  function onEachFeature(feature: GeoJSON.Feature, layer: Layer) {
    const block = feature.properties as Block;
    const value = getIndexValue(block, selectedIndex);
    const displayVal = value !== null ? value.toFixed(4) : 'N/A';
    layer.bindPopup(`
      <div style="min-width:190px">
        <div style="font-weight:700;font-size:14px;margin-bottom:4px">${block.name}</div>
        <div style="color:#6b7280;font-size:12px">Afdeling: ${block.afdeling_name}</div>
        <div style="color:#6b7280;font-size:12px">Kode: ${block.code}</div>
        <hr style="margin:6px 0;border-color:#f3f4f6"/>
        <div style="font-size:13px"><strong>${selectedIndex.toUpperCase()}:</strong> ${displayVal}</div>
        <div style="font-size:12px;color:#6b7280">Tanggal: ${block.acquisition_date ?? '-'}</div>
        <div style="font-size:12px;color:#6b7280">Cloud cover: ${block.cloud_cover !== null ? block.cloud_cover + '%' : '-'}</div>
        <hr style="margin:6px 0;border-color:#f3f4f6"/>
        <a href="/timeseries?block_id=${block.block_id}" style="color:#19C853;font-size:12px;font-weight:600">
          Lihat Time-Series →
        </a>
      </div>
    `);
    layer.on('click', () => onBlockClick(block));
  }

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <MapContainer
        center={[-0.5, 107.022]}
        zoom={14}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          key={basemap}
          attribution={BASEMAPS[basemap].attribution}
          url={BASEMAPS[basemap].url}
        />
        {blocks.length > 0 && (
          <>
            <AutoFit blocks={blocks} />
            <ZoomToEstateControl blocks={blocks} trigger={resetViewTrigger} />
            <BlockLabels blocks={blocks} enabled={labelsVisible} />
            <GeoJSON
              key={geoJsonKey}
              data={features}
              style={styleFeature}
              onEachFeature={onEachFeature}
            />
          </>
        )}
      </MapContainer>

      {/* Top-right controls: zoom-to-estate + basemap toggle */}
      <div
        style={{ position: 'absolute', top: 10, right: 10, zIndex: 1000 }}
        className="flex items-center gap-2"
      >
        <button
          onClick={() => setResetViewTrigger((v) => v + 1)}
          title="Zoom ke seluruh area estate"
          className="flex items-center gap-1.5 bg-white shadow border border-gray-200
                     rounded-lg px-2.5 py-1.5 text-xs font-semibold text-gray-600
                     hover:bg-gray-50 transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <circle cx="11" cy="11" r="8" />
            <path strokeLinecap="round" d="M11 8v6M8 11h6" />
            <path strokeLinecap="round" d="M21 21l-4.35-4.35" />
          </svg>
          Estate
        </button>

        <button
          onClick={() => setLabelsVisible((v) => !v)}
          title={labelsVisible ? 'Sembunyikan label blok' : 'Tampilkan label blok'}
          className={`flex items-center gap-1.5 shadow border rounded-lg px-2.5 py-1.5
                      text-xs font-semibold transition-colors ${
                        labelsVisible
                          ? 'bg-[#1B3A2D] border-[#1B3A2D] text-white'
                          : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'
                      }`}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
          </svg>
          Label
        </button>

        <div className="flex rounded-lg overflow-hidden shadow border border-gray-200">
          {(Object.keys(BASEMAPS) as BasemapKey[]).map((key) => (
            <button
              key={key}
              onClick={() => setBasemap(key)}
              className={`px-3 py-1.5 text-xs font-semibold transition-colors ${
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

      {/* Legend — bottom-left, collapsible */}
      <div
        style={{ position: 'absolute', bottom: 28, left: 10, zIndex: 1000 }}
        className="bg-white/90 backdrop-blur-sm rounded-xl shadow border border-gray-200 overflow-hidden"
      >
        <button
          onClick={() => setLegendOpen((v) => !v)}
          className="flex items-center gap-2 px-3 py-2 w-full text-left
                     hover:bg-gray-50/80 transition-colors"
        >
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex-1">
            {selectedIndex.toUpperCase()} — Legenda
          </span>
          <svg
            className={`w-3 h-3 text-gray-400 transition-transform ${legendOpen ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {legendOpen && (
          <div className="px-3 pb-3 space-y-1.5 border-t border-gray-100">
            {LEGEND_STEPS.map((step) => (
              <div key={step.range} className="flex items-center gap-2 pt-1 first:pt-1.5">
                <div
                  className="w-3 h-3 rounded-sm flex-shrink-0 border border-black/10"
                  style={{ backgroundColor: step.color }}
                />
                <span className="text-[11px] font-semibold text-gray-700 w-[68px] flex-shrink-0">
                  {step.label}
                </span>
                <span className="text-[10px] text-gray-400">{step.range}</span>
              </div>
            ))}
            <div className="flex items-center gap-2 pt-1 border-t border-gray-100">
              <div className="w-3 h-3 rounded-sm flex-shrink-0 bg-gray-300 border border-black/10" />
              <span className="text-[11px] text-gray-400">Tidak ada data</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
