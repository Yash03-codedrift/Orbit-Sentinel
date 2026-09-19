import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useWebSocket } from './hooks/useWebSocket';
import { useSatellitePositions } from './hooks/useSatellitePositions';
import { useConjunctionFeed } from './hooks/useConjunctionFeed';
import { useSystemStore } from './store/useSystemStore';
import { useRiskConfigStore } from './store/useRiskConfigStore';
import axios from 'axios';
import MainDashboard from './components/Dashboard/MainDashboard';
import LandingPage from './pages/LandingPage';

// Dashboard wrapper — runs all the real-time hooks only when on /app
function DashboardRoute() {
  useWebSocket();
  useSatellitePositions();
  useConjunctionFeed();

  const location = useLocation();

  useEffect(() => {
    useRiskConfigStore.getState().hydrate();
  }, []);

  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const hasDemoParam = searchParams.get('demo') === 'true';
    if (hasDemoParam) {
      useSystemStore.getState().setDemoMode(true);
      console.log('Demo Mode Enabled via URL Context Injection.');
    }
  }, [location.search]);

  useEffect(() => {
    const pollHealth = async () => {
      try {
        const res = await axios.get('/health');
        useSystemStore.getState().updateFromHealth(res.data);
      } catch (err) {
        useSystemStore.getState().setSystemStatus('DEGRADED');
      }
    };
    pollHealth();
    const interval = setInterval(pollHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return <MainDashboard />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<DashboardRoute />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
