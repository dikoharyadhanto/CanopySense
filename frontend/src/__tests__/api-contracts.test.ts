import { describe, it, expect, afterEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '../lib/api';

const mock = new MockAdapter(api);

afterEach(() => mock.reset());

describe('GET /api/blocks — response shape contract', () => {
  it('returns an array where each item has required fields', async () => {
    mock.onGet('/api/blocks').reply(200, [
      {
        block_id: 1,
        code: 'B-07',
        name: 'Blok B-07',
        afdeling_name: 'Afdeling II',
        estate_name: 'Kebun Raya',
        geometry: { type: 'Polygon', coordinates: [[]] },
        latest_ndvi: 0.5812,
        latest_evi: 0.4123,
        latest_ndre: null,
        latest_savi: 0.4901,
        latest_gndvi: 0.4512,
        acquisition_date: '2026-04-06',
        cloud_cover: 5,
      },
    ]);

    const res = await api.get('/api/blocks');
    expect(Array.isArray(res.data)).toBe(true);
    const block = res.data[0];
    expect(block).toHaveProperty('block_id');
    expect(block).toHaveProperty('code');
    expect(block).toHaveProperty('name');
    expect(block).toHaveProperty('geometry');
    expect(block).toHaveProperty('latest_ndvi');
    expect(block).toHaveProperty('latest_evi');
    expect(block).toHaveProperty('latest_ndre');
    expect(block).toHaveProperty('latest_savi');
    expect(block).toHaveProperty('latest_gndvi');
    expect(block).toHaveProperty('acquisition_date');
    expect(block).toHaveProperty('cloud_cover');
  });
});

describe('GET /api/blocks/{id}/indices — response shape contract', () => {
  it('returns date-ascending rows with required fields', async () => {
    mock.onGet('/api/blocks/1/indices').reply(200, [
      {
        acquisition_date: '2023-04-02',
        sensor: 'S2',
        cloud_cover: 3,
        ndvi: 0.512,
        evi: 0.401,
        ndre: null,
        savi: 0.489,
        gndvi: 0.445,
      },
      {
        acquisition_date: '2024-01-15',
        sensor: 'S2',
        cloud_cover: 12,
        ndvi: 0.563,
        evi: 0.421,
        ndre: 0.311,
        savi: 0.501,
        gndvi: 0.461,
      },
    ]);

    const res = await api.get('/api/blocks/1/indices');
    expect(Array.isArray(res.data)).toBe(true);
    const row = res.data[0];
    expect(row).toHaveProperty('acquisition_date');
    expect(row).toHaveProperty('ndvi');
    expect(row).toHaveProperty('evi');
    expect(row).toHaveProperty('ndre');
    expect(row).toHaveProperty('savi');
    expect(row).toHaveProperty('gndvi');
    expect(row).toHaveProperty('cloud_cover');
    expect(row).toHaveProperty('sensor');
    expect(res.data[0].acquisition_date <= res.data[1].acquisition_date).toBe(true);
  });
});
