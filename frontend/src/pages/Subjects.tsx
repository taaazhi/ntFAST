import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Search, Plus, Edit2, Trash2, Inbox, Loader2, User, Building2, X,
} from 'lucide-react';
import { subjectsAPI } from '../services/api';
import type { Subject } from '../types';
import { EmptyState } from '../components/ui/EmptyState';
import ConfirmModal from '../components/ui/ConfirmModal';

type SubjectType = 'individual' | 'legal_entity' | 'account_owner';
type SubjectStatus = 'active' | 'suspended' | 'blocked';

interface FormState {
  name: string;
  iin_bin: string;
  type: SubjectType;
  risk_level: number;
  status: SubjectStatus;
  phone_number: string;
  email: string;
  address: string;
}

const blankForm = (): FormState => ({
  name: '',
  iin_bin: '',
  type: 'individual',
  risk_level: 0,
  status: 'active',
  phone_number: '',
  email: '',
  address: '',
});

export default function Subjects() {
  const { t } = useTranslation();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | SubjectStatus>('all');
  const [typeFilter, setTypeFilter] = useState<'all' | SubjectType>('all');

  // Modal state — null = closed, 'create' = new, { id } = edit existing
  const [modal, setModal] = useState<null | { mode: 'create' } | { mode: 'edit'; subject: Subject }>(null);
  const [form, setForm] = useState<FormState>(blankForm());
  const [saving, setSaving] = useState(false);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<Subject | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadSubjects = async () => {
    setLoading(true);
    try {
      const data = await subjectsAPI.getAll();
      setSubjects(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load subjects', err);
      toast.error(t('common.error') || 'Error loading subjects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSubjects();
  }, []);

  // Open create modal
  const openCreate = () => {
    setForm(blankForm());
    setModal({ mode: 'create' });
  };

  // Open edit modal pre-filled with subject's current values
  const openEdit = (subject: Subject) => {
    setForm({
      name: subject.name || '',
      iin_bin: subject.iin_bin || '',
      type: subject.type,
      risk_level: subject.risk_level,
      status: subject.status,
      phone_number: subject.phone_number || '',
      email: subject.email || '',
      address: subject.address || '',
    });
    setModal({ mode: 'edit', subject });
  };

  const closeModal = () => {
    if (saving) return;
    setModal(null);
  };

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.error(t('subjects.enterName') || 'Please enter a name');
      return;
    }
    if (form.iin_bin && !/^\d{12}$/.test(form.iin_bin)) {
      toast.error(t('subjects.enter12Digits') || 'IIN/BIN must be 12 digits');
      return;
    }
    setSaving(true);
    try {
      const payload: Partial<Subject> = {
        name: form.name.trim(),
        iin_bin: form.iin_bin.trim() || null,
        type: form.type,
        risk_level: form.risk_level,
        status: form.status,
        phone_number: form.phone_number.trim() || null,
        email: form.email.trim() || null,
        address: form.address.trim() || null,
      };
      if (modal?.mode === 'create') {
        const created = await subjectsAPI.create(payload);
        setSubjects(prev => [created, ...prev]);
        toast.success(t('subjects.createSuccess') || 'Subject created');
      } else if (modal?.mode === 'edit') {
        const updated = await subjectsAPI.update(modal.subject.id, payload);
        setSubjects(prev => prev.map(s => s.id === updated.id ? updated : s));
        toast.success(t('subjects.updateSuccess') || 'Subject updated');
      }
      setModal(null);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Save failed';
      toast.error(String(detail));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await subjectsAPI.delete(deleteTarget.id);
      setSubjects(prev => prev.filter(s => s.id !== deleteTarget.id));
      toast.success(t('subjects.deleteSuccess') || 'Subject deleted');
      setDeleteTarget(null);
    } catch (err: any) {
      toast.error(String(err?.response?.data?.detail || 'Delete failed'));
    } finally {
      setDeleting(false);
    }
  };

  // Apply client-side filters/search on top of full list
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return subjects.filter(s => {
      if (statusFilter !== 'all' && s.status !== statusFilter) return false;
      if (typeFilter !== 'all' && s.type !== typeFilter) return false;
      if (!needle) return true;
      return (
        s.name.toLowerCase().includes(needle) ||
        (s.iin_bin || '').includes(needle)
      );
    });
  }, [subjects, search, statusFilter, typeFilter]);

  const stats = useMemo(() => ({
    total: subjects.length,
    individuals: subjects.filter(s => s.type === 'individual').length,
    legal: subjects.filter(s => s.type === 'legal_entity').length,
    active: subjects.filter(s => s.status === 'active').length,
  }), [subjects]);

  return (
    <div className="px-8 pb-8 fade-in">
      {/* Header */}
      <div className="mb-8 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.03em', color: 'var(--text)' }}>
            {t('subjects.title')}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, marginTop: 6 }}>
            {t('subjects.subtitle')}
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-colors"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          <Plus className="w-4 h-4" />
          {t('subjects.addSubject') || 'Add subject'}
        </button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: t('subjects.totalSubjects'), value: stats.total },
          { label: t('subjects.individuals'), value: stats.individuals },
          { label: t('subjects.legalEntities'), value: stats.legal },
          { label: t('subjects.active'), value: stats.active },
        ].map(card => (
          <div key={String(card.label)} className="p-4 rounded-xl border" style={{ background: 'var(--card)', borderColor: 'var(--card-border)' }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{card.label}</p>
            <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text)' }}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="flex-1 min-w-[240px] relative">
          <Search style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', width: 16, height: 16, color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder={t('subjects.searchPlaceholder') || 'Search…'}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-3 py-2 rounded-lg border"
            style={{ background: 'var(--card)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as any)}
          className="px-3 py-2 rounded-lg border"
          style={{ background: 'var(--card)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
        >
          <option value="all">{t('subjects.allStatuses') || 'All statuses'}</option>
          <option value="active">{t('subjects.activeStatus') || 'Active'}</option>
          <option value="suspended">{t('subjects.suspended') || 'Suspended'}</option>
          <option value="blocked">{t('subjects.blocked') || 'Blocked'}</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as any)}
          className="px-3 py-2 rounded-lg border"
          style={{ background: 'var(--card)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
        >
          <option value="all">{t('subjects.allTypes') || 'All types'}</option>
          <option value="individual">{t('subjects.individual')}</option>
          <option value="legal_entity">{t('subjects.legalEntity')}</option>
        </select>
      </div>

      {/* Table */}
      <div className="glass-table">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>{t('subjects.name')}</th>
                <th className="hidden md:table-cell">{t('subjects.identifier')}</th>
                <th className="hidden md:table-cell">{t('subjects.type')}</th>
                <th>{t('subjects.riskLevel')}</th>
                <th className="hidden md:table-cell">{t('subjects.status')}</th>
                <th>{t('subjects.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ padding: '40px', textAlign: 'center' }}>
                    <Loader2 className="inline-block animate-spin" style={{ width: 24, height: 24, color: 'var(--text-muted)' }} />
                  </td>
                </tr>
              ) : filtered.map(s => (
                <tr key={s.id}>
                  <td>
                    <div className="flex items-center gap-2">
                      {s.type === 'individual' ? (
                        <User className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                      ) : (
                        <Building2 className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                      )}
                      <span style={{ fontWeight: 500, color: 'var(--text)' }}>{s.name}</span>
                    </div>
                  </td>
                  <td className="hidden md:table-cell" style={{ color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 13 }}>{s.iin_bin || '—'}</td>
                  <td className="hidden md:table-cell" style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                    {s.type === 'individual' ? t('subjects.individual') : s.type === 'legal_entity' ? t('subjects.legalEntity') : s.type}
                  </td>
                  <td>
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
                      s.risk_level >= 7 ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                      s.risk_level >= 4 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300' :
                      'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                    }`}>
                      {s.risk_level}
                    </span>
                  </td>
                  <td className="hidden md:table-cell" style={{ fontSize: 13 }}>
                    {s.status === 'active' ? t('subjects.activeStatus') : s.status === 'suspended' ? t('subjects.suspended') : t('subjects.blocked')}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openEdit(s)}
                        className="glass-action-btn"
                        style={{ padding: '6px 10px' }}
                        aria-label={t('subjects.edit') || 'Edit'}
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeleteTarget(s)}
                        className="glass-action-btn danger"
                        style={{ padding: '6px 10px' }}
                        aria-label={t('subjects.delete') || 'Delete'}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && filtered.length === 0 && (
            <EmptyState
              icon={Inbox}
              title={t('subjects.noSubjects') || 'No subjects'}
              description={t('subjects.noSubjectsDesc') || 'Create your first subject to get started'}
            />
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      <AnimatePresence>
        {modal && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 backdrop-blur-sm z-50"
              style={{ background: 'rgba(0,0,0,0.5)' }}
              onClick={closeModal}
            />
            <div className="fixed inset-0 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 16 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 16 }}
                onClick={(e) => e.stopPropagation()}
                className="rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden"
                style={{ background: 'var(--card)' }}
              >
                <div className="flex items-center justify-between p-6 border-b" style={{ borderColor: 'var(--card-border)' }}>
                  <h2 className="text-xl font-semibold" style={{ color: 'var(--text)' }}>
                    {modal.mode === 'create' ? t('subjects.createSubject') : t('subjects.editSubject') || 'Edit subject'}
                  </h2>
                  <button onClick={closeModal} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800" aria-label="Close">
                    <X className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                  </button>
                </div>

                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[70vh] overflow-y-auto">
                  <div className="md:col-span-2">
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>{t('subjects.name')} *</label>
                    <input
                      type="text" value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border"
                      style={{ background: 'var(--bg)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>{t('subjects.identifier')}</label>
                    <input
                      type="text" value={form.iin_bin} placeholder="123456789012" maxLength={12}
                      onChange={(e) => setForm({ ...form, iin_bin: e.target.value.replace(/\D/g, '') })}
                      className="w-full px-3 py-2 rounded-lg border font-mono"
                      style={{ background: 'var(--bg)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>{t('subjects.type')}</label>
                    <select
                      value={form.type}
                      onChange={(e) => setForm({ ...form, type: e.target.value as SubjectType })}
                      className="w-full px-3 py-2 rounded-lg border"
                      style={{ background: 'var(--bg)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                    >
                      <option value="individual">{t('subjects.individual')}</option>
                      <option value="legal_entity">{t('subjects.legalEntity')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>{t('subjects.riskLevel')} (0-10)</label>
                    <input
                      type="number" value={form.risk_level} min={0} max={10}
                      onChange={(e) => setForm({ ...form, risk_level: Math.max(0, Math.min(10, Number(e.target.value) || 0)) })}
                      className="w-full px-3 py-2 rounded-lg border"
                      style={{ background: 'var(--bg)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>{t('subjects.status')}</label>
                    <select
                      value={form.status}
                      onChange={(e) => setForm({ ...form, status: e.target.value as SubjectStatus })}
                      className="w-full px-3 py-2 rounded-lg border"
                      style={{ background: 'var(--bg)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                    >
                      <option value="active">{t('subjects.activeStatus')}</option>
                      <option value="suspended">{t('subjects.suspended')}</option>
                      <option value="blocked">{t('subjects.blocked')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Phone</label>
                    <input
                      type="text" value={form.phone_number}
                      onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border"
                      style={{ background: 'var(--bg)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Email</label>
                    <input
                      type="email" value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border"
                      style={{ background: 'var(--bg)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Address</label>
                    <input
                      type="text" value={form.address}
                      onChange={(e) => setForm({ ...form, address: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border"
                      style={{ background: 'var(--bg)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2 px-6 py-4 border-t" style={{ borderColor: 'var(--card-border)', background: 'var(--bg-secondary)' }}>
                  <button
                    onClick={closeModal}
                    disabled={saving}
                    className="px-4 py-2 rounded-lg font-medium disabled:opacity-50"
                    style={{ background: 'transparent', color: 'var(--text)', border: '1px solid var(--card-border)' }}
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    onClick={handleSubmit}
                    disabled={saving}
                    className="px-4 py-2 rounded-lg font-medium disabled:opacity-50"
                    style={{ background: 'var(--accent)', color: '#fff' }}
                  >
                    {saving ? (
                      <span className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />{t('common.save')}…</span>
                    ) : (
                      t('common.save')
                    )}
                  </button>
                </div>
              </motion.div>
            </div>
          </>
        )}
      </AnimatePresence>

      {/* Delete confirmation */}
      <ConfirmModal
        isOpen={deleteTarget !== null}
        loading={deleting}
        title={t('subjects.confirmDelete') || 'Delete subject?'}
        description={deleteTarget ? deleteTarget.name : undefined}
        confirmLabel={t('common.confirmDelete')}
        cancelLabel={t('common.cancel')}
        onCancel={() => !deleting && setDeleteTarget(null)}
        onConfirm={handleDelete}
      />
    </div>
  );
}
