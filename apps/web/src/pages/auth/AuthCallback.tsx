import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Extract token from query params
    const queryParams = new URLSearchParams(location.search);
    const token = queryParams.get('token');

    if (token) {
      // In a real app, this might go to Context or Redux
      // For now, storing in localStorage is fine to persist auth state
      localStorage.setItem('codelense_token', token);
      
      // Successfully authenticated, go to home
      navigate('/home', { replace: true });
    } else {
      // Auth failed or invalid callback, go back to login
      navigate('/login', { replace: true });
    }
  }, [location.search, navigate]);

  return (
    <div className="min-h-screen bg-ink flex items-center justify-center">
      <div className="font-mono text-paper text-sm animate-pulse tracking-widest">
        AUTHENTICATING...
      </div>
    </div>
  );
}
