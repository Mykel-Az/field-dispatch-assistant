import { createBrowserRouter, Outlet } from 'react-router-dom';
import { AuthProvider } from './auth/AuthProvider';
import { HomeRedirect, PublicOnly, RequireAuth, RequireRole } from './auth/guards';
import LoginPage from './auth/pages/LoginPage';
import RegisterPage from './auth/pages/RegisterPage';
import DashboardPage from './dispatcher/pages/home';
import OrganizationPage from './dispatcher/pages/OrganizationPage';
import UsersPage from './dispatcher/pages/UsersPage';
import AppLayout from './layout/AppLayout';
import TechnicianHome from './technician/pages/TechnicianHome';

// navigation hooks and wraps every page.
export const router = createBrowserRouter([
  {
    element: (
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    ),
    children: [
      { element: <PublicOnly />, children: [
        { path: '/login', element: <LoginPage /> },
        { path: '/register', element: <RegisterPage /> },
      ] },
      { element: <RequireAuth />, children: [
        { path: '/', element: <HomeRedirect /> },
        { element: <AppLayout />, children: [
          { element: <RequireRole roles={['head_dispatcher', 'dispatcher']} />, children: [
            { path: '/dashboard', element: <DashboardPage /> },
            { path: '/organization', element: <OrganizationPage /> },
          ] },
          { element: <RequireRole roles={['head_dispatcher']} />, children: [
            { path: '/users', element: <UsersPage /> },
          ] },
          { element: <RequireRole roles={['technician']} />, children: [
            { path: '/tech', element: <TechnicianHome /> },
          ] },
        ] },
      ] },
    ],
  },
]);