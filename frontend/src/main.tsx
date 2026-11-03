import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import './index.css';
import { WakeGate } from './shared/components/WakeGate';
import { router } from './router';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WakeGate>
      <RouterProvider router={router} />
    </WakeGate>
  </StrictMode>,
);