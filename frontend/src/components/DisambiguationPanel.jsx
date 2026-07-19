import { useState } from 'react';

function formatCurrency(n) {
  const value = parseFloat(n);
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(isNaN(value) ? 0 : value);
}

/**
 * DisambiguationPanel — rendered when a chat EDIT/DELETE prompt matched more
 * than one entry (ChatResponse.intent === 'CONFIRM_NEEDED'). The user picks
 * the entry they meant; that re-fires the original prompt with `confirm_id`
 * set, which resolves server-side as an explicit, unambiguous mutation.
 *
 * `candidates`: array of normalized entries ({ id, item, category, amount, date })
 * `onSelect(id)`: async — re-sends the prompt with confirm_id = id
 * `onCancel()`: dismisses the panel without mutating anything
 */
export default function DisambiguationPanel({ message, candidates = [], onSelect, onCancel }) {
  const [pendingId, setPendingId] = useState(null);

  async function handlePick(candidate) {
    if (pendingId != null) return;
    setPendingId(candidate.id);
    try {
      await onSelect(candidate.id);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="disambiguation-panel">
      <p className="query-result-message">{message}</p>
      <div className="disambiguation-list">
        {candidates.map((c) => (
          <button
            key={c.id}
            type="button"
            className="disambiguation-option"
            onClick={() => handlePick(c)}
            disabled={pendingId != null}
          >
            <span className="disambiguation-radio" aria-hidden="true">○</span>
            <span className="disambiguation-label">
              #{c.id} — {c.item} · {formatCurrency(c.amount)} · {c.date} · {c.category}
            </span>
            {pendingId === c.id && (
              <span className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5 }} />
            )}
          </button>
        ))}
      </div>
      <div className="disambiguation-actions">
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={onCancel}
          disabled={pendingId != null}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
