import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/**
 * Reusable confirmation dialog — replaces native window.confirm() for
 * destructive actions (delete, batch delete, irreversible operations).
 *
 * Closes on backdrop click, Escape key, or explicit Cancel/Confirm buttons.
 */
export interface ConfirmModalProps {
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
  /** Body text or any React node. */
  description?: React.ReactNode;
  /** Custom button labels. Defaults to translated common.cancel / common.confirmDelete. */
  confirmLabel?: string;
  cancelLabel?: string;
  /** Style the confirm button as destructive (red). Default: true. */
  danger?: boolean;
  /** Disable confirm button + show spinner-like state while parent processes. */
  loading?: boolean;
}

export default function ConfirmModal({
  isOpen,
  onCancel,
  onConfirm,
  title,
  description,
  confirmLabel,
  cancelLabel,
  danger = true,
  loading = false,
}: ConfirmModalProps) {
  const { t } = useTranslation();

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) onCancel();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onCancel, loading]);

  const confirmText = confirmLabel || t('common.confirm') || 'Confirm';
  const cancelText = cancelLabel || t('common.cancel') || 'Cancel';

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => !loading && onCancel()}
            className="fixed inset-0 backdrop-blur-sm z-50"
            style={{ background: 'rgba(0,0,0,0.5)' }}
            aria-hidden="true"
          />

          {/* Dialog */}
          <div className="fixed inset-0 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 16 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              onClick={(e) => e.stopPropagation()}
              className="rounded-2xl shadow-2xl max-w-md w-full overflow-hidden"
              style={{ background: 'var(--card)' }}
            >
              {/* Header */}
              <div
                className="flex items-start justify-between gap-4 p-6 border-b"
                style={{ borderColor: 'var(--card-border)' }}
              >
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  {danger && (
                    <div
                      className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                      style={{ background: 'var(--danger-bg)' }}
                    >
                      <AlertTriangle className="w-5 h-5" style={{ color: 'var(--danger)' }} />
                    </div>
                  )}
                  <h2
                    id="confirm-modal-title"
                    className="text-lg font-semibold pt-1.5"
                    style={{ color: 'var(--text)' }}
                  >
                    {title}
                  </h2>
                </div>
                <button
                  onClick={onCancel}
                  disabled={loading}
                  aria-label={cancelText}
                  className="p-1.5 rounded-lg transition-colors hover:bg-[var(--bg-secondary)] disabled:opacity-50"
                >
                  <X className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                </button>
              </div>

              {/* Body */}
              {description && (
                <div className="p-6" style={{ color: 'var(--text-secondary)' }}>
                  {description}
                </div>
              )}

              {/* Actions */}
              <div
                className="flex justify-end gap-2 px-6 py-4 border-t"
                style={{ borderColor: 'var(--card-border)', background: 'var(--bg-secondary)' }}
              >
                <button
                  onClick={onCancel}
                  disabled={loading}
                  className="px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
                  style={{
                    background: 'transparent',
                    color: 'var(--text)',
                    border: '1px solid var(--card-border)',
                  }}
                >
                  {cancelText}
                </button>
                <button
                  onClick={onConfirm}
                  disabled={loading}
                  className="px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
                  style={{
                    background: danger ? 'var(--danger)' : 'var(--accent)',
                    color: '#fff',
                  }}
                >
                  {loading ? `${confirmText}…` : confirmText}
                </button>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
