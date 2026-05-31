import { useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { Feature, FeatureCollection } from 'geojson';

interface Props {
  features: Feature[];
}

const PALETTE = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#06B6D4', '#84CC16', '#F97316', '#6366F1',
];

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function afdelingColor(name: string): string {
  return PALETTE[hashStr(name) % PALETTE.length];
}

function BoundsFitter({ features }: { features: Feature[] }) {
  const map = useMap();
  useEffect(() => {
    if (!features.length) return;
    const bounds = L.latLngBounds([]);
    for (const feat of features) {
      const geom = feat.geometry as { type: string; coordinates: unknown };
      if (!geom) continue;
      const polys: number[][][][] =
        geom.type === 'Polygon'
          ? [(geom.coordinates as number[][][])]
          : geom.type === 'MultiPolygon'
          ? (geom.coordinates as number[][][][])
          : [];
      for (const poly of polys) {
        for (const ring of poly) {
          for (const coord of ring) {
            bounds.extend([coord[1], coord[0]]);
          }
        }
      }
    }
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [20, 20] });
  }, [features, map]);
  return null;
}

export default function BlockImportMap({ features }: Props) {
  if (features.length === 0) {
    return (
      <div
        data-testid="block-import-map-empty"
        className="flex items-center justify-center h-48 bg-slate-50 border border-slate-200 rounded-lg"
      >
        <p className="text-sm text-slate-500">No valid geometries to display.</p>
      </div>
    );
  }

  const fc: FeatureCollection = { type: 'FeatureCollection', features };

  return (
    <MapContainer
      data-testid="map-container"
      center={[0, 118]}
      zoom={5}
      style={{ height: '480px', width: '100%', borderRadius: '8px', border: '1px solid #e2e8f0' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      <GeoJSON
        key={features.length}
        data={fc}
        style={(feature) => {
          const name = (feature?.properties?.afdeling_name as string) ?? '';
          const color = afdelingColor(name);
          return { color, fillColor: color, fillOpacity: 0.4, weight: 1.5 };
        }}
        onEachFeature={(feature, layer) => {
          const props = feature.properties ?? {};
          const code = String(props.block_code ?? '—');
          const afd = String(props.afdeling_name ?? '—');
          layer.bindTooltip(`${code} · ${afd}`, { sticky: true });
        }}
      />
      <BoundsFitter features={features} />
    </MapContainer>
  );
}
