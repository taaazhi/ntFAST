/**
 * NotificationBell — bell icon with badge + dropdown panel.
 *
 * Place inside FloatingNav. Reads state from NotificationsContext.
 * - Badge shows unread count (capped at 99+)
 * - Dropdown shows last 50 notifications, newest first
 * - Each row: icon by kind/severity, title, body, relative time, delete button
 * - "Mark all read" + "Clear all" actions at top
 * - Closes on outside-click or Escape
 */
import { useState, useRef, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  Bell, BellOff, Check, CheckCheck, Trash2, X, ShieldAlert,
  LogIn, KeyRound, AlertTriangle, Info, CheckCircle, XCircle,
} from 'lucide-react';
import { useNotifications } from '../context/NotificationsContext';
import type { NotificationItem, NotificationKind } from '../services/api';

// Map notification kind → Lucide icon
function kindIcon(kind: NotificationKind) {
  switch (kind) {
    case 'analysis_completed': return CheckCircle;
    case 'analysis_failed': return XCircle;
    case 'analysis_cancelled': return X;
    case 'new_login': return LogIn;
    case 'parallel_session': return ShieldAlert;
    case 'password_changed': return KeyRound;
    case 'system_alert': return AlertTriangle;
    default: return Info;
  }
}

// Severity → tailwind color tokens
function severityColor(severity: string): string {
  switch (severity) {
    case 'success': return 'text-emerald-500';
    case 'warning': return 'text-amber-500';
    case 'error': return 'text-red-500';
    default: return 'text-blue-500';
  }
}

// Format "2 hours ago"-style relative time. Locale-aware via Intl.RelativeTimeFormat.
function formatRelative(iso: string, lang: string): string {
  const locale = lang === 'kk' ? 'kk-KZ' : lang === 'en' ? 'en-US' : 'ru-RU';
  const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
  const diffMs = date.getTime() - Date.now();
  const diffSec = Math.round(diffMs / 1000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
  const abs = Math.abs(diffSec);
  if (abs < 60) return rtf.format(diffSec, 'second');
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), 'minute');
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), 'hour');
  if (abs < 2592000) return rtf.format(Math.round(diffSec / 86400), 'day');
  return rtf.format(Math.round(diffSec / 2592000), 'month');
}

