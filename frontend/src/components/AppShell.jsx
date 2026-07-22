import { useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { ToastProvider } from '../context/ToastContext';
import { DataRefreshProvider, useDataRefresh } from '../context/DataRefreshContext';
import { ChatProvider } from '../context/ChatContext';
import AddTransactionModal from './AddTransactionModal';
import ChatInput from './ChatInput';
import {
  BarChart2, LayoutDashboard, ArrowRightLeft, LineChart,
  LogOut, Plus, Moon, Sun,
} from 'lucide-react';

const NAV = [
  { label: 'Dashboard',    icon: LayoutDashboard, path: '/dashboard' },
  { label: 'Transactions', icon: ArrowRightLeft,  path: '/transactions' },
  { label: 'Analytics',    icon: LineChart,        path: '/analytics' },
];

function AppShellInner() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { bumpRefresh } = useDataRefresh();
  const [modalOpen, setModalOpen] = useState(false);

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : '??';

  return (
    <div className="app-shell">
      <AddTransactionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => bumpRefresh()}
      />

      {/* ── Sidebar (desktop) ── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">
            <BarChart2 size={16} color="white" />
          </div>
          <div className="sidebar-brand-text">
            <div className="sidebar-brand-name">FinTrack</div>
            <div className="sidebar-brand-tag">Premium Finance</div>
          </div>
        </div>

        <button
          id="sidebar-add-transaction"
          className="sidebar-new-btn"
          onClick={() => setModalOpen(true)}
        >
          <Plus size={15} /> Add Transaction
        </button>

        <nav className="sidebar-nav">
          {NAV.map(({ label, icon: Icon, path }) => (
            <NavLink
              key={path}
              id={`nav-${label.toLowerCase()}`}
              to={path}
              className={({ isActive }) => `sidebar-nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button
            type="button"
            id="theme-toggle"
            className="sidebar-theme-toggle"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>

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

      {/* ── Bottom nav (mobile) ── */}
      <nav className="mobile-nav" aria-label="Primary">
        {NAV.map(({ label, icon: Icon, path }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <button
        type="button"
        className="mobile-fab"
        onClick={() => setModalOpen(true)}
        aria-label="Add transaction"
        title="Add transaction"
      >
        <Plus size={20} />
      </button>

      {/* ── Content area ── */}
      <div className="main-content">
        <div className="topbar">
          <div className="topbar-query">
            <ChatInput />
          </div>
          <div className="topbar-actions">
            <div className="topbar-avatar" title={user?.email}>{initials}</div>
          </div>
        </div>

        <div className="page-body">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

export default function AppShell() {
  return (
    <ToastProvider>
      <DataRefreshProvider>
        <ChatProvider>
          <AppShellInner />
        </ChatProvider>
      </DataRefreshProvider>
    </ToastProvider>
  );
}
