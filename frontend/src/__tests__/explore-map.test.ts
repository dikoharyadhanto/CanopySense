import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { createElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import api from '../lib/api';
import { fetchRasterMetadata, fetchUserContext, RasterApiError } from '../lib/rasterApi';
import ExploreMap from '../pages/ExploreMap';

// Stub react-leaflet so jsdom does not need a real Leaflet canvas environment
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: unknown }) =>
    createElement('div', { 'data-testid': 'map-container' }, children as never),
  TileLayer: ({ url }: { url: string }) =>
    createElement('div', { 'data-testid': 'tile-layer', 'data-url': url }),
  GeoJSON: () => createElement('div', { 'data-testid': 'geojson-layer' }),
  useMap: () => ({ fitBounds: vi.fn() }),
}));
vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('leaflet', () => ({ default: {} }));

// Single shared MockAdapter — multiple instances on the same axios object override each other
const mock = new MockAdapter(api);
beforeEach(() => mock.reset());

const MOCK_METADATA = {
  schema_version: '1.0',
  serving_mode: 'gee_mapid',
  subscription_tier: 'basic',
  index: 'ndvi',
  sensor: 'S2',
  date_acquired: '2026-05-21',
  date_window_start: '2026-05-14',
  date_window_end: '2026-05-21',
  valid_pixel_ratio: 0.847,
  low_quality: false,
  bounds: { west: 104.12, south: -3.22, east: 104.51, north: -2.98 },
  resolution_m: 10,
  palette: ['red', 'yellow', 'green'],
  viz_min: -0.2,
  viz_max: 0.9,
  tile_url_format: 'https://earthengine.googleapis.com/v1/projects/test/maps/abc123/{z}/{x}/{y}',
  tile_url_expires_note: '~48 hours',
  cloud_nodata_note: 'Cloudy pixels masked.',
  generated_at_utc: '2026-05-27T10:00:00+00:00',
};

const MOCK_USER_BASIC = {
  username: 'manager',
  role: 'manager',
  company_id: 1,
  subscription_tier: 'basic',
};

const MOCK_USER_PREMIUM = {
  username: 'dikoharyadhanto',
  role: 'manager',
  company_id: 2,
  subscription_tier: 'premium',
};

function renderExploreMap() {
  return render(createElement(MemoryRouter, null, createElement(ExploreMap)));
}

// ─── rasterApi unit tests ─────────────────────────────────────────────────────

describe('rasterApi — fetchRasterMetadata (TC-002)', () => {
  it('returns typed RasterMetadata with all 18 fields on 200', async () => {
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);
    const data = await fetchRasterMetadata({ index: 'ndvi' });

    expect(data.tile_url_format).toBe(MOCK_METADATA.tile_url_format);
    expect(Array.isArray(data.palette)).toBe(true);
    expect(data.bounds).toHaveProperty('west');

    // Verify all 18 contract fields
    const fields = [
      'schema_version', 'serving_mode', 'subscription_tier', 'index', 'sensor',
      'date_acquired', 'date_window_start', 'date_window_end', 'valid_pixel_ratio',
      'low_quality', 'bounds', 'resolution_m', 'palette', 'viz_min', 'viz_max',
      'tile_url_format', 'tile_url_expires_note', 'cloud_nodata_note', 'generated_at_utc',
    ];
    for (const f of fields) {
      expect(data, `missing field: ${f}`).toHaveProperty(f);
    }
  });

  it('throws RasterApiError status 503 on GEE unavailable', async () => {
    mock.onGet('/api/raster/metadata').reply(503, { detail: 'GEE initialization failed' });
    await expect(fetchRasterMetadata()).rejects.toMatchObject({
      name: 'RasterApiError', status: 503,
    });
  });

  it('throws RasterApiError status 402 on no subscription', async () => {
    mock.onGet('/api/raster/metadata').reply(402, { detail: 'No active subscription' });
    await expect(fetchRasterMetadata()).rejects.toMatchObject({ status: 402 });
  });

  it('throws RasterApiError status 403 on date out of range', async () => {
    mock.onGet('/api/raster/metadata').reply(403, { detail: 'Date outside timelapse window' });
    await expect(fetchRasterMetadata({ date_start: '2020-01-01' })).rejects.toMatchObject({
      status: 403,
    });
  });

  it('throws RasterApiError status 404 on no estate blocks', async () => {
    mock.onGet('/api/raster/metadata').reply(404, { detail: 'No blocks found' });
    await expect(fetchRasterMetadata()).rejects.toMatchObject({ status: 404 });
  });

  it('throws RasterApiError status 401 on missing auth', async () => {
    mock.onGet('/api/raster/metadata').reply(401, { detail: 'Not authenticated' });
    await expect(fetchRasterMetadata()).rejects.toMatchObject({ status: 401 });
  });
});

