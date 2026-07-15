import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AddTransactionModal from './AddTransactionModal';
import {
  BarChart2, LayoutDashboard, ArrowRightLeft,
  LineChart, FileText, Settings, LogOut, Plus,
} from 'lucide-react';

const NAV = [
  { label: 'Dashboard',    icon: LayoutDashboard, path: '/dashboard' },
  { label: 'Transactions', icon: ArrowRightLeft,  path: '/transactions' },
  { label: 'Analytics',    icon: LineChart,        path: '/analytics' },
  { label: 'Invoices',     icon: FileText,         path: '/invoices' },
  { label: 'Settings',     icon: Settings,         path: '/settings' },
];

export default function AppShell({ children, onTransactionAdded }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [modalOpen, setModalOpen] = useState(false);

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : '??';

  function handleTransactionSuccess(newEntry) {
    if (onTransactionAdded) onTransactionAdded(newEntry);
  }

  return (
    <div className="app-shell">
      {/* ── Add Transaction Modal ── */}
      <AddTransactionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={handleTransactionSuccess}
      />

      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">
            <BarChart2 size={16} color="white" />
          </div>
          <div className="sidebar-brand-text">
            <div className="sidebar-brand-name">InvoiceFlow</div>
            <div className="sidebar-brand-tag">Premium Finance</div>
          </div>
        </div>

        <button
          id="sidebar-new-invoice"
          className="sidebar-new-btn"
          onClick={() => setModalOpen(true)}
        >
          <Plus size={15} /> New Invoice
        </button>

        <nav className="sidebar-nav">
          {NAV.map(({ label, icon: Icon, path }) => (
            <button
              key={path}
              id={`nav-${label.toLowerCase()}`}
              className={`sidebar-nav-item ${pathname === path ? 'active' : ''}`}
              onClick={() => navigate(path)}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-avatar">{initials}</div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user?.email?.split('@')[0] ?? 'User'}</div>
              <div className="sidebar-user-email">{user?.email ?? ''}</div>
            </div>
            <button
              id="sidebar-logout"
              className="sidebar-logout"
              onClick={logout}
              title="Sign out"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Content area ── */}
      <div className="main-content">
        {children}
      </div>
    </div>
  );
}

