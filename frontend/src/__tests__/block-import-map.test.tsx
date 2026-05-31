import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createElement } from 'react';
import BlockImportMap from '../components/BlockImportMap';
import type { Feature } from 'geojson';

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: unknown }) =>
    createElement('div', { 'data-testid': 'map-container' }, children as never),
  TileLayer: () => null,
  GeoJSON: () => null,
  useMap: () => ({ fitBounds: vi.fn() }),
}));
vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('leaflet', () => ({
  default: {
    latLngBounds: () => ({ extend: vi.fn(), isValid: () => true }),
  },
  latLngBounds: () => ({ extend: vi.fn(), isValid: () => true }),
}));

const sampleFeature: Feature = {
  type: 'Feature',
  geometry: {
    type: 'Polygon',
    coordinates: [
      [[107.619, -6.917], [107.629, -6.917], [107.629, -6.927], [107.619, -6.917]],
    ],
  },
  properties: {
    block_code: 'BLK-001',
    block_name: 'Blok Utara 1',
    afdeling_code: 'AFD-A',
    afdeling_name: 'Afdeling A',
  },
};

// TC-006: BlockImportMap renders without crashing given a valid FeatureCollection
describe('BlockImportMap — TC-006', () => {
  it('renders map container given valid features', () => {
    render(createElement(BlockImportMap, { features: [sampleFeature] }));
    expect(screen.getByTestId('map-container')).toBeDefined();
  });

  it('renders with multiple features without crashing', () => {
    const feat2: Feature = {
      ...sampleFeature,
      properties: {
        ...sampleFeature.properties,
        block_code: 'BLK-002',
        afdeling_name: 'Afdeling B',
      },
    };
    render(createElement(BlockImportMap, { features: [sampleFeature, feat2] }));
    expect(screen.getByTestId('map-container')).toBeDefined();
  });
});

// TC-007: BlockImportMap renders error state given empty features array
describe('BlockImportMap — TC-007', () => {
  it('shows empty-state message when features is empty', () => {
    render(createElement(BlockImportMap, { features: [] }));
    expect(screen.queryByTestId('map-container')).toBeNull();
    expect(screen.getByTestId('block-import-map-empty')).toBeDefined();
    const msg = screen.getByTestId('block-import-map-empty').textContent ?? '';
    expect(msg.toLowerCase()).toContain('no valid geometries');
  });
});
