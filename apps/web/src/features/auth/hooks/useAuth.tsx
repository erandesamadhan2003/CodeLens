import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api } from '../../../api/client';

interface User {
  id: string;
  githubId: string;
  username: string;
  email: string;
  avatar_url: string;
  plan: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = async () => {
    const token = localStorage.getItem('codelense_token');
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const response = await api.get('/api/v1/auth/me');
      setUser(response.data);
    } catch (error) {
      console.error('Failed to authenticate:', error);
      setUser(null);
      localStorage.removeItem('codelense_token');
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api.post('/api/v1/auth/logout', {});
    } catch (err) {
      console.error('Logout failed on server, proceeding to clear local session', err);
    } finally {
      setUser(null);
      localStorage.removeItem('codelense_token');
      window.location.href = '/login';
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
