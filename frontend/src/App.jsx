import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { ThemeProvider } from './hooks/useTheme';
import { AuthProvider } from './hooks/useAuth';
import AppShell from './components/layout/AppShell';
import Landing from './pages/Landing';
import Guide from './pages/Guide';
import Dashboard from './pages/Dashboard';
import NewRun from './pages/NewRun';
import LiveRun from './pages/LiveRun';
import RunDetail from './pages/RunDetail';
import History from './pages/History';
import Memory from './pages/Memory';
import Config from './pages/Config';

/** Every navigation should start at the top of the new page. */
function ScrollToTop() {
  const { pathname } = useLocation();
  // Block body, not a concise arrow: an effect must return a cleanup function
  // or nothing, and a concise arrow returns whatever the call evaluates to.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

/** Wraps the application routes in the sidebar shell; the landing page opts out. */
function Shell({ children }) {
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <ScrollToTop />
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/guide" element={<Guide />} />
            <Route path="/dashboard" element={<Shell><Dashboard /></Shell>} />
            <Route path="/runs/new" element={<Shell><NewRun /></Shell>} />
            <Route path="/runs/:runId/live" element={<Shell><LiveRun /></Shell>} />
            <Route path="/runs/:runId" element={<Shell><RunDetail /></Shell>} />
            <Route path="/history" element={<Shell><History /></Shell>} />
            <Route path="/memory" element={<Shell><Memory /></Shell>} />
            <Route path="/config" element={<Shell><Config /></Shell>} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
