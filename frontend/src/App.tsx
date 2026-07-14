import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AnimatePresence } from 'framer-motion';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import NewScan from './pages/NewScan';
import History from './pages/History';
import ScanDetails from './pages/ScanDetails';
import Profile from './pages/Profile';
import AdminDashboard from './pages/AdminDashboard';
import BreachChecker from './pages/BreachChecker';
import WebIntelPage from './pages/WebIntelPage';
import AttackSurface from './pages/AttackSurface';
import Exposures from './pages/Exposures';
import Remediation from './pages/Remediation';
import Schedules from './pages/Schedules';
import AiToolsRegistry from './pages/AiToolsRegistry';
import AiScanView from './pages/AiScanView';
import DeepScanView from './pages/DeepScanView';
import Engagements from './pages/Engagements';

const AnimatedRoutes = () => {
  const location = useLocation();
  
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/scan/new" element={<NewScan />} />
              <Route path="/scan/history" element={<History />} />
              <Route path="/scan/:id" element={<ScanDetails />} />
              <Route path="/ai-scan/:id" element={<AiScanView />} />
              <Route path="/deep-scan/:id" element={<DeepScanView />} />
              <Route path="/ai-tools" element={<AiToolsRegistry />} />
              <Route path="/engagements" element={<Engagements />} />
              <Route path="/attack-surface" element={<AttackSurface />} />
              <Route path="/exposures" element={<Exposures />} />
              <Route path="/remediation" element={<Remediation />} />
              <Route path="/schedules" element={<Schedules />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/admin" element={<AdminDashboard />} />
              <Route path="/breach-checker" element={<BreachChecker />} />
              <Route path="/webintel" element={<WebIntelPage />} />
          </Route>
        </Route>
      </Routes>
    </AnimatePresence>
  );
};

import { ThemeProvider } from './context/ThemeContext';
import { SSEProvider } from './context/SSEContext';

// ... (existing imports moved or kept, handled by logic below)

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <SSEProvider>
          <Router>
            <AnimatedRoutes />
          </Router>
        </SSEProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
