import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LandingPage from '../features/landing/pages/LandingPage';
import LoginPage from '../features/auth/pages/LoginPage';
import AuthCallback from '../features/auth/pages/AuthCallback';
import HomePage from '../features/dashboard/pages/HomePage';
import { AuthProvider } from '../features/auth/hooks/useAuth';
import ProtectedRoute from '../components/ProtectedRoute';
import InfrastructureDashboard from '../features/infrastructure/pages/InfrastructureDashboard';
import SecurityDashboard from '../features/security/pages/SecurityDashboard';
import DependencyDashboard from '../features/dependency/pages/DependencyDashboard';
import CodeQualityDashboard from '../features/code-quality/pages/CodeQualityDashboard';
import DocumentsDashboard from '../features/documents/pages/DocumentsDashboard';

export default function AppRoutes() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          
          {/* Main Dashboard */}
          <Route 
            path="/home" 
            element={
              <ProtectedRoute>
                <HomePage />
              </ProtectedRoute>
            } 
          />
          {/* Engine Dashboards */}
          <Route 
            path="/dashboard/infrastructure/:repoId" 
            element={
              <ProtectedRoute>
                <InfrastructureDashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/dashboard/security/:repoId" 
            element={
              <ProtectedRoute>
                <SecurityDashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/dashboard/dependency/:repoId" 
            element={
              <ProtectedRoute>
                <DependencyDashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/dashboard/code-quality/:repoId" 
            element={
              <ProtectedRoute>
                <CodeQualityDashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/dashboard/documents/:repoId" 
            element={
              <ProtectedRoute>
                <DocumentsDashboard />
              </ProtectedRoute>
            } 
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
