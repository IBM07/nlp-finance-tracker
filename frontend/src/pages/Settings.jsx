import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import AppShell from '../components/AppShell';
import apiClient from '../api/client';

export default function Settings() {
  const { user } = useAuth();
  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : '??';

  // Profile form state
  const [displayName, setDisplayName] = useState(user?.email?.split('@')[0] ?? '');
  const [email]         = useState(user?.email ?? '');
  const [profileSaved, setProfileSaved] = useState(false);

  // Preferences
  const [prefs, setPrefs] = useState({
    emailNotifications: true,
    weeklySummary: false,
  });

  // Security
  const [passwords, setPasswords]   = useState({ current: '', newPw: '', confirm: '' });
  const [pwError, setPwError]       = useState('');
  const [pwSuccess, setPwSuccess]   = useState('');
  const [pwLoading, setPwLoading]   = useState(false);

  function handleProfileSave(e) {
    e.preventDefault();
    setProfileSaved(true);
    setTimeout(() => setProfileSaved(false), 2500);
  }

  async function handlePasswordUpdate(e) {
    e.preventDefault();
    setPwError(''); setPwSuccess('');
    if (passwords.newPw.length < 8) { setPwError('New password must be at least 8 characters.'); return; }
    if (passwords.newPw !== passwords.confirm) { setPwError('Passwords do not match.'); return; }
    setPwLoading(true);
    try {
      await apiClient.post('/auth/change-password', {
        current_password: passwords.current,
        new_password: passwords.newPw,
      });
      setPwSuccess('Password updated successfully.');
      setPasswords({ current: '', newPw: '', confirm: '' });
    } catch (err) {
      setPwError(err.response?.data?.detail || 'Failed to update password.');
    } finally {
      setPwLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="topbar">
        <h1 style={{ fontSize: 16, fontWeight: 700, color: 'var(--gray-900)' }}>Settings</h1>
        <nav style={{ display: 'flex', gap: 24, marginLeft: 24 }}>
          {['Profile', 'Preferences', 'Security'].map((t) => (
            <span key={t} style={{ fontSize: 14, fontWeight: 500, color: t === 'Profile' ? 'var(--brand)' : 'var(--gray-500)', cursor: 'pointer', borderBottom: t === 'Profile' ? '2px solid var(--brand)' : 'none', paddingBottom: 2 }}>
              {t}
            </span>
          ))}
        </nav>
      </div>

      <div className="page-body">
        <h1 className="page-title">Account Settings</h1>
        <p className="page-sub">Manage your profile, preferences, and security settings.</p>

        <div className="settings-grid">
          {/* ── Profile card ── */}
          <div className="card">
            <div className="settings-section-title">Profile</div>
            <div className="settings-section-sub">Update your personal information and how others see you.</div>

            <div className="avatar-wrap">
              <div className="avatar-large">{initials}</div>
              <button id="change-avatar-btn" className="btn btn-ghost btn-sm">Change Avatar</button>
            </div>

            <form onSubmit={handleProfileSave}>
              <div className="settings-field">
                <label className="settings-label" htmlFor="settings-name">Display Name</label>
                <input
                  id="settings-name"
                  type="text"
                  className="settings-input"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>
              <div className="settings-field">
                <label className="settings-label" htmlFor="settings-email">Email Address</label>
                <input
                  id="settings-email"
                  type="email"
                  className="settings-input"
                  value={email}
                  readOnly
                  style={{ background: 'var(--gray-50)', color: 'var(--gray-400)', cursor: 'not-allowed' }}
                />
              </div>
              <button id="save-profile-btn" type="submit" className="btn btn-primary" style={{ width: 'auto', padding: '0 28px' }}>
                {profileSaved ? '✓ Saved' : 'Save Changes'}
              </button>
            </form>
          </div>

          {/* ── Right column ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Preferences */}
            <div className="card">
              <div className="settings-section-title" style={{ marginBottom: 4 }}>Preferences</div>
              <div style={{ fontSize: 13, color: 'var(--gray-400)', marginBottom: 16 }}>Customize your experience.</div>
              <div className="divider" style={{ margin: '0 0 4px' }} />

              {[
                { key: 'emailNotifications', label: 'Email Notifications', desc: 'Receive alerts via email.' },
                { key: 'weeklySummary',      label: 'Weekly Summary Report', desc: 'Get a digest of your activity.' },
              ].map(({ key, label, desc }) => (
                <div key={key} className="toggle-row">
                  <div className="toggle-info">
                    <div className="toggle-label">{label}</div>
                    <div className="toggle-desc">{desc}</div>
                  </div>
                  <label className="toggle" htmlFor={`toggle-${key}`}>
                    <input
                      id={`toggle-${key}`}
                      type="checkbox"
                      checked={prefs[key]}
                      onChange={() => setPrefs({ ...prefs, [key]: !prefs[key] })}
                    />
                    <span className="toggle-slider" />
                  </label>
                </div>
              ))}
            </div>

            {/* Security */}
            <div className="card">
              <div className="settings-section-title" style={{ marginBottom: 4 }}>Security</div>
              <div style={{ fontSize: 13, color: 'var(--gray-400)', marginBottom: 16 }}>Manage your password.</div>
              <div className="divider" style={{ margin: '0 0 16px' }} />

              <form onSubmit={handlePasswordUpdate}>
                {[
                  { id: 'current-pw', label: 'Current Password',  key: 'current' },
                  { id: 'new-pw',     label: 'New Password',       key: 'newPw' },
                  { id: 'confirm-pw', label: 'Confirm New Password', key: 'confirm' },
                ].map(({ id, label, key }) => (
                  <div key={key} className="settings-field">
                    <label className="settings-label" htmlFor={id}>{label}</label>
                    <input
                      id={id}
                      type="password"
                      className="settings-input"
                      value={passwords[key]}
                      onChange={(e) => setPasswords({ ...passwords, [key]: e.target.value })}
                      autoComplete="new-password"
                    />
                  </div>
                ))}

                {pwError   && <p className="form-error" style={{ marginBottom: 10 }}>{pwError}</p>}
                {pwSuccess && <p style={{ fontSize: 13, color: 'var(--green)', marginBottom: 10 }}>{pwSuccess}</p>}

                <button id="update-password-btn" type="submit" className="btn btn-ghost w-full" disabled={pwLoading}>
                  {pwLoading ? <span className="spinner spinner-dark" /> : 'Update Password'}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
