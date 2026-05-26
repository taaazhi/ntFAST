import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { FloatingNav } from '../components/FloatingNav';
import { AnalysisNotification } from '../components/AnalysisNotification';
import { useAuth } from '../context/AuthContext';
import { ActivityProvider } from '../context/ActivityContext';
import { BackgroundAnalysisProvider } from '../context/BackgroundAnalysisContext';
import { NotificationsProvider } from '../context/NotificationsContext';

export const Layout: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2" style={{ borderColor: 'var(--accent)' }}></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <ActivityProvider>
      <BackgroundAnalysisProvider>
        <NotificationsProvider>
          {/* Animated mesh gradient background */}
          <div className="bg-mesh">
            <div className="blob blob-1" />
            <div className="blob blob-2" />
            <div className="blob blob-3" />
            <div className="blob blob-4" />
          </div>

          {/* Floating navigation */}
          <FloatingNav />

          {/* Main content */}
          <main className="glass-content">
            <AnalysisNotification />
            <Outlet />
          </main>
        </NotificationsProvider>
      </BackgroundAnalysisProvider>
    </ActivityProvider>
  );
};
