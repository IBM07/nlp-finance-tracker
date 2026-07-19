import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';

export default function App() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login />}
      />
      <Route
        path="/signup"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Signup />}
      />

      {/* Protected routes */}
      <Route
        path="/dashboard"
        element={<ProtectedRoute><Dashboard /></ProtectedRoute>}
      />
      {/* Default redirect */}
      <Route
        path="*"
        element={<Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />}
      />
    </Routes>
  );
}
