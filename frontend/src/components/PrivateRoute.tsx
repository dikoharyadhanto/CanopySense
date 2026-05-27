import { Navigate, Outlet } from 'react-router-dom';
import { getStoredToken } from '../lib/auth';

export default function PrivateRoute() {
  const token = getStoredToken();
  if (!token) return <Navigate to="/login" replace />;
  return <Outlet />;
}
