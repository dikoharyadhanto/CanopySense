import api from './api';

// ---- Types ----

export interface UserContext {
  username: string;
  role: string | null;
  company_id: number | null;
  subscription_tier: string | null;
  is_admin: boolean;
  is_global_admin: boolean;
}

export interface Company {
  id: number;
  company_id: string;
  company_name: string;
  created_at: string;
}

export interface CompanyDetail {
  company: Company & { metadata: Record<string, unknown> };
  readiness: {
    estates: number;
    blocks: number;
    satellite_records: number;
    has_subscription: boolean;
  };
  subscription: Subscription | null;
  managers: Manager[];
}

export interface Subscription {
  id: number;
  company_id: number;
  tier: string;
  status: string;
  billing_interval: string | null;
  subscription_starts_at: string | null;
  subscription_ends_at: string | null;
  timelapse_enabled: boolean;
  timelapse_period_months: number | null;
  raster_serving_mode: string;
  updated_at: string;
}

export interface Manager {
  id: number;
  username: string;
  full_name: string | null;
  email: string;
  is_active: boolean;
  setup_required: boolean;
}

export interface InternalAdmin {
  id: number;
  username: string;
  full_name: string;
  email: string;
  is_admin: boolean;
  is_global_admin: boolean;
  is_active: boolean;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  actor_id: number;
  actor_username: string;
  action: string;
  target_type: string;
  target_id: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface DashboardData {
  company_count: number;
  active_manager_count: number;
  subscription_summary: Record<string, number>;
  recent_audit_actions: AuditEntry[];
}

export interface PaginatedResponse<T> {
  total: number;
  items: T[];
}

// ---- Auth ----

export const getMe = () =>
  api.get<UserContext>('/auth/me').then((r) => r.data);

// ---- Dashboard ----

export const getDashboard = () =>
  api.get<DashboardData>('/api/admin/dashboard').then((r) => r.data);

// ---- Companies ----

export const listCompanies = (params?: { search?: string; limit?: number; offset?: number }) =>
  api.get<PaginatedResponse<Company>>('/api/admin/companies', { params }).then((r) => r.data);

export const createCompany = (body: { company_name: string; metadata?: Record<string, unknown> }) =>
  api.post<Company>('/api/admin/companies', body).then((r) => r.data);

export const getCompanyDetail = (companyId: number) =>
  api.get<CompanyDetail>(`/api/admin/companies/${companyId}`).then((r) => r.data);

// ---- Managers ----

export const createManager = (body: { email: string; company_id: number }) =>
  api.post<{ user: Manager; setup_token: string; setup_token_expires_at: string; note: string }>(
    '/api/admin/managers',
    body,
  ).then((r) => r.data);

export const updateManagerStatus = (userId: number, is_active: boolean) =>
  api.patch(`/api/admin/managers/${userId}/status`, { is_active }).then((r) => r.data);

// ---- Subscriptions ----

export const getSubscription = (companyId: number) =>
  api.get<Subscription>(`/api/admin/subscriptions/${companyId}`).then((r) => r.data);

export const updateSubscription = (companyId: number, body: Partial<Subscription>) =>
  api.patch<Subscription>(`/api/admin/subscriptions/${companyId}`, body).then((r) => r.data);

// ---- Internal Admins (super-admin only) ----

export const listInternalAdmins = () =>
  api.get<InternalAdmin[]>('/api/admin/internal-users').then((r) => r.data);

export const createInternalAdmin = (body: {
  email: string;
  full_name: string;
  username: string;
  password: string;
}) =>
  api.post<InternalAdmin>('/api/admin/internal-users', body).then((r) => r.data);

export const updateInternalAdminStatus = (userId: number, is_active: boolean) =>
  api.patch(`/api/admin/internal-users/${userId}/status`, { is_active }).then((r) => r.data);

// ---- Audit Log ----

export const listAuditLog = (params?: {
  target_type?: string;
  target_id?: number;
  limit?: number;
  offset?: number;
}) =>
  api
    .get<PaginatedResponse<AuditEntry>>('/api/admin/audit', { params })
    .then((r) => r.data);

// ---- Pipeline ----

export interface PipelineEstate {
  id: number;
  name: string;
  code: string;
}

export interface PipelineAfdeling {
  id: number;
  name: string;
  code: string;
}

export interface PipelineRun {
  id: number;
  run_id: string;
  mode: string;
  company_id: number | null;
  estate_id: number | null;
  afdeling_id: number | null;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  date_start: string | null;
  date_end: string | null;
  exit_code: number | null;
  sanitized_error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  actor_username: string;
}

export interface PipelineRunDetail {
  run: PipelineRun;
  batches: Array<{
    id: number;
    trigger_mode: string;
    afdeling_id: number | null;
    block_id: number | null;
    status: string;
    rows_inserted: number;
    api_version: string | null;
    triggered_at: string;
    started_at: string | null;
    estate_id: number | null;
    date_start: string | null;
    date_end: string | null;
  }>;
}

export interface PipelineSchedule {
  id: number;
  created_by: number;
  created_by_username: string;
  mode: string;
  company_id: number | null;
  estate_id: number | null;
  afdeling_id: number | null;
  cadence: string;
  timezone: string;
  date_start: string | null;
  date_end: string | null;
  enabled: boolean;
  next_run: string | null;
  last_run: string | null;
  created_at: string;
  updated_at: string;
}

export const listEstatesForCompany = (companyId: number) =>
  api
    .get<{ items: PipelineEstate[] }>('/api/admin/pipeline/scopes/estates', {
      params: { company_id: companyId },
    })
    .then((r) => r.data.items);

export const listAfdelingsForEstate = (estateId: number) =>
  api
    .get<{ items: PipelineAfdeling[] }>('/api/admin/pipeline/scopes/afdelings', {
      params: { estate_id: estateId },
    })
    .then((r) => r.data.items);

export const triggerPipeline = (body: {
  mode: string;
  company_id: number;
  estate_id: number;
  afdeling_id?: number | null;
  date_start?: string | null;
  date_end?: string | null;
}) =>
  api
    .post<{ run_id: string; status: string }>('/api/admin/pipeline/trigger', body)
    .then((r) => r.data);

export const listPipelineRuns = (params?: { page?: number; page_size?: number }) =>
  api
    .get<{ items: PipelineRun[]; total: number; page: number; page_size: number }>(
      '/api/admin/pipeline/runs',
      { params },
    )
    .then((r) => r.data);

export const getPipelineRun = (runId: string) =>
  api.get<PipelineRunDetail>(`/api/admin/pipeline/runs/${runId}`).then((r) => r.data);

export const listPipelineSchedules = () =>
  api.get<{ items: PipelineSchedule[] }>('/api/admin/pipeline/schedules').then((r) => r.data);

export const createPipelineSchedule = (body: {
  mode: string;
  company_id: number;
  estate_id: number;
  afdeling_id?: number | null;
  cadence: string;
  timezone?: string;
  date_start?: string | null;
  date_end?: string | null;
  first_run_at?: string | null;
}) =>
  api
    .post<{ id: number; status: string }>('/api/admin/pipeline/schedules', body)
    .then((r) => r.data);

export const updatePipelineSchedule = (
  scheduleId: number,
  body: { enabled?: boolean; cadence?: string; timezone?: string; date_start?: string; date_end?: string },
) =>
  api
    .patch<{ id: number; status: string }>(`/api/admin/pipeline/schedules/${scheduleId}`, body)
    .then((r) => r.data);

// ---- Estate Onboarding ----

export interface EstateStub {
  id: number;
  name: string;
  code: string;
  company_id: number;
  is_draft: boolean;
  created_at: string;
  afdeling_count: number;
  block_count: number;
}

export interface EstateDetail extends EstateStub {
  company_name: string;
  afdelings: Array<{
    id: number;
    name: string | null;
    code: string | null;
    block_count: number;
  }>;
  blocks_sample: Array<{
    id: number;
    name: string | null;
    code: string | null;
    plant_year: number | null;
    clone_type: string | null;
    afdeling_code: string | null;
  }>;
}

export interface ImportPreviewResult {
  commit_eligible: boolean;
  file_error: string | null;
  valid_blocks: Array<{
    index: number;
    block_code: string;
    block_name: string;
    afdeling_code: string;
    afdeling_name: string;
    plant_year: number | null;
    clone_type: string | null;
  }>;
  invalid_rows: Array<{
    index: number;
    block_code: string | null;
    reason: string;
  }>;
  afdeling_count: number;
  warnings: string[];
}

export interface ImportCommitResult {
  estate_id: number;
  afdelings_created: number;
  blocks_created: number;
}

export const listOnboardingEstates = (companyId: number) =>
  api
    .get<{ items: EstateStub[] }>(
      `/api/admin/estate-onboarding/companies/${companyId}/estates`,
    )
    .then((r) => r.data.items);

export const createOnboardingEstate = (
  companyId: number,
  body: { name: string; code: string },
) =>
  api
    .post<EstateStub>(
      `/api/admin/estate-onboarding/companies/${companyId}/estates`,
      body,
    )
    .then((r) => r.data);

export const getOnboardingEstateDetail = (estateId: number) =>
  api
    .get<EstateDetail>(`/api/admin/estate-onboarding/estates/${estateId}`)
    .then((r) => r.data);

export const editOnboardingEstate = (
  estateId: number,
  body: { name?: string; code?: string },
) =>
  api
    .patch<EstateStub>(`/api/admin/estate-onboarding/estates/${estateId}`, body)
    .then((r) => r.data);

export const previewImport = (estateId: number, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api
    .post<ImportPreviewResult>(
      `/api/admin/estate-onboarding/estates/${estateId}/import/preview`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    .then((r) => r.data);
};

export const commitImport = (estateId: number, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api
    .post<ImportCommitResult>(
      `/api/admin/estate-onboarding/estates/${estateId}/import/commit`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    .then((r) => r.data);
};

// ---- Data Viewer (super-admin only) ----

export interface DataViewerTable {
  id: string;
  display: string;
  schema: string;
  table: string;
}

export interface DataViewerColumnInfo {
  name: string;
  is_geometry: boolean;
  is_json_summary: boolean;
}

export interface DataViewerColumnMeta {
  table_id: string;
  display: string;
  search_col: string | null;
  sort_allowed: string[];
  columns: DataViewerColumnInfo[];
}

export interface DataViewerRowsResponse {
  table_id: string;
  display: string;
  total: number;
  page: number;
  page_size: number;
  columns: string[];
  rows: Record<string, unknown>[];
}

export const getDataViewerCatalog = () =>
  api.get<{ tables: DataViewerTable[] }>('/api/admin/data-viewer/catalog').then((r) => r.data);

export const getDataViewerColumns = (tableId: string) =>
  api
    .get<DataViewerColumnMeta>(`/api/admin/data-viewer/${tableId}/columns`)
    .then((r) => r.data);

export const getDataViewerRows = (
  tableId: string,
  params: {
    page?: number;
    page_size?: number;
    sort_col?: string;
    sort_dir?: string;
    filter_col?: string;
    filter_val?: string;
  },
) =>
  api
    .get<DataViewerRowsResponse>(`/api/admin/data-viewer/${tableId}/rows`, { params })
    .then((r) => r.data);
