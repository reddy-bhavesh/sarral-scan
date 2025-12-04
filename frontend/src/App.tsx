import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AnimatePresence } from 'framer-motion';
import Login from './pages/Login';
import Register from './pages/Register';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import NewScan from './pages/NewScan';
import History from './pages/History';
import ScanDetails from './pages/ScanDetails';

const AnimatedRoutes = () => {
  const location = useLocation();
  
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/scan/new" element={<NewScan />} />
              <Route path="/scan/history" element={<History />} />
              <Route path="/scan/:id" element={<ScanDetails />} />
              <Route path="/" element={<Navigate to="/dashboard" />} />
          </Route>
        </Route>
      </Routes>
    </AnimatePresence>
  );
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <AnimatedRoutes />
      </Router>
    </AuthProvider>
  );
}

export default App;
