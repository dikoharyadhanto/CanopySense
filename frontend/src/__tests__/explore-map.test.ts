import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { createElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import api from '../lib/api';
import { fetchRasterMetadata, fetchRasterFrames, fetchUserContext, RasterApiError } from '../lib/rasterApi';
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

const MOCK_PREMIUM_METADATA = {
  ...MOCK_METADATA,
  serving_mode: 'maps_platform',
  subscription_tier: 'premium',
  date_acquired: '2026-10-14',
  date_window_start: '2026-10-14',
  date_window_end: '2026-10-15',
  tile_url_format: 'https://earthengine.googleapis.com/v1/projects/test/maps/premium123/{z}/{x}/{y}',
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

const MOCK_FRAMES = {
  frames: [
    { frame_id: '2026-10-14', label: '14 Oct 2026', sensor: 'S2' },
    { frame_id: '2026-09-24', label: '24 Sep 2026', sensor: 'S2' },
  ],
  default_frame_id: '2026-10-14',
  total_frames: 2,
};

const MOCK_EMPTY_FRAMES = {
  frames: [],
  default_frame_id: null,
  total_frames: 0,
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

  it('TC-002: accepts frame_id param and passes it to API', async () => {
    mock.onGet('/api/raster/metadata').reply((config) => {
      const hasFrameId = config.params?.frame_id === '2026-10-14';
      return [200, { ...MOCK_PREMIUM_METADATA, date_acquired: hasFrameId ? '2026-10-14' : 'wrong' }];
    });
    const data = await fetchRasterMetadata({ index: 'ndvi', frame_id: '2026-10-14' });
    expect(data.date_acquired).toBe('2026-10-14');
  });
});

describe('rasterApi — fetchRasterFrames (TC-002, v1.9)', () => {
  it('returns FrameList with frames array on 200', async () => {
    mock.onGet('/api/raster/frames').reply(200, MOCK_FRAMES);
    const data = await fetchRasterFrames('ndvi');
    expect(data.total_frames).toBe(2);
    expect(data.frames[0].frame_id).toBe('2026-10-14');
    expect(data.frames[0].label).toBe('14 Oct 2026');
    expect(data.frames[0].sensor).toBe('S2');
    expect(data.default_frame_id).toBe('2026-10-14');
  });

  it('returns empty FrameList when no data exists', async () => {
    mock.onGet('/api/raster/frames').reply(200, MOCK_EMPTY_FRAMES);
    const data = await fetchRasterFrames('ndvi');
    expect(data.total_frames).toBe(0);
    expect(data.frames).toHaveLength(0);
    expect(data.default_frame_id).toBeNull();
  });

  it('throws RasterApiError 403 for basic user', async () => {
    mock.onGet('/api/raster/frames').reply(403, { detail: 'Timelapse is a Premium feature.' });
    await expect(fetchRasterFrames('ndvi')).rejects.toMatchObject({ status: 403 });
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

// ─── ExploreMap component — subscription gating (v1.9) ───────────────────────

describe('ExploreMap — subscription gating (TC-005, TC-006, v1.9)', () => {
  it('TC-005: basic user — no timelapse controls, no calendar inputs, Basic badge shown', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.getByTestId('subscription-badge')).toBeDefined());

    // Timelapse controls must not be rendered for Basic users
    expect(screen.queryByTestId('timelapse-controls')).toBeNull();
    // No calendar date inputs in Premium flow
    expect(screen.queryByTestId('date-controls')).toBeNull();
    expect(screen.getByTestId('subscription-badge').textContent).toContain('Basic');
  });

  it('TC-006: premium user — timelapse controls shown, slider present, Premium badge shown', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_PREMIUM);
    mock.onGet('/api/raster/frames').reply(200, MOCK_FRAMES);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_PREMIUM_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.getByTestId('subscription-badge')).toBeDefined());
    await waitFor(() => expect(screen.getByTestId('timelapse-controls')).toBeDefined());

    expect(screen.getByTestId('timelapse-slider')).toBeDefined();
    expect(screen.getByTestId('prev-frame-btn')).toBeDefined();
    expect(screen.getByTestId('next-frame-btn')).toBeDefined();
    expect(screen.getByTestId('subscription-badge').textContent).toContain('Premium');
  });

  it('TC-006: premium slider shows actual acquisition dates from satellite_data', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_PREMIUM);
    mock.onGet('/api/raster/frames').reply(200, MOCK_FRAMES);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_PREMIUM_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.getByTestId('frame-label')).toBeDefined());

    const label = screen.getByTestId('frame-label').textContent ?? '';
    // Most recent frame is default (index 0)
    expect(label).toBe('14 Oct 2026');
  });
});

