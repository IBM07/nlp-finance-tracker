import { useState, useEffect, useCallback } from 'react';
import { Search, ChevronLeft, ChevronRight, Pencil, Trash2 } from 'lucide-react';
import apiClient from '../api/client';
import AddTransactionModal from '../components/AddTransactionModal';
import { useToast } from '../context/ToastContext';
import { useDataRefresh } from '../context/DataRefreshContext';
import { CATEGORIES } from '../constants/finance';
import { formatDate, formatSignedCurrency, formatCurrency } from '../utils/format';

const PAGE_SIZE = 15;

export default function Transactions() {
  const { pushToast } = useToast();
  const { refreshToken } = useDataRefresh();

  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [editingEntry, setEditingEntry] = useState(null);

  // Debounce free-text search so we're not firing a request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Any filter change starts back at page 1
  useEffect(() => { setPage(0); }, [category, debouncedSearch]);

  const fetchPage = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await apiClient.get('/finance/entries', {
        params: {
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
          category: category || undefined,
          search: debouncedSearch || undefined,
        },
      });
      setRows(data.data ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      console.error('Transactions fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [page, category, debouncedSearch]);

  useEffect(() => { fetchPage(); }, [fetchPage, refreshToken]);

  function handleEdit(row) {
    setEditingEntry(row);
  }

  function handleEditSuccess() {
    setEditingEntry(null);
    fetchPage();
  }

  // Manual inline delete: nothing is committed yet, so Undo can genuinely
  // cancel the write — the DELETE call only fires once the toast expires
  // untouched, matching the Dashboard/RecentActivityTable pattern.
  function handleDelete(row) {
    setRows((prev) => prev.filter((r) => r.id !== row.id));
    setTotal((t) => Math.max(0, t - 1));
    pushToast({
      message: `✦ Deleted "${row.item}" · ${formatCurrency(row.amount)}`,
      undoable: true,
      onUndo: () => { fetchPage(); },
      onExpire: async () => {
        await apiClient.delete(`/finance/entries/${row.id}`);
      },
    });
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const rangeStart = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const rangeEnd = Math.min(total, (page + 1) * PAGE_SIZE);

  return (
    <>
      <AddTransactionModal
        open={Boolean(editingEntry)}
        editEntry={editingEntry}
        onClose={() => setEditingEntry(null)}
        onSuccess={handleEditSuccess}
      />

      <div className="page-title">Transactions</div>
      <p className="page-sub">Every expense and revenue entry, searchable and filterable.</p>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="transactions-toolbar">
          <div className="transactions-search">
            <Search size={15} />
            <input
              type="text"
              placeholder="Search description..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search transactions"
            />
          </div>
          <select
            className="transactions-filter"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            aria-label="Filter by category"
          >
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {loading && rows.length === 0 ? (
          <div className="flex-center" style={{ height: 240 }}>
            <span className="spinner spinner-dark" style={{ width: 28, height: 28, borderWidth: 3 }} />
          </div>
        ) : rows.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <div className="empty-state-title">No matching transactions</div>
            <div className="empty-state-desc">Try a different search term or category.</div>
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>DATE</th>
                    <th>DESCRIPTION</th>
                    <th>CATEGORY</th>
                    <th>PAYMENT</th>
                    <th style={{ textAlign: 'right' }}>AMOUNT</th>
                    <th style={{ width: 72 }} />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="row-hover-actions">
                      <td className="text-sm text-muted">{formatDate(row.date)}</td>
                      <td style={{ fontWeight: 500 }}>{row.item}</td>
                      <td><span className="badge badge-gray">{row.category}</span></td>
                      <td className="text-sm text-muted">{row.payment_type || '—'}</td>
                      <td style={{ textAlign: 'right' }}>
                        <span className={parseFloat(row.amount) >= 0 ? 'amount-pos' : 'amount-neg'}>
                          {formatSignedCurrency(row.amount)}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="row-actions">
                          <button
                            type="button"
                            className="row-action-btn"
                            title="Edit transaction"
                            onClick={() => handleEdit(row)}
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            type="button"
                            className="row-action-btn row-action-danger"
                            title="Delete transaction"
                            onClick={() => handleDelete(row)}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="transactions-pagination">
              <span className="text-sm text-muted">
                {rangeStart}–{rangeEnd} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
