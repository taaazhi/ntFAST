import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import Modal from './ui/Modal';
import { formatTimeAgo } from '../hooks/useActivityMonitor';
import { authAPI } from '../services/api';

interface LoginHistoryRecord {
  id: number;
  login_time: string | null;
  logout_time: string | null;
  session_duration: number | null;
  ip_address: string | null;
  user_agent: string | null;
  location: string | null;
  is_suspicious: boolean;
}

interface ActiveSession {
  id: number;
  login_time: string | null;
  ip_address: string | null;
  user_agent: string | null;
  location: string | null;
  is_suspicious: boolean;
  // Backend-decided flag: true for the session that matches the requesting UA+IP.
  // Falls back to the newest session if no exact match.
  is_current?: boolean;
}

// Friendly label for localhost / private IPs (common in dev / LAN). In prod
// users will see real public IPs — this just makes 127.0.0.1 readable.
const isPrivateIp = (ip: string | null): boolean => {
  if (!ip) return false;
  if (ip === '127.0.0.1' || ip === '::1' || ip === 'localhost') return true;
  // RFC1918 private ranges
  if (/^10\./.test(ip)) return true;
  if (/^192\.168\./.test(ip)) return true;
  if (/^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(ip)) return true;
  return false;
};

interface AccountSecurityProps {
  userId: number;
}

