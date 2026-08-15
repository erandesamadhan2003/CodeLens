import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../features/auth/hooks/useAuth';

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-ink flex items-center justify-center">
        <div className="font-mono text-paper text-sm animate-pulse tracking-widest">
          AUTHENTICATING...
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
