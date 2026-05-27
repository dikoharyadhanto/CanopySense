import api from './api';
import type { AxiosError } from 'axios';

export interface RasterBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface RasterMetadata {
  schema_version: string;
  serving_mode: string;
  subscription_tier: 'basic' | 'premium';
  index: string;
  sensor: string;
  date_acquired: string;
  date_window_start: string;
  date_window_end: string;
  valid_pixel_ratio: number;
  low_quality: boolean;
  bounds: RasterBounds;
  resolution_m: number;
  palette: string[];
  viz_min: number;
  viz_max: number;
  tile_url_format: string;
  tile_url_expires_note: string;
  cloud_nodata_note: string;
  generated_at_utc: string;
}

export interface UserContext {
  username: string;
  role: string | null;
  company_id: number | null;
  subscription_tier: 'basic' | 'premium' | null;
}

export interface FetchRasterParams {
  index?: string;
  date_start?: string;
  date_end?: string;
}

export class RasterApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'RasterApiError';
  }
}

export async function fetchRasterMetadata(
  params: FetchRasterParams = {},
): Promise<RasterMetadata> {
  try {
    const res = await api.get<RasterMetadata>('/api/raster/metadata', { params });
    return res.data;
  } catch (err) {
    const axiosErr = err as AxiosError<{ detail?: string }>;
    const status = axiosErr.response?.status ?? 0;
    const detail = axiosErr.response?.data?.detail ?? axiosErr.message;
    throw new RasterApiError(status, detail);
  }
}

export async function fetchUserContext(): Promise<UserContext> {
  try {
    const res = await api.get<UserContext>('/auth/me');
    return res.data;
  } catch (err) {
    const axiosErr = err as AxiosError<{ detail?: string }>;
    const status = axiosErr.response?.status ?? 0;
    const detail = axiosErr.response?.data?.detail ?? axiosErr.message;
    throw new RasterApiError(status, detail);
  }
}
