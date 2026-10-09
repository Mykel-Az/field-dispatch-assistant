import { createBrowserRouter } from 'react-router-dom';
import DashboardPage from './dispatcher/pages/home';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <DashboardPage />,
  },
  // Your existing paths (like /tech) go here...
]);
