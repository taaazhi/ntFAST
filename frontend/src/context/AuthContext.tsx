import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authAPI } from '../services/api';
import type { User, LoginCredentials } from '../types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  // Track mount status so async work that finishes after unmount doesn't trigger
  // "Can't perform a React state update on an unmounted component" warnings.
  const isMountedRef = React.useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    const initAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const currentUser = await authAPI.getCurrentUser();
          if (isMountedRef.current) setUser(currentUser);
        } catch (error) {
          localStorage.removeItem('access_token');
        }
      }
      if (isMountedRef.current) setLoading(false);
    };

    initAuth();
    // Heartbeat is handled by WebSocket in useActivityMonitor (single mechanism)
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const login = async (credentials: LoginCredentials) => {
    const response = await authAPI.login(credentials);

    // SECURITY: Use session_start from BACKEND (single source of truth)
    // NEVER create timestamp on frontend - always use backend time
    // This ensures identical timestamp between frontend and backend
    if (response.session_start) {
      localStorage.setItem('session_start', response.session_start);
    }

    // Save token FIRST so getCurrentUser() can use it in Authorization header
    localStorage.setItem('access_token', response.access_token);

    // Fetch current user (includes previous_login from backend)
    const currentUser = await authAPI.getCurrentUser();

    // SECURITY: Save previous_login to localStorage (backend is source of truth)
    // This value is FIXED and should NEVER change during current session
    if (currentUser.previous_login) {
      localStorage.setItem('previous_login', currentUser.previous_login);
    }

    if (isMountedRef.current) setUser(currentUser);
  };

  const logout = async () => {
    try {
      // Call backend logout endpoint to update online status
      await authAPI.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Always clear local storage and redirect
      localStorage.removeItem('access_token');
      // SECURITY: Clear session_start and previous_login on logout
      localStorage.removeItem('session_start');
      localStorage.removeItem('previous_login');
      setUser(null);
      window.location.href = '/login';
    }
  };

  const value = {
    user,
    loading,
    login,
    logout,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