describe('rasterApi — fetchUserContext (TC-002)', () => {
  it('returns UserContext with subscription_tier on 200', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    const ctx = await fetchUserContext();
    expect(ctx.subscription_tier).toBe('basic');
    expect(ctx.username).toBe('manager');
    expect(ctx).toHaveProperty('company_id');
    expect(ctx).toHaveProperty('role');
  });
});

describe('RasterApiError', () => {
  it('carries status code and message', () => {
    const err = new RasterApiError(503, 'GEE failed');
    expect(err.status).toBe(503);
    expect(err.message).toBe('GEE failed');
    expect(err.name).toBe('RasterApiError');
    expect(err instanceof Error).toBe(true);
  });
});

// ─── ExploreMap component tests ───────────────────────────────────────────────

describe('ExploreMap — subscription gating (TASK-005)', () => {
  it('TC-005: basic user — date controls hidden, Basic badge shown', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);

    renderExploreMap();

    // Wait for userCtx to load (badge appears only after /auth/me resolves)
    await waitFor(() => expect(screen.getByTestId('subscription-badge')).toBeDefined());

    expect(screen.queryByTestId('date-controls')).toBeNull();
    expect(screen.getByTestId('subscription-badge').textContent).toContain('Basic');
  });

  it('TC-006: premium user — date controls shown, Premium badge shown', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_PREMIUM);
    mock.onGet('/api/raster/metadata').reply(200, { ...MOCK_METADATA, subscription_tier: 'premium' });

    renderExploreMap();

    await waitFor(() => expect(screen.getByTestId('subscription-badge')).toBeDefined());

    expect(screen.getByTestId('date-controls')).toBeDefined();
    expect(screen.getByTestId('subscription-badge').textContent).toContain('Premium');
  });
});

describe('ExploreMap — error states (TASK-008)', () => {
  it('TC-010: 503 → shows GEE unavailable title (no success placeholder)', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(503, { detail: 'GEE initialization failed' });

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    expect(screen.getByTestId('error-overlay')).toBeDefined();
    const title = screen.getByTestId('error-title').textContent ?? '';
    expect(title).toContain('GEE');
  });

  it('TC-011: 404 → shows no estate data message', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(404, { detail: 'No blocks found' });

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    const title = screen.getByTestId('error-title').textContent ?? '';
    expect(title.toLowerCase()).toContain('estate');
  });

  it('TC-012: 403 → shows date range error message', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_PREMIUM);
    mock.onGet('/api/raster/metadata').reply(403, { detail: 'Date outside timelapse window' });

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    const title = screen.getByTestId('error-title').textContent ?? '';
    expect(title.toLowerCase()).toContain('tanggal');
  });

  it('402 → shows subscription error message', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(402, { detail: 'No active subscription' });

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    const title = screen.getByTestId('error-title').textContent ?? '';
    expect(title.toLowerCase()).toContain('subscription');
  });
});

describe('ExploreMap — raster tile from backend (TC-003, no fake raster)', () => {
  it('TC-003: raster-tile-layer probe URL matches tile_url_format from API response', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    // Test probe span (in MapContainer) captures the URL from metadata — no hardcoded raster
    const probe = screen.getByTestId('raster-tile-layer');
    expect(probe.getAttribute('data-url')).toBe(MOCK_METADATA.tile_url_format);
  });

  it('TC-003: different tile_url_format from API is reflected in the probe', async () => {
    const customUrl = 'https://earthengine.googleapis.com/v1/projects/custom/maps/xyz456/{z}/{x}/{y}';
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, { ...MOCK_METADATA, tile_url_format: customUrl });

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    const probe = screen.getByTestId('raster-tile-layer');
    expect(probe.getAttribute('data-url')).toBe(customUrl);
  });
});

describe('ExploreMap — metadata panel (TC-007, TASK-006)', () => {
  it('metadata panel shows index, sensor, and acquisition date', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.getByTestId('metadata-panel')).toBeDefined());

    const header = screen.getByTestId('metadata-panel').textContent ?? '';
    expect(header).toContain('NDVI');
    expect(header).toContain('S2');
    expect(header).toContain('2026-05-21');
  });
});

describe('ExploreMap — control elements (TASK-007)', () => {
  it('opacity slider, block overlay toggle, and refresh button are present', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    expect(screen.getByTestId('opacity-slider')).toBeDefined();
    expect(screen.getByTestId('block-overlay-toggle')).toBeDefined();
    expect(screen.getByTestId('refresh-btn')).toBeDefined();
  });
});