const AccountSecurity: React.FC<AccountSecurityProps> = ({ userId }) => {
  const { t } = useTranslation();
  const [loginHistory, setLoginHistory] = useState<LoginHistoryRecord[]>([]);
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTerminateModal, setShowTerminateModal] = useState(false);

  // Fetch login history
  const fetchLoginHistory = async () => {
    try {
      const data = await authAPI.loginHistory(10);
      setLoginHistory(data.history || []);
    } catch (error) {
      console.error('Failed to fetch login history:', error);
    }
  };

  // Fetch active sessions
  const fetchActiveSessions = async () => {
    try {
      const data = await authAPI.activeSessions();
      setActiveSessions(data.active_sessions || []);
    } catch (error) {
      console.error('Failed to fetch active sessions:', error);
    }
  };

  // Close all sessions
  const handleCloseAllSessions = async () => {
    try {
      const data = await authAPI.closeAllSessions();
      toast.success(data.message);
      // Refresh active sessions
      await fetchActiveSessions();
      setShowTerminateModal(false);
    } catch (error) {
      console.error('Failed to close all sessions:', error);
      toast.error('Failed to close sessions');
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        await Promise.all([fetchLoginHistory(), fetchActiveSessions()]);
      } catch (error) {
        console.error('Failed to load security data:', error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [userId]);

  if (loading) {
    return (
      <div className="flex justify-center items-center p-8">
        <div className="text-gray-500">{t('common.loading')}</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Active Sessions Section */}
      <Card>
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {t('security.activeSessions')}
            </h2>
            {activeSessions.length > 1 && (
              <Button
                variant="ghost"
                onClick={() => setShowTerminateModal(true)}
                className="text-red-600 hover:bg-red-50 dark:hover:bg-red-900"
              >
                {t('security.closeAllSessions')}
              </Button>
            )}
          </div>

          <div className="space-y-3">
            {activeSessions.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400">{t('security.noActiveSessions')}</p>
            ) : (
              activeSessions.map((session) => {
                // Prefer server-provided is_current (matches UA+IP); index-0 fallback only if absent.
                const isCurrent = session.is_current === true;
                return (
                <div
                  key={session.id}
                  className={`p-4 border rounded-lg ${
                    isCurrent
                      ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
                      : 'bg-gray-50 border-gray-200 dark:bg-gray-800 dark:border-gray-700'
                  } ${
                    session.is_suspicious
                      ? 'border-red-500 dark:border-red-600'
                      : ''
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-white">
                          {isCurrent ? t('security.currentSession') : t('security.otherDevice')}
                        </span>
                        {session.is_suspicious && (
                          <span className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded dark:bg-red-900 dark:text-red-200">
                            {t('security.suspicious')}
                          </span>
                        )}
                      </div>
                      <div className="mt-2 space-y-1 text-sm text-gray-600 dark:text-gray-400">
                        <p>
                          <span className="font-medium">{t('security.loginTime')}:</span>{' '}
                          {session.login_time ? formatTimeAgo(session.login_time, t) : t('common.unknown')}
                        </p>
                        {session.ip_address && (
                          <p>
                            <span className="font-medium">{t('security.ipAddress')}:</span>{' '}
                            {isPrivateIp(session.ip_address) ? (
                              <span title={session.ip_address}>{session.ip_address} ({t('security.localDev') || 'local dev'})</span>
                            ) : session.ip_address}
                          </p>
                        )}
                        {session.location && (
                          <p>
                            <span className="font-medium">{t('security.location')}:</span> {session.location}
                          </p>
                        )}
                        {session.user_agent && (
                          <p className="text-xs text-gray-500 dark:text-gray-500">
                            {session.user_agent.substring(0, 80)}...
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                );
              })
            )}
          </div>

          {activeSessions.length > 1 && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg dark:bg-yellow-900/20 dark:border-yellow-800">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                {t('security.multipleSessionsWarning', { count: activeSessions.length })}
              </p>
            </div>
          )}
        </div>
      </Card>

      {/* Login History Section */}
      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            {t('security.loginHistory')}
          </h2>

          <div className="space-y-3">
            {loginHistory.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400">{t('security.noLoginHistory')}</p>
            ) : (
              loginHistory.map((record, index) => (
                <div
                  key={record.id}
                  className={`p-4 border rounded-lg ${
                    record.is_suspicious
                      ? 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
                      : 'bg-gray-50 border-gray-200 dark:bg-gray-800 dark:border-gray-700'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        {index === 0 && (
                          <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded dark:bg-blue-900 dark:text-blue-200">
                            {t('security.latestLogin')}
                          </span>
                        )}
                        {record.is_suspicious && (
                          <span className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded dark:bg-red-900 dark:text-red-200">
                            {t('security.suspicious')}
                          </span>
                        )}
                        {!record.logout_time && (
                          <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded dark:bg-green-900 dark:text-green-200">
                            {t('security.activeNow')}
                          </span>
                        )}
                      </div>
                      <div className="space-y-1 text-sm text-gray-600 dark:text-gray-400">
                        <p>
                          <span className="font-medium">{t('security.loginTime')}:</span>{' '}
                          {record.login_time ? new Date(record.login_time).toLocaleString() : t('common.unknown')}
                        </p>
                        {record.logout_time && (
                          <p>
                            <span className="font-medium">{t('security.logoutTime')}:</span>{' '}
                            {new Date(record.logout_time).toLocaleString()}
                          </p>
                        )}
                        {record.session_duration !== null && (
                          <p>
                            <span className="font-medium">{t('security.sessionDuration')}:</span>{' '}
                            {Math.floor(record.session_duration / 60)} {t('common.minutes')}
                          </p>
                        )}
                        {record.ip_address && (
                          <p>
                            <span className="font-medium">{t('security.ipAddress')}:</span> {record.ip_address}
                          </p>
                        )}
                        {record.location && (
                          <p>
                            <span className="font-medium">{t('security.location')}:</span> {record.location}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </Card>

      {/* Terminate All Sessions Modal */}
      {showTerminateModal && (
        <Modal isOpen={showTerminateModal} onClose={() => setShowTerminateModal(false)} title={t('security.confirmCloseAllSessions')}>
          <div className="p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              {t('security.confirmCloseAllSessions')}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {t('security.closeAllSessionsWarning')}
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="ghost" onClick={() => setShowTerminateModal(false)}>
                {t('common.cancel')}
              </Button>
              <Button variant="danger" onClick={handleCloseAllSessions}>
                {t('security.confirmClose')}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

export default AccountSecurity;
