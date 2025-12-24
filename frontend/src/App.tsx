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
              <Route path="/profile" element={<Profile />} />
              <Route path="/admin" element={<AdminDashboard />} />
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