export const NotificationBell = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { items, unread, markAsRead, markAllRead, remove, clear } = useNotifications();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on Escape + outside-click
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  // Click row handler — mark read + navigate if the notification has a target
  const onClickRow = (n: NotificationItem) => {
    if (!n.is_read) void markAsRead(n.id);
    // Deep-link based on notification kind
    const analysisId = n.data?.analysis_id;
    if (analysisId && (n.kind === 'analysis_completed' || n.kind === 'analysis_failed' || n.kind === 'analysis_cancelled')) {
      setOpen(false);
      navigate(`/analyses?focus=${analysisId}`);
    } else if (n.kind === 'new_login' || n.kind === 'parallel_session') {
      setOpen(false);
      navigate('/settings');
    }
  };

  const badgeText = useMemo(() => unread > 99 ? '99+' : String(unread), [unread]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setOpen(o => !o)}
        className="nav-item"
        style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
        aria-label={t('notifications.title') || 'Notifications'}
        title={t('notifications.title') || 'Notifications'}
      >
        {unread > 0 ? <Bell style={{ width: 15, height: 15 }} /> : <BellOff style={{ width: 15, height: 15 }} />}
        {unread > 0 && (
          <span
            style={{
              position: 'absolute',
              top: -4,
              right: -6,
              minWidth: 16,
              height: 16,
              padding: '0 4px',
              borderRadius: 8,
              background: 'var(--danger)',
              color: '#fff',
              fontSize: 10,
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              lineHeight: 1,
            }}
          >
            {badgeText}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
            transition={{ duration: 0.15 }}
            className="nav-dropdown"
            style={{
              right: 0,
              minWidth: 380,
              maxWidth: 420,
              maxHeight: '70vh',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
            role="dialog"
            aria-label={t('notifications.title') || 'Notifications'}
          >
            {/* Header */}
            <div
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid var(--card-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                {t('notifications.title') || 'Notifications'}
                {unread > 0 && (
                  <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 }}>
                    {t('notifications.unreadCount', { count: unread }) || `${unread} unread`}
                  </span>
                )}
              </h3>
              <div style={{ display: 'flex', gap: 6 }}>
                {unread > 0 && (
                  <button
                    onClick={() => void markAllRead()}
                    title={t('notifications.markAllRead') || 'Mark all read'}
                    aria-label={t('notifications.markAllRead') || 'Mark all read'}
                    className="p-1.5 rounded-md hover:bg-[var(--bg-secondary)]"
                  >
                    <CheckCheck className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)' }} />
                  </button>
                )}
                {items.length > 0 && (
                  <button
                    onClick={() => void clear()}
                    title={t('notifications.clearAll') || 'Clear all'}
                    aria-label={t('notifications.clearAll') || 'Clear all'}
                    className="p-1.5 rounded-md hover:bg-[var(--bg-secondary)]"
                  >
                    <Trash2 className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)' }} />
                  </button>
                )}
              </div>
            </div>

            {/* List */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {items.length === 0 ? (
                <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <BellOff className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p style={{ fontSize: 13 }}>{t('notifications.empty') || 'No notifications yet'}</p>
                </div>
              ) : (
                items.map((n) => {
                  const Icon = kindIcon(n.kind);
                  const colorClass = severityColor(n.severity);
                  return (
                    <div
                      key={n.id}
                      onClick={() => onClickRow(n)}
                      style={{
                        padding: '12px 16px',
                        borderBottom: '1px solid var(--card-border)',
                        background: n.is_read ? 'transparent' : 'var(--accent-subtle)',
                        cursor: 'pointer',
                        display: 'flex',
                        gap: 10,
                        alignItems: 'flex-start',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-secondary)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = n.is_read ? 'transparent' : 'var(--accent-subtle)')}
                    >
                      {/* Icon */}
                      <Icon className={`w-4 h-4 ${colorClass} flex-shrink-0 mt-0.5`} />

                      {/* Content. Title/body from backend are i18n KEYS like
                          "notifications.kind.new_login.title" plus interpolation params in `data`.
                          For legacy notifications that still hold raw English text, i18next's
                          `defaultValue` fallback returns the original string unchanged. */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ fontSize: 13, fontWeight: n.is_read ? 400 : 600, color: 'var(--text)', marginBottom: 2 }}>
                          {t(n.title, { ...(n.data || {}), defaultValue: n.title })}
                        </p>
                        {n.body && (
                          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, lineHeight: 1.4 }}>
                            {t(n.body, { ...(n.data || {}), defaultValue: n.body })}
                          </p>
                        )}
                        <p style={{ fontSize: 11, color: 'var(--text-faint)' }}>
                          {formatRelative(n.created_at, i18n.language)}
                        </p>
                      </div>

                      {/* Actions */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {!n.is_read && (
                          <button
                            onClick={(e) => { e.stopPropagation(); void markAsRead(n.id); }}
                            title={t('notifications.markAsRead') || 'Mark as read'}
                            aria-label={t('notifications.markAsRead') || 'Mark as read'}
                            className="p-1 rounded hover:bg-[var(--card)]"
                          >
                            <Check className="w-3 h-3" style={{ color: 'var(--text-muted)' }} />
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); void remove(n.id); }}
                          title={t('notifications.delete') || 'Delete'}
                          aria-label={t('notifications.delete') || 'Delete'}
                          className="p-1 rounded hover:bg-[var(--card)]"
                        >
                          <X className="w-3 h-3" style={{ color: 'var(--text-muted)' }} />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
