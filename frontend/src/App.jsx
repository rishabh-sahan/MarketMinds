import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './hooks/useTheme';
import { AuthProvider } from './hooks/useAuth';
import Navbar from './components/Navbar';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import RunConsole from './pages/RunConsole';
import LiveViewer from './pages/LiveViewer';
import RunDetail from './pages/RunDetail';
import History from './pages/History';
import ConfigEditor from './pages/ConfigEditor';
import AuthCallback from './pages/AuthCallback';

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Navbar />
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/runs/new" element={<RunConsole />} />
            <Route path="/runs/:runId/live" element={<LiveViewer />} />
            <Route path="/runs/:runId" element={<RunDetail />} />
            <Route path="/history" element={<History />} />
            <Route path="/config" element={<ConfigEditor />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
