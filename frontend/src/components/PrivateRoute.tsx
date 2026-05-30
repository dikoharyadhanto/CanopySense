import { Navigate, Outlet } from 'react-router-dom';
import { getStoredToken, getStoredUser } from '../lib/auth';

export default function PrivateRoute() {
  const token = getStoredToken();
  if (!token) return <Navigate to="/login" replace />;

  const user = getStoredUser();
  // Unaffiliated users (no company_id and not admin/super_admin) see empty state
  if (
    user &&
    !user.company_id &&
    user.role !== 'super_admin' &&
    user.role !== 'admin'
  ) {
    return <Navigate to="/empty-state" replace />;
  }

  return <Outlet />;
}
