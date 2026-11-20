import { useState } from "react";
import { motion } from "motion/react";
import { Link, useNavigate } from "react-router-dom";
import { getApiError } from "../api.js";
import AuthLayout from "../components/AuthLayout.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useCountdown } from "../hooks/useCountdown.js";
import { formatDuration } from "../lib/utils.js";

const USERNAME_RE = /^[A-Za-z0-9_.-]+$/;
const STRENGTH_LABELS = ["Too short", "Weak", "Okay", "Good", "Strong"];

function strength(password) {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) score += 1;
  return score;
}

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const countdown = useCountdown();

  const score = strength(form.password);
  const update = (field) => (event) => setForm((f) => ({ ...f, [field]: event.target.value }));

  function validate() {
    const found = {};
    if (form.username.trim().length < 3) found.username = "Use at least 3 characters.";
    else if (!USERNAME_RE.test(form.username.trim())) found.username = "Letters, numbers, dot, dash and underscore only.";
    if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) found.email = "Enter a valid email address.";
    if (form.password.length < 8) found.password = "Use at least 8 characters.";
    if (form.confirm !== form.password) found.confirm = "Passwords don't match.";
    return found;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (busy || countdown.active) return;
    const found = validate();
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      await register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
      });
      navigate("/", { replace: true });
    } catch (err) {
      const info = getApiError(err);
      setErrors(info.fields || {});
      if (!Object.keys(info.fields || {}).length) setFormError(info.message);
      if (info.status === 429 && info.retryAfter) countdown.start(info.retryAfter);
    } finally {
      setBusy(false);
    }
  }

  const fieldProps = (name) => ({
    className: `input ${errors[name] ? "is-invalid" : ""}`,
    "aria-invalid": Boolean(errors[name]),
    "aria-describedby": errors[name] ? `${name}-error` : undefined,
  });

  return (
    <AuthLayout title="Create your account" subtitle="It takes under a minute.">
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="reg-username">Username</label>
          <input id="reg-username" value={form.username} onChange={update("username")} autoComplete="username" autoFocus {...fieldProps("username")} />
          {errors.username && <p id="username-error" className="field-error">{errors.username}</p>}
        </div>
        <div className="field">
          <label htmlFor="reg-email">Email</label>
          <input id="reg-email" type="email" value={form.email} onChange={update("email")} autoComplete="email" {...fieldProps("email")} />
          {errors.email && <p id="email-error" className="field-error">{errors.email}</p>}
        </div>
        <div className="field">
          <label htmlFor="reg-password">Password</label>
          <input id="reg-password" type="password" value={form.password} onChange={update("password")} autoComplete="new-password" {...fieldProps("password")} />
          <div className="strength" aria-hidden="true">
            <motion.div
              className={`strength-fill s${score}`}
              initial={false}
              animate={{ width: `${(score / 4) * 100}%` }}
              transition={{ type: "spring", stiffness: 260, damping: 28 }}
            />
          </div>
          <p className="hint">{form.password ? STRENGTH_LABELS[score] : "At least 8 characters. Longer is stronger."}</p>
          {errors.password && <p id="password-error" className="field-error">{errors.password}</p>}
        </div>
        <div className="field">
          <label htmlFor="reg-confirm">Confirm password</label>
          <input id="reg-confirm" type="password" value={form.confirm} onChange={update("confirm")} autoComplete="new-password" {...fieldProps("confirm")} />
          {errors.confirm && <p id="confirm-error" className="field-error">{errors.confirm}</p>}
        </div>

        {formError && (
          <p className="form-error" role="alert">
            {formError}
          </p>
        )}
        <motion.button type="submit" className="btn btn-primary btn-block" disabled={busy || countdown.active} whileTap={{ scale: 0.97 }}>
          {countdown.active ? `Try again in ${formatDuration(countdown.remaining)}` : busy ? "Creating account…" : "Create account"}
        </motion.button>
        <p className="auth-switch">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  );
}