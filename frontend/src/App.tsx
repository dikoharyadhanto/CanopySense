import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ExploreMap from './pages/ExploreMap';
import TimeSeries from './pages/TimeSeries';
import Unavailable from './pages/Unavailable';
import SetupAccount from './pages/SetupAccount';
import PrivateRoute from './components/PrivateRoute';
import Layout from './components/Layout';
import AdminRoute from './components/AdminRoute';
import AdminLayout from './components/AdminLayout';
import AdminDashboard from './pages/admin/AdminDashboard';
import CompanyList from './pages/admin/CompanyList';
import CompanyDetail from './pages/admin/CompanyDetail';
import ManagerInvite from './pages/admin/ManagerInvite';
import SubscriptionEdit from './pages/admin/SubscriptionEdit';
import UserManagement from './pages/admin/UserManagement';
import AuditLog from './pages/admin/AuditLog';
import PipelineTrigger from './pages/admin/PipelineTrigger';
import PipelineRunHistory from './pages/admin/PipelineRunHistory';
import PipelineSchedules from './pages/admin/PipelineSchedules';
import EstateOnboarding from './pages/admin/EstateOnboarding';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/setup" element={<SetupAccount />} />

        {/* Manager product surfaces */}
        <Route element={<PrivateRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/explore-map" element={<ExploreMap />} />
            <Route path="/timeseries" element={<TimeSeries />} />
            <Route path="/unavailable" element={<Unavailable />} />
          </Route>
        </Route>

        {/* Admin surfaces (admin + super-admin only) */}
        <Route element={<AdminRoute />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/companies" element={<CompanyList />} />
            <Route path="/admin/companies/:companyId" element={<CompanyDetail />} />
            <Route path="/admin/companies/:companyId/invite" element={<ManagerInvite />} />
            <Route path="/admin/companies/:companyId/subscription" element={<SubscriptionEdit />} />
            <Route path="/admin/users" element={<UserManagement />} />
            <Route path="/admin/audit" element={<AuditLog />} />
            <Route path="/admin/pipeline/trigger" element={<PipelineTrigger />} />
            <Route path="/admin/pipeline/history" element={<PipelineRunHistory />} />
            <Route path="/admin/pipeline/schedules" element={<PipelineSchedules />} />
            <Route path="/admin/estate-onboarding" element={<EstateOnboarding />} />
          </Route>
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
