import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
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
  const v = Math.max(-1, Math.min(1, value));
  if (v <= 0) {
    const t = (v + 1);
    return `rgb(255,${Math.round(t * 255)},0)`;
  }
  const t = v;
  return `rgb(${Math.round((1 - t) * 255)},${Math.round(160 + t * 80)},0)`;
}

function AutoFit({ blocks }: { blocks: Block[] }) {
  const map = useMap();
  const fitted = useRef(false);
  useEffect(() => {
    if (blocks.length === 0 || fitted.current) return;
    const lats: number[] = [];
    const lngs: number[] = [];
    blocks.forEach((b) => {
      const coords = (b.geometry as GeoJSON.Polygon).coordinates[0];
      coords.forEach(([lng, lat]) => { lngs.push(lng); lats.push(lat); });
    });
    if (lats.length) {
      map.fitBounds([[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]], { padding: [30, 30] });
      fitted.current = true;
    }
  }, [blocks, map]);
  return null;
}

export default function MapView({ blocks, selectedIndex, onBlockClick }: Props) {
  const geoJsonKey = `${selectedIndex}-${blocks.length}`;

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
      fillOpacity: 0.75,
      color: '#374151',
      weight: 1,
    };
  }

  function onEachFeature(feature: GeoJSON.Feature, layer: Layer) {
    const block = feature.properties as Block;
    const value = getIndexValue(block, selectedIndex);
    const displayVal = value !== null ? value.toFixed(4) : 'N/A';
    layer.bindPopup(`
      <div style="min-width:180px">
        <div style="font-weight:600;font-size:14px;margin-bottom:4px">${block.name}</div>
        <div style="color:#6b7280;font-size:12px">Afdeling: ${block.afdeling_name}</div>
        <div style="color:#6b7280;font-size:12px">Kode: ${block.code}</div>
        <hr style="margin:6px 0"/>
        <div style="font-size:13px"><strong>${selectedIndex.toUpperCase()}:</strong> ${displayVal}</div>
        <div style="font-size:12px;color:#6b7280">Tanggal: ${block.acquisition_date ?? '-'}</div>
        <div style="font-size:12px;color:#6b7280">Cloud cover: ${block.cloud_cover !== null ? block.cloud_cover + '%' : '-'}</div>
        <hr style="margin:6px 0"/>
        <a href="/timeseries?block_id=${block.block_id}" style="color:#16a34a;font-size:12px;font-weight:600">
          Lihat Time-Series →
        </a>
      </div>
    `);
    layer.on('click', () => onBlockClick(block));
  }

  return (
    <MapContainer
      center={[-0.5, 107.022]}
      zoom={14}
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer
        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {blocks.length > 0 && (
        <>
          <AutoFit blocks={blocks} />
          <GeoJSON
            key={geoJsonKey}
            data={features}
            style={styleFeature}
            onEachFeature={onEachFeature}
          />
        </>
      )}
    </MapContainer>
  );
}
