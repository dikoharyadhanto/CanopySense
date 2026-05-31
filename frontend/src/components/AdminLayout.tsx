import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getMe, UserContext } from '../lib/adminApi';
import { getStoredUser, clearToken } from '../lib/auth';

function Initials({ name }: { name: string }) {
  const letters = name
    .split(/[\s_-]/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
  return (
    <div className="w-8 h-8 rounded-full bg-indigo-700 flex items-center justify-center
                    text-white text-xs font-bold select-none flex-shrink-0">
      {letters || '?'}
    </div>
  );
}

export default function AdminLayout() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = getStoredUser();
  const [me, setMe] = useState<UserContext | null>(null);

  useEffect(() => {
    getMe().then(setMe).catch(() => {});
  }, []);

  function handleLogout() {
    clearToken();
    navigate('/login', { replace: true });
  }

  const ADMIN_NAV = [
    { to: '/admin',             label: t('navigation.admin.dashboard'),  end: true },
    { to: '/admin/companies',   label: t('navigation.admin.companies'),  end: false },
    { to: '/admin/audit',       label: t('navigation.admin.auditLog'),   end: false },
  ];

  const PIPELINE_NAV = [
    { to: '/admin/pipeline/trigger',   label: t('navigation.admin.triggerRun'), end: false },
    { to: '/admin/pipeline/history',   label: t('navigation.admin.runHistory'), end: false },
    { to: '/admin/pipeline/schedules', label: t('navigation.admin.schedules'),  end: false },
  ];

  const DATA_NAV = [
    { to: '/admin/estate-onboarding', label: t('navigation.admin.estateOnboarding'), end: false },
  ];

  const SUPER_ADMIN_NAV = [
    { to: '/admin/users',                    label: t('navigation.admin.adminUsers'),     end: false },
    { to: '/admin/data-viewer',              label: t('navigation.admin.dataViewer'),     end: false },
    { to: '/admin/estate-change-requests',   label: t('navigation.admin.estateChange'),   end: false },
    { to: '/admin/registrations',            label: t('navigation.admin.registrations'),  end: false },
    { to: '/admin/system-settings',          label: t('navigation.admin.systemSettings'), end: false },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 bg-[#1E2A3A] text-white flex flex-col">
        {/* Branding */}
        <div className="px-4 pt-5 pb-4 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-indigo-500 flex items-center justify-center
                            text-white text-sm font-bold select-none flex-shrink-0">
              A
            </div>
            <div className="min-w-0">
              <div className="text-sm font-bold tracking-wide truncate">Admin Panel</div>
              <div className="text-[10px] text-indigo-300/80 leading-tight truncate">
                CanopySense
              </div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          <div className="pt-1 pb-1 px-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400/60">
              {t('navigation.admin.management')}
            </div>
          </div>
          {ADMIN_NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-indigo-700/60 text-white font-semibold border-l-2 border-indigo-400'
                    : 'text-slate-300/80 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              {label}
            </NavLink>
          ))}

          <div className="pt-4 pb-1 px-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400/60">
              {t('navigation.admin.pipeline')}
            </div>
          </div>
          {PIPELINE_NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-indigo-700/60 text-white font-semibold border-l-2 border-indigo-400'
                    : 'text-slate-300/80 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              {label}
            </NavLink>
          ))}

          <div className="pt-4 pb-1 px-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400/60">
              {t('navigation.admin.data')}
            </div>
          </div>
          {DATA_NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-indigo-700/60 text-white font-semibold border-l-2 border-indigo-400'
                    : 'text-slate-300/80 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              {label}
            </NavLink>
          ))}

          {me?.is_global_admin && (
            <>
              <div className="pt-4 pb-1 px-3">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400/60">
                  {t('navigation.admin.superAdmin')}
                </div>
              </div>
              {SUPER_ADMIN_NAV.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                      isActive
                        ? 'bg-indigo-700/60 text-white font-semibold border-l-2 border-indigo-400'
                        : 'text-slate-300/80 hover:bg-white/10 hover:text-white'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}
            </>
          )}

          <div className="pt-4 pb-1 px-3">
            <NavLink
              to="/dashboard"
              className="flex items-center gap-2 px-0 py-1 text-[11px] text-slate-400 hover:text-white transition-colors"
            >
              {t('navigation.admin.backToDashboard')}
            </NavLink>
          </div>
        </nav>

        {/* User context */}
        <div className="border-t border-white/10 px-4 py-3">
          <div className="flex items-center gap-2.5 mb-2">
            <Initials name={user?.sub ?? '?'} />
            <div className="min-w-0">
              <div className="text-xs text-slate-100 font-semibold truncate">
                {user?.sub ?? '—'}
              </div>
              <div className="text-[10px] text-indigo-300/60 capitalize truncate">Admin</div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="text-[11px] text-red-300/70 hover:text-red-300 transition-colors"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
