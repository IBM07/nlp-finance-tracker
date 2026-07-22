import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Mail, Lock, Eye, EyeOff, BarChart2 } from 'lucide-react';

export default function Signup() {
  const { signup, isLoading } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ email: '', password: '', confirmPassword: '' });
  const [showPass, setShowPass] = useState(false);
  const [errors, setErrors] = useState({});

  function validate() {
    const errs = {};
    if (!form.email) errs.email = 'Email is required.';
    if (form.password.length < 8) errs.password = 'Password must be at least 8 characters.';
    if (form.password !== form.confirmPassword) errs.confirmPassword = 'Passwords do not match.';
    return errs;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setErrors({});
    const result = await signup(form.email, form.password);
    if (result.success) {
      navigate('/dashboard', { replace: true });
    } else {
      setErrors({ api: result.message });
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-left">
        <div className="auth-brand">
          <div className="auth-brand-icon">
            <BarChart2 size={20} color="white" />
          </div>
          <span className="auth-brand-name">FinTrack</span>
        </div>

        <h1 className="auth-heading">Create an account</h1>
        <p className="auth-sub">Start tracking your finances with AI — free forever.</p>

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="signup-email">Email address</label>
            <div className="form-input-wrap">
              <span className="form-input-icon"><Mail size={16} /></span>
              <input
                id="signup-email"
                type="email"
                className="form-input"
                placeholder="name@company.com"
                autoComplete="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            {errors.email && <p className="form-error">{errors.email}</p>}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="signup-password">Password</label>
            <div className="form-input-wrap">
              <span className="form-input-icon"><Lock size={16} /></span>
              <input
                id="signup-password"
                type={showPass ? 'text' : 'password'}
                className="form-input"
                placeholder="Min. 8 characters"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
              <button type="button" className="form-input-action" onClick={() => setShowPass(!showPass)}>
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errors.password && <p className="form-error">{errors.password}</p>}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="signup-confirm">Confirm password</label>
            <div className="form-input-wrap">
              <span className="form-input-icon"><Lock size={16} /></span>
              <input
                id="signup-confirm"
                type={showPass ? 'text' : 'password'}
                className="form-input"
                placeholder="Repeat password"
                autoComplete="new-password"
                value={form.confirmPassword}
                onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })}
              />
            </div>
            {errors.confirmPassword && <p className="form-error">{errors.confirmPassword}</p>}
          </div>

          {errors.api && <p className="form-error" style={{ marginBottom: 14 }}>{errors.api}</p>}

          <button id="signup-submit" type="submit" className="btn btn-primary" disabled={isLoading}>
            {isLoading ? <span className="spinner" /> : 'Create account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{' '}
          <Link to="/login" className="form-link">Sign in</Link>
        </p>
      </div>

      <div className="auth-right">
        <div className="auth-testimonial">
          <div className="auth-testimonial-quote">"</div>
          <p className="auth-testimonial-text">
            "Finally a finance tool that actually understands what I'm asking. Ask it anything — it just works."
          </p>
          <div className="auth-testimonial-author">
            <div className="auth-testimonial-avatar">JR</div>
            <div>
              <div className="auth-testimonial-name">James Rivera</div>
              <div className="auth-testimonial-role">Founder at Launchpad</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
