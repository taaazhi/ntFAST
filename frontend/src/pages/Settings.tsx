import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  UserRound,
  KeyRound,
  BellRing,
  AtSign,
  ShieldCheck,
  Bell,
  BarChart3,
  CalendarDays,
  Timer,
  BadgeCheck,
  AlertCircle,
  UsersRound,
  Eye,
  EyeOff,
  Loader2
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import UserManagement from '../components/UserManagement';
import { PasswordStrength } from '../components/ui/PasswordStrength';
import AccountSecurity from '../components/AccountSecurity';
import { authAPI, usersAPI, NotificationSettings } from '../services/api';

type TabType = 'profile' | 'userManagement' | 'security' | 'notifications';

export const Settings = () => {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabType>('profile');
  const [showSaveMessage, setShowSaveMessage] = useState(false);

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  // Password visibility states
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Notification preferences — loaded from /api/users/me/notification-settings.
  // null while loading, defaults filled in by backend on first GET.
  const [notifSettings, setNotifSettings] = useState<NotificationSettings | null>(null);
  const [notifSaving, setNotifSaving] = useState(false);

  // Load notification settings when tab becomes active (lazy fetch).
  useEffect(() => {
    if (activeTab !== 'notifications' || notifSettings !== null) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await usersAPI.getNotificationSettings();
        if (!cancelled) setNotifSettings(data);
      } catch (err) {
        if (!cancelled) {
          // Fallback to defaults so UI is usable even if endpoint fails
          setNotifSettings({ email: true, in_app: true, security: true, analyses: true });
        }
      }
    })();
    return () => { cancelled = true; };
  }, [activeTab, notifSettings]);

  const handleSaveNotifications = async () => {
    if (!notifSettings) return;
    setNotifSaving(true);
    try {
      const updated = await usersAPI.updateNotificationSettings(notifSettings);
      setNotifSettings(updated);
      toast.success(t('settings.notificationsSaved') || 'Notification preferences saved');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t('common.error') || 'Save failed');
    } finally {
      setNotifSaving(false);
    }
  };

  const toggleNotifPref = (key: keyof NotificationSettings) => {
    setNotifSettings(prev => prev ? { ...prev, [key]: !prev[key] } : prev);
  };

  const tabs = [
    { id: 'profile' as const, label: t('settings.profile'), icon: UserRound },
    ...(user?.role === 'admin' ? [{ id: 'userManagement' as const, label: t('settings.userManagement'), icon: UsersRound }] : []),
    { id: 'security' as const, label: t('settings.security'), icon: KeyRound },
    { id: 'notifications' as const, label: t('settings.notifications'), icon: BellRing },
  ];

  const handleSave = () => {
    setShowSaveMessage(true);
    setTimeout(() => setShowSaveMessage(false), 3000);
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError('');
    setPasswordSuccess(false);

    // Validation
    if (newPassword.length < 6) {
      setPasswordError(t('register.passwordTooShort'));
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError(t('register.passwordMismatch'));
      return;
    }

    setChangingPassword(true);

    try {
      await authAPI.changePassword({
        current_password: currentPassword,
        new_password: newPassword
      });

      setPasswordSuccess(true);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');

      setTimeout(() => {
        setPasswordSuccess(false);
      }, 3000);
    } catch (err: any) {
      setPasswordError(err.response?.data?.detail || t('common.error'));
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <div className="px-8 pb-8 fade-in">
      <div className="max-w-5xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.2, color: 'var(--text)' }}>
            {t('settings.title')}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, marginTop: 6 }}>
            {t('settings.subtitle')}
          </p>
        </div>

        {/* Save Success Message */}
        <AnimatePresence>
          {showSaveMessage && (
            <motion.div
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              transition={{ duration: 0.3 }}
              className="fixed top-8 right-8 z-50 backdrop-blur-xl rounded-2xl shadow-2xl p-4 flex items-center gap-3"
              style={{ background: 'var(--success-bg)', border: '1px solid rgba(26,115,232,0.3)' }}
            >
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--success)' }}>
                <BadgeCheck className="w-5 h-5" style={{ color: '#ffffff' }} />
              </div>
              <div>
                <p className="font-semibold" style={{ color: 'var(--success)' }}>{t('common.success')}</p>
                <p className="text-sm" style={{ color: 'var(--success)' }}>{t('common.success')}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main Card */}
        <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
          {/* Accent gradient bar */}
          <div style={{ height: 3, background: 'var(--accent)' }} />

            {/* Tabs */}
            <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
              <div className="flex gap-2 overflow-x-auto">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;

                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`nav-item ${isActive ? 'active' : ''}`}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, padding: '8px 18px' }}
                    >
                      <Icon style={{ width: 15, height: 15 }} />
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Tab Content */}
            <div className="p-8">
              <AnimatePresence mode="wait">
                {activeTab === 'profile' && (
                  <motion.div
                    key="profile"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-8"
                  >
                    {/* User Info Card */}
                    <div className="relative">
                      <div className="relative rounded-2xl border p-6" style={{ background: 'var(--accent-subtle)', borderColor: 'var(--card-border)' }}>
                        <div className="flex items-center gap-6">
                          <div className="w-20 h-20 rounded-2xl flex items-center justify-center" style={{ background: 'var(--accent)', boxShadow: '0 8px 24px var(--accent-glow)' }}>
                            <span className="text-3xl font-bold" style={{ color: '#ffffff' }}>
                              {user?.full_name?.charAt(0) || 'U'}
                            </span>
                          </div>
                          <div>
                            <h3 className="text-2xl font-bold mb-1" style={{ color: 'var(--text)' }}>
                              {user?.full_name || t('common.user')}
                            </h3>
                            <p className="text-sm capitalize" style={{ color: 'var(--text-muted)' }}>
                              {user?.role === 'admin' ? t('settings.admin') : user?.role === 'analyst' ? 'Analyst' : 'Observer'}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Form Fields */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {[
                        { label: t('settings.fullName'), value: user?.full_name, icon: UserRound },
                        { label: t('settings.email'), value: user?.email, icon: AtSign },
                        { label: t('settings.role'), value: user?.role === 'admin' ? t('settings.admin') : user?.role === 'analyst' ? 'Analyst' : 'Observer', icon: ShieldCheck },
                      ].map((field, index) => {
                        const Icon = field.icon;
                        return (
                          <motion.div
                            key={field.label}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.1 + index * 0.05 }}
                          >
                            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                              {field.label}
                            </label>
                            <div className="relative">
                              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                <Icon className="w-5 h-5" style={{ color: 'var(--text-faint)' }} />
                              </div>
                              <input
                                type="text"
                                value={field.value || ''}
                                disabled
                                className="w-full pl-12 pr-4 py-3 rounded-xl backdrop-blur-xl transition-all duration-300 cursor-not-allowed opacity-75"
                                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--card-border)', color: 'var(--text)' }}
                              />
                            </div>
                          </motion.div>
                        );
                      })}
                    </div>

                    {/* Account Info */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="backdrop-blur-xl rounded-xl p-6"
                        style={{ background: 'var(--bg-secondary)', border: '1px solid var(--card-border)' }}
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--success)' }}>
                            <CalendarDays className="w-6 h-6" style={{ color: '#ffffff' }} />
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>
                              {t('dashboard.registrationDate')}
                            </p>
                            <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
                              {user?.created_at
                                ? new Date(user.created_at).toLocaleDateString('ru-RU', {
                                    day: 'numeric',
                                    month: 'long',
                                    year: 'numeric'
                                  })
                                : 'N/A'}
                            </p>
                          </div>
                        </div>
                      </motion.div>

                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.35 }}
                        className="backdrop-blur-xl rounded-xl p-6"
                        style={{ background: 'var(--bg-secondary)', border: '1px solid var(--card-border)' }}
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--accent)' }}>
                            <Timer className="w-6 h-6" style={{ color: '#ffffff' }} />
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>
                              {t('dashboard.lastLogin')}
                            </p>
                            <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
                              {user?.last_login
                                ? new Date(user.last_login).toLocaleString('ru-RU')
                                : 'N/A'}
                            </p>
                          </div>
                        </div>
                      </motion.div>
                    </div>

                    <motion.button
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.4 }}
                      whileHover={{ scale: 1.02, y: -2 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleSave}
                      className="btn-gradient"
                      style={{ width: '100%', padding: '14px 24px', justifyContent: 'center' }}
                    >
                      {t('common.save')}
                    </motion.button>
                  </motion.div>
                )}

                {activeTab === 'userManagement' && (
                  <motion.div
                    key="userManagement"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ duration: 0.3 }}
                  >
                    <UserManagement />
                  </motion.div>
                )}

                {activeTab === 'security' && (
                  <motion.div
                    key="security"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-8"
                  >
                    {/* Change Password Section */}
                    <div className="space-y-6">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--danger)' }}>
                          <KeyRound className="w-6 h-6" style={{ color: '#ffffff' }} />
                        </div>
                        <div>
                          <h3 className="text-xl font-bold" style={{ color: 'var(--text)' }}>{t('settings.changePassword')}</h3>
                          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('settings.changePasswordDesc')}</p>
                        </div>
                      </div>

                      {/* Password Success Message */}
                      <AnimatePresence>
                        {passwordSuccess && (
                          <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="p-3 rounded-xl backdrop-blur-xl flex items-start gap-2"
                            style={{ background: 'var(--success-bg)', border: '1px solid rgba(26,115,232,0.2)' }}
                          >
                            <BadgeCheck className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: 'var(--success)' }} />
                            <p className="text-xs" style={{ color: 'var(--success)' }}>{t('settings.passwordChanged')}</p>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* Password Error Message */}
                      <AnimatePresence>
                        {passwordError && (
                          <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="p-3 rounded-xl backdrop-blur-xl flex items-start gap-2"
                            style={{ background: 'var(--danger-bg)', border: '1px solid rgba(220,38,38,0.2)' }}
                          >
                            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
                            <p className="text-xs" style={{ color: 'var(--danger)' }}>{passwordError}</p>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      <form onSubmit={handleChangePassword} className="space-y-4">
                        {/* Current Password */}
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.1 }}
                        >
                          <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                            {t('settings.currentPassword')}
                          </label>
                          <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                              <KeyRound className="w-5 h-5" style={{ color: 'var(--text-faint)' }} />
                            </div>
                            <input
                              type={showCurrentPassword ? "text" : "password"}
                              value={currentPassword}
                              onChange={(e) => setCurrentPassword(e.target.value)}
                              placeholder={t('settings.currentPasswordPlaceholder')}
                              disabled={changingPassword}
                              required
                              className="w-full pl-12 pr-12 py-3 rounded-xl backdrop-blur-xl focus:outline-none focus:ring-2 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--card-border)', color: 'var(--text)', '--tw-ring-color': 'rgba(26,115,232,0.4)' } as React.CSSProperties}
                            />
                            <button
                              type="button"
                              onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                              className="absolute inset-y-0 right-0 pr-4 flex items-center transition-colors"
                              style={{ color: 'var(--text-faint)' }}
                            >
                              {showCurrentPassword ? (
                                <EyeOff className="w-5 h-5" />
                              ) : (
                                <Eye className="w-5 h-5" />
                              )}
                            </button>
                          </div>
                        </motion.div>

                        {/* New Password */}
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.15 }}
                        >
                          <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                            {t('settings.newPassword')}
                          </label>
                          <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                              <KeyRound className="w-5 h-5" style={{ color: 'var(--text-faint)' }} />
                            </div>
                            <input
                              type={showNewPassword ? "text" : "password"}
                              value={newPassword}
                              onChange={(e) => setNewPassword(e.target.value)}
                              placeholder={t('settings.newPasswordPlaceholder')}
                              disabled={changingPassword}
                              required
                              className="w-full pl-12 pr-12 py-3 rounded-xl backdrop-blur-xl focus:outline-none focus:ring-2 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--card-border)', color: 'var(--text)', '--tw-ring-color': 'rgba(26,115,232,0.4)' } as React.CSSProperties}
                            />
                            <button
                              type="button"
                              onClick={() => setShowNewPassword(!showNewPassword)}
                              className="absolute inset-y-0 right-0 pr-4 flex items-center transition-colors"
                              style={{ color: 'var(--text-faint)' }}
                            >
                              {showNewPassword ? (
                                <EyeOff className="w-5 h-5" />
                              ) : (
                                <Eye className="w-5 h-5" />
                              )}
                            </button>
                          </div>
                          <AnimatePresence>
                            {newPassword && <PasswordStrength password={newPassword} />}
                          </AnimatePresence>
                        </motion.div>

                        {/* Confirm New Password */}
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.2 }}
                        >
                          <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                            {t('settings.confirmPassword')}
                          </label>
                          <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                              <KeyRound className="w-5 h-5" style={{ color: 'var(--text-faint)' }} />
                            </div>
                            <input
                              type={showConfirmPassword ? "text" : "password"}
                              value={confirmPassword}
                              onChange={(e) => setConfirmPassword(e.target.value)}
                              placeholder={t('settings.confirmPasswordPlaceholder')}
                              disabled={changingPassword}
                              required
                              className="w-full pl-12 pr-12 py-3 rounded-xl backdrop-blur-xl focus:outline-none focus:ring-2 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--card-border)', color: 'var(--text)', '--tw-ring-color': 'rgba(26,115,232,0.4)' } as React.CSSProperties}
                            />
                            <button
                              type="button"
                              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                              className="absolute inset-y-0 right-0 pr-4 flex items-center transition-colors"
                              style={{ color: 'var(--text-faint)' }}
                            >
                              {showConfirmPassword ? (
                                <EyeOff className="w-5 h-5" />
                              ) : (
                                <Eye className="w-5 h-5" />
                              )}
                            </button>
                          </div>
                        </motion.div>

                        <motion.button
                          type="submit"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: 0.25 }}
                          whileHover={{ scale: changingPassword ? 1 : 1.02, y: changingPassword ? 0 : -2 }}
                          whileTap={{ scale: changingPassword ? 1 : 0.98 }}
                          disabled={changingPassword}
                          className="btn-gradient flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                          style={{ width: '100%', padding: '14px 24px', justifyContent: 'center' }}
                        >
                          <KeyRound className="w-5 h-5" />
                          {changingPassword ? t('common.loading') : t('settings.changePassword')}
                        </motion.button>
                      </form>
                    </div>

                    {/* 2FA Section */}
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.3 }}
                      className="relative"
                    >
                      <div className="relative rounded-2xl border p-6" style={{ background: 'var(--success-bg)', borderColor: 'var(--card-border)' }}>
                        <div className="flex items-start gap-4">
                          <div className="w-14 h-14 rounded-xl flex items-center justify-center" style={{ background: 'var(--success)' }}>
                            <ShieldCheck className="w-7 h-7" style={{ color: '#ffffff' }} />
                          </div>
                          <div className="flex-1">
                            <h3 className="text-xl font-bold mb-2" style={{ color: 'var(--text)' }}>
                              {t('settings.twoFactorAuth')}
                            </h3>
                            <p className="text-sm mb-4 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                              {t('settings.twoFactorAuthDesc')}
                            </p>
                            <button className="px-6 py-3 rounded-xl font-medium transition-all duration-300 hover:opacity-90" style={{ background: 'var(--success)', color: '#ffffff' }}>
                              {t('settings.twoFactorAuth')}
                            </button>
                          </div>
                        </div>
                      </div>
                    </motion.div>

                    {/* Active sessions + login history (AccountSecurity component) */}
                    {user?.id && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.35 }}
                      >
                        <AccountSecurity userId={user.id} />
                      </motion.div>
                    )}
                  </motion.div>
                )}

                {activeTab === 'notifications' && (
                  <motion.div
                    key="notifications"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-8"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--warning)' }}>
                        <BellRing className="w-6 h-6" style={{ color: '#ffffff' }} />
                      </div>
                      <div>
                        <h3 className="text-xl font-bold" style={{ color: 'var(--text)' }}>{t('settings.notifications')}</h3>
                        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('settings.notificationsDesc') || t('settings.notifications')}</p>
                      </div>
                    </div>

                    {notifSettings === null ? (
                      <div className="flex items-center justify-center py-12">
                        <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--text-muted)' }} />
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {/* Four distinct categories — fixes the earlier copy-paste bug where 3 toggles
                            all said "Системные оповещения" with the same description. */}
                        {([
                          {
                            key: 'email' as const,
                            icon: AtSign,
                            title: t('settings.emailNotifications'),
                            description: t('settings.emailNotificationsDesc'),
                            color: 'blue',
                          },
                          {
                            key: 'in_app' as const,
                            icon: Bell,
                            title: t('settings.inAppNotifications') || 'In-app notifications',
                            description: t('settings.inAppNotificationsDesc') || 'Show notifications in the bell icon',
                            color: 'slate',
                          },
                          {
                            key: 'security' as const,
                            icon: ShieldCheck,
                            title: t('settings.securityAlerts') || 'Security alerts',
                            description: t('settings.securityAlertsDesc') || 'Login from new device, parallel sessions, password changes',
                            color: 'green',
                          },
                          {
                            key: 'analyses' as const,
                            icon: BarChart3,
                            title: t('settings.analysisAlerts') || 'Analysis events',
                            description: t('settings.analysisAlertsDesc') || 'Bank statement analysis completed, failed, or cancelled',
                            color: 'red',
                          },
                        ]).map((item, index) => {
                          const Icon = item.icon;
                          const colorMap = {
                            blue: 'var(--accent)',
                            red: 'var(--danger)',
                            green: 'var(--success)',
                            slate: 'var(--text-muted)',
                          };
                          const checked = notifSettings[item.key];
                          return (
                            <motion.div
                              key={item.key}
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ delay: 0.05 * index }}
                              className="group backdrop-blur-xl rounded-xl transition-all duration-300 p-6"
                              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--card-border)' }}
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-start gap-4 flex-1">
                                  <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: colorMap[item.color as keyof typeof colorMap] }}>
                                    <Icon className="w-6 h-6" style={{ color: '#ffffff' }} />
                                  </div>
                                  <div>
                                    <p className="font-semibold mb-1" style={{ color: 'var(--text)' }}>{item.title}</p>
                                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                                      {item.description}
                                    </p>
                                  </div>
                                </div>
                                <label className="relative inline-flex items-center cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleNotifPref(item.key)}
                                    aria-label={item.title}
                                    className="sr-only peer"
                                  />
                                  <div
                                    className="w-14 h-7 rounded-full peer after:content-[''] after:absolute after:top-0.5 after:left-[4px] after:bg-white after:rounded-full after:h-6 after:w-6 after:transition-all shadow-inner"
                                    style={{
                                      background: checked ? 'var(--accent)' : 'var(--card-border)',
                                      // Manual peer-checked emulation since :checked is on the hidden input
                                    }}
                                  >
                                    <div
                                      style={{
                                        position: 'absolute',
                                        top: 2,
                                        left: checked ? 30 : 4,
                                        width: 24,
                                        height: 24,
                                        background: '#fff',
                                        borderRadius: '50%',
                                        transition: 'left 0.2s ease',
                                      }}
                                    />
                                  </div>
                                </label>
                              </div>
                            </motion.div>
                          );
                        })}
                      </div>
                    )}

                    <motion.button
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.3 }}
                      whileHover={{ scale: 1.02, y: -2 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleSaveNotifications}
                      disabled={notifSaving || notifSettings === null}
                      className="btn-gradient"
                      style={{ width: '100%', padding: '14px 24px', justifyContent: 'center', opacity: (notifSaving || notifSettings === null) ? 0.6 : 1 }}
                    >
                      {notifSaving ? (
                        <span className="flex items-center gap-2 justify-center">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          {t('common.save')}…
                        </span>
                      ) : (
                        t('common.save')
                      )}
                    </motion.button>
                  </motion.div>
                )}

              </AnimatePresence>
            </div>
        </div>
      </div>
    </div>
  );
};
