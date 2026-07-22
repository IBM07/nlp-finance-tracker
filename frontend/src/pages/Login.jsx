import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Mail, Lock, Eye, EyeOff, BarChart2 } from 'lucide-react';

export default function Login() {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ email: '', password: '' });
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const result = await login(form.email, form.password);
    if (result.success) {
      navigate('/dashboard', { replace: true });
    } else {
      setError(result.message);
    }
  }

  return (
    <div className="auth-layout">
      {/* ── Left panel ── */}
      <div className="auth-left">
        <div className="auth-brand">
          <div className="auth-brand-icon">
            <BarChart2 size={20} color="white" />
          </div>
          <span className="auth-brand-name">FinTrack</span>
        </div>

        <h1 className="auth-heading">Welcome back</h1>
        <p className="auth-sub">Enter your details below to continue.</p>

        <form onSubmit={handleSubmit} noValidate>
          {/* Email */}
          <div className="form-group">
            <label className="form-label" htmlFor="login-email">Email address</label>
            <div className="form-input-wrap">
              <span className="form-input-icon"><Mail size={16} /></span>
              <input
                id="login-email"
                type="email"
                className="form-input"
                placeholder="name@company.com"
                autoComplete="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
          </div>

          {/* Password */}
          <div className="form-group">
            <div className="form-label-row">
              <label className="form-label" htmlFor="login-password">Password</label>
              <span className="form-link">Forgot password?</span>
            </div>
            <div className="form-input-wrap">
              <span className="form-input-icon"><Lock size={16} /></span>
              <input
                id="login-password"
                type={showPass ? 'text' : 'password'}
                className="form-input"
                placeholder="••••••••"
                autoComplete="current-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
              <button
                type="button"
                className="form-input-action"
                onClick={() => setShowPass(!showPass)}
                aria-label={showPass ? 'Hide password' : 'Show password'}
              >
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && <p className="form-error" style={{ marginBottom: 14 }}>{error}</p>}

          <button id="login-submit" type="submit" className="btn btn-primary" disabled={isLoading}>
            {isLoading ? <span className="spinner" /> : 'Sign in'}
          </button>
        </form>

        <p className="auth-footer">
          Don't have an account?{' '}
          <Link to="/signup" className="form-link">Sign up for free</Link>
        </p>
      </div>

      {/* ── Right panel ── */}
      <div className="auth-right">
        <div className="auth-testimonial">
          <div className="auth-testimonial-quote">"</div>
          <p className="auth-testimonial-text">
            "FinTrack has completely transformed how we track our burn. It is the gold standard."
          </p>
          <div className="auth-testimonial-author">
            <div className="auth-testimonial-avatar">SC</div>
            <div>
              <div className="auth-testimonial-name">Sarah Chen</div>
              <div className="auth-testimonial-role">CFO at Orbit</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
