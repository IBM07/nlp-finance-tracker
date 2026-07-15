/**
 * RecentActivityTable — shows the latest N finance entries.
 * `rows` prop: array of { id, item, amount, category, date }
 */
export default function RecentActivityTable({ rows = [], onViewAll }) {
  function getStatusBadge(amount) {
    return parseFloat(amount) >= 0
      ? <span className="badge badge-green">Revenue</span>
      : <span className="badge badge-amber">Expense</span>;
  }

  function formatAmount(amount) {
    const n = parseFloat(amount);
    const cls = n >= 0 ? 'amount-pos' : 'amount-neg';
    const formatted = new Intl.NumberFormat('en-US', {
      style: 'currency', currency: 'USD', signDisplay: 'always',
    }).format(n);
    return <span className={cls}>{formatted}</span>;
  }

  function formatDate(dateStr) {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
      });
    } catch { return dateStr; }
  }

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 24px 0' }}>
        <div className="chart-title">Recent Transactions</div>
        {onViewAll && (
          <button id="view-all-btn" className="form-link text-sm" onClick={onViewAll}>
            View All
          </button>
        )}
      </div>

      {rows.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📊</div>
          <div className="empty-state-title">No transactions yet</div>
          <div className="empty-state-desc">Add your first finance entry to see it here.</div>
        </div>
      ) : (
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead>
              <tr>
                <th>DATE</th>
                <th>DESCRIPTION</th>
                <th>CATEGORY</th>
                <th>STATUS</th>
                <th style={{ textAlign: 'right' }}>AMOUNT</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="text-sm text-muted">{formatDate(row.date)}</td>
                  <td style={{ fontWeight: 500 }}>{row.item}</td>
                  <td>
                    <span className="badge badge-gray">{row.category}</span>
                  </td>
                  <td>{getStatusBadge(row.amount)}</td>
                  <td style={{ textAlign: 'right' }}>{formatAmount(row.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
