import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LandingPage from '../features/landing/pages/LandingPage';
import LoginPage from '../features/auth/pages/LoginPage';
import AuthCallback from '../features/auth/pages/AuthCallback';
import HomePage from '../features/dashboard/pages/HomePage';
import { AuthProvider } from '../features/auth/hooks/useAuth';
import ProtectedRoute from '../components/ProtectedRoute';

export default function AppRoutes() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route 
            path="/home" 
            element={
              <ProtectedRoute>
                <HomePage />
              </ProtectedRoute>
            } 
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
