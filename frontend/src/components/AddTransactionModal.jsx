import { useState, useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import apiClient from '../api/client';
import { CATEGORIES, PAYMENT_TYPES } from '../constants/finance';

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
 * AddTransactionModal — modal for adding or editing a finance entry.
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

  const dialogRef = useRef(null);
  const firstFieldRef = useRef(null);
  const previouslyFocusedRef = useRef(null);

  // Re-sync form contents whenever the modal opens or the edit target changes.
  useEffect(() => {
    if (!open) return;
    setError('');
    setForm(editEntry ? formFromEntry(editEntry, today) : emptyForm(today));
  }, [open, editEntry]);

  // Focus trap + Escape-to-close + focus restore on close.
  useEffect(() => {
    if (!open) return;
    previouslyFocusedRef.current = document.activeElement;
    const raf = requestAnimationFrame(() => firstFieldRef.current?.focus());

    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab' || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll(
        'input, select, button, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [open, onClose]);

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
      <div className="modal-backdrop" onClick={onClose} />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="modal-panel"
      >
        <div className="modal-header">
          <div>
            <h2 id="modal-title" className="modal-title">
              {isEdit ? 'Edit Transaction' : 'Add Transaction'}
            </h2>
            <p className="modal-sub">
              {isEdit ? 'Update the details of this entry.' : 'Record a new expense or revenue entry.'}
            </p>
          </div>
          <button
            id="modal-close"
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          {/* Type toggle */}
          <div className="modal-type-toggle">
            {['expense', 'revenue'].map((t) => (
              <button
                key={t}
                type="button"
                id={`type-${t}`}
                className={`modal-type-btn ${t} ${form.type === t ? 'active' : ''}`}
                onClick={() => handleChange('type', t)}
              >
                {t === 'expense' ? '↓ Expense' : '↑ Revenue'}
              </button>
            ))}
          </div>

          {/* Item name */}
          <div className="settings-field">
            <label className="settings-label" htmlFor="entry-purchased">Item / Description</label>
            <input
              ref={firstFieldRef}
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
          <div className="modal-row-2">
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
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Payment type (optional) */}
          <div className="settings-field">
            <label className="settings-label" htmlFor="entry-payment">
              Payment Method <span className="settings-label-optional">(optional)</span>
            </label>
            <select
              id="entry-payment"
              className="settings-input"
              value={form.payment_type}
              onChange={(e) => handleChange('payment_type', e.target.value)}
            >
              <option value="">Select method...</option>
              {PAYMENT_TYPES.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          {error && <p className="form-error modal-error">{error}</p>}

          {/* Actions */}
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button
              id="add-transaction-submit"
              type="submit"
              className="btn btn-primary"
              disabled={loading || !form.purchased.trim() || !form.amount || !form.date}
            >
              {loading ? <span className="spinner" /> : (isEdit ? 'Save Changes' : 'Add Transaction')}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
