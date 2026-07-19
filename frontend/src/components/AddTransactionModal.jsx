import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import apiClient from '../api/client';

// Unified taxonomy (feature plan Decision 5) — must stay in sync with
// backend/app/schemas.py::CATEGORIES, the single source of truth.
const CATEGORIES = [
  'Food & Dining', 'Transport', 'Shopping', 'Entertainment',
  'Healthcare', 'Utilities', 'Housing', 'Business & Software',
  'Income', 'Other',
];

const PAYMENT_TYPES = ['Cash', 'Credit Card', 'Debit Card', 'UPI', 'Bank Transfer', 'Other'];

function emptyForm(today) {
  return {
    purchased: '',
    categorization: CATEGORIES[0],
    amount: '',
    date: today,
    payment_type: '',
    type: 'expense',   // 'expense' | 'revenue'  — controls amount sign
  };
}

// Builds form state from an entry that may use either the create_entry() key
// shape ({item, category}) or the NLP snapshot key shape ({purchased, categorization}).
function formFromEntry(entry, today) {
  const rawAmount = parseFloat(entry.amount);
  return {
    purchased: entry.item ?? entry.purchased ?? '',
    categorization: entry.category ?? entry.categorization ?? CATEGORIES[0],
    amount: String(Math.abs(rawAmount)),
    date: entry.date || today,
    payment_type: entry.payment_type || '',
    type: rawAmount < 0 ? 'expense' : 'revenue',
  };
}

/**
 * AddTransactionModal — slide-in modal for adding or editing a finance entry.
 * Props:
 *   open: boolean
 *   onClose: () => void
 *   onSuccess: (entry) => void   — called after successful create/update
 *   editEntry: object | null     — when set, the modal opens in edit mode,
 *                                  pre-filled from this entry, and submits
 *                                  via PUT /finance/entries/{editEntry.id}
 */
