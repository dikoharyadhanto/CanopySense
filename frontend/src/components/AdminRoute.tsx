import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { getMe } from '../lib/adminApi';
import { getStoredToken } from '../lib/auth';

type Status = 'loading' | 'allowed' | 'forbidden' | 'unauthenticated';

export default function AdminRoute() {
  const [status, setStatus] = useState<Status>('loading');

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setStatus('unauthenticated');
      return;
    }
    getMe()
      .then((user) => {
        if (user.is_admin || user.is_global_admin) {
          setStatus('allowed');
        } else {
          setStatus('forbidden');
        }
      })
      .catch(() => setStatus('unauthenticated'));
  }, []);

  if (status === 'loading') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        Checking access...
      </div>
    );
  }
  if (status === 'unauthenticated') return <Navigate to="/login" replace />;
  if (status === 'forbidden') return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