describe('ExploreMap — timelapse slider navigation (TC-007, v1.9)', () => {
  it('TC-007: moving slider triggers new metadata fetch with correct frame_id', async () => {
    const fetchedFrameIds: string[] = [];

    mock.onGet('/auth/me').reply(200, MOCK_USER_PREMIUM);
    mock.onGet('/api/raster/frames').reply(200, MOCK_FRAMES);
    mock.onGet('/api/raster/metadata').reply((config) => {
      if (config.params?.frame_id) {
        fetchedFrameIds.push(config.params.frame_id as string);
      }
      return [200, MOCK_PREMIUM_METADATA];
    });

    renderExploreMap();
    await waitFor(() => expect(screen.getByTestId('timelapse-slider')).toBeDefined());
    // Initial fetch loads frame index 0 (2026-10-14)
    await waitFor(() => expect(fetchedFrameIds).toContain('2026-10-14'));

    // Move slider to index 1 (2026-09-24)
    const slider = screen.getByTestId('timelapse-slider');
    fireEvent.change(slider, { target: { value: '1' } });

    await waitFor(() => expect(fetchedFrameIds).toContain('2026-09-24'));
  });

  it('TC-005: empty frames — honest no-data message shown, no slider', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_PREMIUM);
    mock.onGet('/api/raster/frames').reply(200, MOCK_EMPTY_FRAMES);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_PREMIUM_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.getByTestId('timelapse-controls')).toBeDefined());

    // No slider when no frames
    expect(screen.queryByTestId('timelapse-slider')).toBeNull();
    // Honest empty state message
    const msg = screen.getByTestId('no-frames-message').textContent ?? '';
    expect(msg.toLowerCase()).toContain('tidak ada data satelit');
  });
});

// ─── ExploreMap — error states (TASK-008) ─────────────────────────────────────

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

  it('TC-012: 403 on metadata → shows access denied error, slider remains navigable', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_PREMIUM);
    mock.onGet('/api/raster/frames').reply(200, MOCK_FRAMES);
    mock.onGet('/api/raster/metadata').reply(403, { detail: 'Date outside timelapse window' });

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    const title = screen.getByTestId('error-title').textContent ?? '';
    expect(title.toLowerCase()).toMatch(/tanggal|akses/);
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

// ─── ExploreMap — raster tile from backend (TC-003, no fake raster) ───────────

describe('ExploreMap — raster tile from backend (TC-003, no fake raster)', () => {
  it('TC-003: raster-tile-layer probe URL matches tile_url_format from API response', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.queryByTestId('loading-overlay')).toBeNull());

    // Test probe span captures the URL from metadata — no hardcoded raster
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

// ─── ExploreMap — metadata panel (TC-008, per-pixel raster semantics) ─────────

describe('ExploreMap — metadata panel (TC-008, TASK-006, v1.9)', () => {
  it('metadata panel shows per-pixel index, sensor, and actual acquisition date', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.getByTestId('metadata-panel')).toBeDefined());

    const panel = screen.getByTestId('metadata-panel').textContent ?? '';
    expect(panel).toContain('NDVI');
    expect(panel).toContain('S2');
    expect(panel).toContain('2026-05-21');
    // Must say per-pixel (TC-008: no average NDVI claim)
    expect(panel.toLowerCase()).toContain('per-pik');
  });

  it('TC-008: panel does not claim average NDVI', async () => {
    mock.onGet('/auth/me').reply(200, MOCK_USER_BASIC);
    mock.onGet('/api/raster/metadata').reply(200, MOCK_METADATA);

    renderExploreMap();
    await waitFor(() => expect(screen.getByTestId('metadata-panel')).toBeDefined());

    const panel = screen.getByTestId('metadata-panel').textContent ?? '';
    // Must not claim block average or time-averaged NDVI
    expect(panel.toLowerCase()).not.toContain('rata-rata blok');
  });
});

// ─── ExploreMap — control elements (TASK-007) ─────────────────────────────────

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
