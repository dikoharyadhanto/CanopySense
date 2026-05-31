import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import api, { API_BASE } from '../lib/api';
import { getStoredUser, clearToken } from '../lib/auth';

const PHASE1_NAV = [
  { to: '/dashboard',    label: 'Dashboard' },
  { to: '/explore-map',  label: 'Explore Map' },
  { to: '/timeseries',   label: 'Time-Series Analyzer' },
];

const PHASE2_NAV = [
  'Long-Term Trends',
  'Model Studio',
  'Alerts & Tasking',
  'Reports & Export',
];

function Initials({ name }: { name: string }) {
  const letters = name
    .split(/[\s_-]/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
  return (
    <div className="w-8 h-8 rounded-full bg-green-700 flex items-center justify-center
                    text-white text-xs font-bold select-none flex-shrink-0">
      {letters || '?'}
    </div>
  );
}

interface Branding {
  company_name: string | null;
  show_name_in_header: boolean;
  show_logo_in_header: boolean;
  has_logo: boolean;
}

export default function Layout() {
  const navigate = useNavigate();
  const user = getStoredUser();
  const [branding, setBranding] = useState<Branding | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (user?.company_id) {
      api.get<Branding>(`/api/companies/${user.company_id}/branding`)
        .then((r) => setBranding(r.data))
        .catch(() => {});
    }
  }, [user?.company_id]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    }
    if (showMenu) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMenu]);

  const showName = branding?.show_name_in_header && branding.company_name;
  const showLogo = branding?.show_logo_in_header && branding.has_logo;

  function handleLogout() {
    clearToken();
    navigate('/login', { replace: true });
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#F4FAF6]">
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 bg-[#1B3A2D] text-white flex flex-col">
        {/* Branding */}
        <div className="px-4 pt-5 pb-4 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-[#19C853] flex items-center justify-center
                            text-white text-sm font-bold select-none flex-shrink-0">
              C
            </div>
            <div className="min-w-0">
              <div className="text-sm font-bold tracking-wide truncate">CanopySense</div>
              <div className="text-[10px] text-green-300/80 leading-tight truncate">
                Monitoring Perkebunan Karet
              </div>
            </div>
          </div>
        </div>

        {/* Phase 1 nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {PHASE1_NAV.map(({ to, label }) => (
            <NavLink
              key={label}
              to={to}
              end={to === '/dashboard'}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-green-700/60 text-white font-semibold border-l-2 border-[#19C853]'
                    : 'text-green-100/80 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              {label}
            </NavLink>
          ))}

          {/* Back to Admin Panel */}
          {(user?.role === 'super_admin' || user?.role === 'admin') && (
            <div className="pt-4 pb-1 px-3">
              <NavLink
                to="/admin"
                className="flex items-center gap-2 px-0 py-1 text-[11px] text-green-400/60 hover:text-white transition-colors"
              >
                ← Admin Panel
              </NavLink>
            </div>
          )}

          {/* Phase 2+ section */}
          <div className="pt-4 pb-1 px-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-green-400/50">
              Segera Hadir
            </div>
          </div>

          {PHASE2_NAV.map((label) => (
            <NavLink
              key={label}
              to="/unavailable"
              className="flex items-center justify-between px-3 py-2 rounded-md text-sm
                         text-green-100/30 hover:bg-white/5 transition-colors cursor-default"
              tabIndex={-1}
            >
              <span className="truncate">{label}</span>
              <span className="text-[9px] bg-green-900/50 text-green-300/50 px-1.5 py-0.5
                               rounded flex-shrink-0 ml-1">
                Fase 2
              </span>
            </NavLink>
          ))}

        </nav>

        {/* User context */}
        <div className="border-t border-white/10 px-3 py-3 relative" ref={menuRef}>
          {showMenu && (
            <div className="absolute bottom-full left-2 right-2 mb-1 bg-[#162e22] border border-white/15 rounded-lg shadow-xl overflow-hidden">
              <NavLink
                to="/profile"
                onClick={() => setShowMenu(false)}
                className="flex items-center gap-2 px-3 py-2.5 text-sm text-green-100/80 hover:bg-white/10 hover:text-white transition-colors"
              >
                Profil Saya
              </NavLink>
              {user?.role === 'manager' && (
                <NavLink
                  to="/settings"
                  onClick={() => setShowMenu(false)}
                  className="flex items-center gap-2 px-3 py-2.5 text-sm text-green-100/80 hover:bg-white/10 hover:text-white transition-colors"
                >
                  Pengaturan Manajemen
                </NavLink>
              )}
              <button
                onClick={handleLogout}
                className="w-full text-left flex items-center gap-2 px-3 py-2.5 text-sm text-red-300/70 hover:text-red-300 hover:bg-white/10 transition-colors border-t border-white/10"
              >
                Logout
              </button>
            </div>
          )}
          <button
            onClick={() => setShowMenu((v) => !v)}
            className="flex items-center gap-2.5 w-full rounded-md px-1 py-1 hover:bg-white/10 transition-colors"
          >
            <Initials name={user?.sub ?? '?'} />
            <div className="min-w-0 flex-1 text-left">
              <div className="text-xs text-green-100 font-semibold truncate">
                {user?.sub ?? '—'}
              </div>
              <div className="text-[10px] text-green-300/60 capitalize truncate">
                {user?.role ?? 'Unknown Role'}
              </div>
            </div>
            <svg
              className={`w-3 h-3 text-green-400/60 flex-shrink-0 transition-transform ${showMenu ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        {(showName || showLogo) && (
          <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-100 shadow-sm flex-shrink-0">
            {/* Left — company identity */}
            <div className="flex items-center gap-4 min-w-0">
              {showLogo && user?.company_id && (
                <img
                  src={`${API_BASE}/api/companies/${user.company_id}/logo`}
                  alt="Company logo"
                  style={{ maxHeight: 44, maxWidth: 160 }}
                  className="object-contain block flex-shrink-0"
                />
              )}
              {showName && (
                <div className="text-base font-bold text-slate-800 truncate">
                  {branding!.company_name}
                </div>
              )}
            </div>

            {/* Divider */}
            <div className="mx-6 h-9 w-px bg-gray-200 flex-shrink-0" />

            {/* Right — platform identity */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <div className="w-2 h-2 rounded-full bg-[#19C853] flex-shrink-0" />
              <div className="text-right">
                <div className="text-base font-bold text-[#1B3A2D] tracking-wide leading-tight">
                  CanopySense
                </div>
                <div className="text-xs text-slate-500 leading-tight mt-0.5">
                  Monitoring Kerapatan Kanopi Perkebunan Karet
                </div>
              </div>
            </div>
          </div>
        )}
        <Outlet />
      </div>
    </div>
  );
}
