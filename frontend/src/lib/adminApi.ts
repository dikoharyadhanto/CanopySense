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