export default function AddTransactionModal({ open, onClose, onSuccess, editEntry = null }) {
  const today = new Date().toISOString().split('T')[0];
  const isEdit = Boolean(editEntry);

  const [form, setForm] = useState(() => emptyForm(today));
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  // Re-sync form contents whenever the modal opens or the edit target changes.
  useEffect(() => {
    if (!open) return;
    setError('');
    setForm(editEntry ? formFromEntry(editEntry, today) : emptyForm(today));
  }, [open, editEntry]);

  function handleChange(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    const rawAmount = parseFloat(form.amount);
    if (isNaN(rawAmount) || rawAmount <= 0) {
      setError('Amount must be a positive number.');
      return;
    }

    // Expenses are stored as negative, revenues as positive
    const finalAmount = form.type === 'expense' ? -Math.abs(rawAmount) : Math.abs(rawAmount);
    const payload = {
      purchased:      form.purchased.trim(),
      categorization: form.categorization,
      amount:         finalAmount,
      date:           form.date,
      payment_type:   form.payment_type || null,
    };

    setLoading(true);
    try {
      const { data } = isEdit
        ? await apiClient.put(`/finance/entries/${editEntry.id}`, payload)
        : await apiClient.post('/finance/entries', payload);
      onSuccess(data.data);
      if (!isEdit) setForm(emptyForm(today));
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail;
      if (Array.isArray(msg)) {
        setError(msg.map((e) => e.msg).join('; '));
      } else {
        setError(msg || `Failed to ${isEdit ? 'update' : 'add'} transaction. Please try again.`);
      }
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(17,24,39,.45)',
          backdropFilter: 'blur(4px)',
          zIndex: 1000,
          animation: 'fadeIn .15s ease',
        }}
      />

      {/* Modal panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        style={{
          position: 'fixed',
          top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'var(--white)',
          borderRadius: 'var(--radius-xl)',
          width: '100%', maxWidth: 480,
          padding: '32px',
          boxShadow: '0 24px 64px rgba(0,0,0,.18)',
          zIndex: 1001,
          animation: 'slideUp .2s ease',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div>
            <h2 id="modal-title" style={{ fontSize: 20, fontWeight: 800, color: 'var(--gray-900)', marginBottom: 4 }}>
              {isEdit ? 'Edit Transaction' : 'Add Transaction'}
            </h2>
            <p style={{ fontSize: 13, color: 'var(--gray-400)' }}>
              {isEdit ? 'Update the details of this entry.' : 'Record a new expense or revenue entry.'}
            </p>
          </div>
          <button
            id="modal-close"
            onClick={onClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--gray-400)', display: 'grid', placeItems: 'center',
              width: 32, height: 32, borderRadius: 8,
            }}
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          {/* Type toggle */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
            {['expense', 'revenue'].map((t) => (
              <button
                key={t}
                type="button"
                id={`type-${t}`}
                onClick={() => handleChange('type', t)}
                style={{
                  flex: 1, height: 38, borderRadius: 'var(--radius-sm)',
                  border: '1.5px solid',
                  borderColor: form.type === t
                    ? (t === 'expense' ? 'var(--red)' : 'var(--green)')
                    : 'var(--gray-200)',
                  background: form.type === t
                    ? (t === 'expense' ? 'var(--red-bg)' : 'var(--green-bg)')
                    : 'var(--white)',
                  color: form.type === t
                    ? (t === 'expense' ? 'var(--red)' : 'var(--green)')
                    : 'var(--gray-500)',
                  fontWeight: 600, fontSize: 13, cursor: 'pointer',
                  fontFamily: 'inherit', transition: 'var(--transition)',
                  textTransform: 'capitalize',
                }}
              >
                {t === 'expense' ? '↓ Expense' : '↑ Revenue'}
              </button>
            ))}
          </div>

          {/* Item name */}
          <div className="settings-field">
            <label className="settings-label" htmlFor="entry-purchased">Item / Description</label>
            <input
              id="entry-purchased"
              type="text"
              className="settings-input"
              placeholder="e.g. AWS Web Services"
              value={form.purchased}
              onChange={(e) => handleChange('purchased', e.target.value)}
              required
            />
          </div>

          {/* Amount + Date row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 0 }}>
            <div className="settings-field">
              <label className="settings-label" htmlFor="entry-amount">Amount</label>
              <input
                id="entry-amount"
                type="number"
                min="0.01"
                step="0.01"
                className="settings-input"
                placeholder="0.00"
                value={form.amount}
                onChange={(e) => handleChange('amount', e.target.value)}
                required
              />
            </div>
            <div className="settings-field">
              <label className="settings-label" htmlFor="entry-date">Date</label>
              <input
                id="entry-date"
                type="date"
                className="settings-input"
                value={form.date}
                onChange={(e) => handleChange('date', e.target.value)}
                required
              />
            </div>
          </div>

          {/* Category */}
          <div className="settings-field">
            <label className="settings-label" htmlFor="entry-category">Category</label>
            <select
              id="entry-category"
              className="settings-input"
              value={form.categorization}
              onChange={(e) => handleChange('categorization', e.target.value)}
              style={{ cursor: 'pointer' }}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Payment type (optional) */}
          <div className="settings-field">
            <label className="settings-label" htmlFor="entry-payment">Payment Method <span style={{ color: 'var(--gray-400)', fontWeight: 400 }}>(optional)</span></label>
            <select
              id="entry-payment"
              className="settings-input"
              value={form.payment_type}
              onChange={(e) => handleChange('payment_type', e.target.value)}
              style={{ cursor: 'pointer' }}
            >
              <option value="">Select method...</option>
              {PAYMENT_TYPES.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          {error && <p className="form-error" style={{ marginBottom: 14 }}>{error}</p>}

          {/* Actions */}
          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
              style={{ flex: 1 }}
            >
              Cancel
            </button>
            <button
              id="add-transaction-submit"
              type="submit"
              className="btn btn-primary"
              style={{ flex: 1 }}
              disabled={loading || !form.purchased.trim() || !form.amount || !form.date}
            >
              {loading ? <span className="spinner" /> : (isEdit ? 'Save Changes' : 'Add Transaction')}
            </button>
          </div>
        </form>
      </div>

      <style>{`
        @keyframes fadeIn  { from { opacity:0 } to { opacity:1 } }
        @keyframes slideUp { from { opacity:0; transform: translate(-50%,-48%) } to { opacity:1; transform: translate(-50%,-50%) } }
      `}</style>
    </>
  );
}
