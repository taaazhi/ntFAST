import { useState, useRef, useEffect } from 'react';
import { Home, LayoutDashboard, ScanSearch, SlidersHorizontal, LogOut, Moon, Sun, Languages, Users } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { useLanguage } from '../context/LanguageContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { LogoIcon } from './ui/LogoIcon';

const languages = [
  { code: 'ru', name: 'RU', flag: '🇷🇺' },
  { code: 'kk', name: 'KZ', flag: '🇰🇿' },
  { code: 'en', name: 'EN', flag: '🇬🇧' },
];

export const FloatingNav = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { language, setLanguage } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const menuItems = [
    { icon: Home, label: t('sidebar.home'), path: '/' },
    { icon: LayoutDashboard, label: t('sidebar.dashboard'), path: '/dashboard' },
    { icon: ScanSearch, label: t('sidebar.analyses'), path: '/analyses' },
    { icon: Users, label: t('sidebar.subjects'), path: '/subjects' },
  ];

  const currentLangIndex = languages.findIndex(l => l.code === language);
  const currentLang = currentLangIndex >= 0 ? languages[currentLangIndex] : languages[0];

  const cycleLanguage = () => {
    const nextIndex = (currentLangIndex + 1) % languages.length;
    setLanguage(languages[nextIndex].code);
  };

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) setUserMenuOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className="floating-nav">
      {/* Brand */}
      <div className="nav-brand" onClick={() => navigate('/')} style={{ display: 'flex', alignItems: 'center', padding: '0 4px' }}>
        <LogoIcon height={16} color="var(--accent)" />
      </div>

      <div className="nav-divider" />

      {/* Nav items */}
      {menuItems.map((item) => {
        const Icon = item.icon;
        const isActive = item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path);
        return (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`nav-item ${isActive ? 'active' : ''}`}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <Icon style={{ width: 15, height: 15 }} />
              {item.label}
            </span>
          </button>
        );
      })}

      <div className="nav-divider" />

      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        className="nav-item"
        title={t('settings.darkMode')}
        aria-label={t('settings.darkMode') || 'Toggle theme'}
      >
        {theme === 'dark' ? <Sun style={{ width: 15, height: 15 }} /> : <Moon style={{ width: 15, height: 15 }} />}
      </button>

      {/* Language switcher — single-click cycle */}
      <button
        onClick={cycleLanguage}
        className="nav-item"
        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
        title={t('common.switchLanguage', { next: languages[(currentLangIndex + 1) % languages.length].name })}
        aria-label={t('common.switchLanguage', { next: languages[(currentLangIndex + 1) % languages.length].name }) || 'Switch language'}
      >
        <Languages style={{ width: 14, height: 14 }} />
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={currentLang.code}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            transition={{ duration: 0.12 }}
            style={{ fontSize: 12, display: 'inline-block', minWidth: 18, textAlign: 'center' }}
          >
            {currentLang.name}
          </motion.span>
        </AnimatePresence>
      </button>

      <div className="nav-divider" />

      {/* User avatar */}
      <div className="relative" ref={userMenuRef}>
        <button
          onClick={() => setUserMenuOpen(!userMenuOpen)}
          className="nav-avatar"
          title={user?.full_name || t('common.user')}
        >
          {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
        </button>
        <AnimatePresence>
          {userMenuOpen && (
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="nav-dropdown"
              style={{ right: 0, minWidth: 200 }}
            >
              <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                  {user?.full_name || t('common.user')}
                </p>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {user?.email}
                </p>
              </div>
              <div style={{ padding: 6 }}>
                <button
                  onClick={() => { setUserMenuOpen(false); navigate('/settings'); }}
                  className="nav-dropdown-item"
                >
                  <SlidersHorizontal style={{ width: 14, height: 14 }} />
                  <span>{t('sidebar.settings')}</span>
                </button>
                <button
                  onClick={handleLogout}
                  className="nav-dropdown-item danger"
                >
                  <LogOut style={{ width: 14, height: 14 }} />
                  <span>{t('sidebar.logout')}</span>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </nav>
  );
};
