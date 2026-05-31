import { NavLink, Outlet, useNavigate } from 'react-router-dom';
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

export default function Layout() {
  const navigate = useNavigate();
  const user = getStoredUser();

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
        <div className="border-t border-white/10 px-4 py-3">
          <NavLink
            to="/profile"
            className="flex items-center gap-2.5 mb-2 rounded-md px-1 py-1 hover:bg-white/10 transition-colors"
          >
            <Initials name={user?.sub ?? '?'} />
            <div className="min-w-0">
              <div className="text-xs text-green-100 font-semibold truncate">
                {user?.sub ?? '—'}
              </div>
              <div className="text-[10px] text-green-300/60 capitalize truncate">
                {user?.role ?? 'Unknown Role'}
              </div>
            </div>
          </NavLink>
          <button
            onClick={handleLogout}
            className="text-[11px] text-red-300/70 hover:text-red-300 transition-colors ml-1"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        <Outlet />
      </div>
    </div>
  );
}
