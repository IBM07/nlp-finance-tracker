import { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Mail, Lock, Eye, EyeOff, BarChart2 } from 'lucide-react';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(form) {
  const errs = {};
  if (!form.email) errs.email = 'Email is required.';
  else if (!EMAIL_RE.test(form.email)) errs.email = 'Enter a valid email address.';
  if (!form.password) errs.password = 'Password is required.';
  return errs;
}

export default function Login() {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [form, setForm] = useState({ email: '', password: '' });
  const [showPass, setShowPass] = useState(false);
  const [errors, setErrors] = useState({});

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate(form);
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setErrors({});

    const result = await login(form.email, form.password);
    if (result.success) {
      const redirectTo = location.state?.from?.pathname || '/dashboard';
      navigate(redirectTo, { replace: true, state: { justLoggedIn: true } });
    } else {
      setErrors({ api: result.message });
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
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? 'login-email-error' : undefined}
              />
            </div>
            {errors.email && <p id="login-email-error" className="form-error">{errors.email}</p>}
          </div>

          {/* Password */}
          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Password</label>
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
                aria-invalid={Boolean(errors.password)}
                aria-describedby={errors.password ? 'login-password-error' : undefined}
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
            {errors.password && <p id="login-password-error" className="form-error">{errors.password}</p>}
          </div>

          {errors.api && <p className="form-error" style={{ marginBottom: 14 }}>{errors.api}</p>}

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
