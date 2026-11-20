import { useState } from "react";
import { AnimatePresence, motion, useAnimationControls } from "motion/react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getApiError } from "../api.js";
import AuthLayout from "../components/AuthLayout.jsx";
import Icon from "../components/Icon.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useCountdown } from "../hooks/useCountdown.js";
import { formatDuration } from "../lib/utils.js";

const MAX_ATTEMPTS = 5; // matches LOGIN_MAX_ATTEMPTS on the server

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const routerLocation = useLocation();
  const from = routerLocation.state?.from?.pathname || "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [lockTotal, setLockTotal] = useState(900);
  const countdown = useCountdown();
  const controls = useAnimationControls();

  const locked = countdown.active;
  const showLocked = error?.code === "login_locked" && locked;
  const showError = error && error.code !== "login_locked";

  async function handleSubmit(event) {
    event.preventDefault();
    if (locked || busy) return;
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      const info = getApiError(err);
      setError(info);
      setPassword("");
      if (info.code === "login_locked") {
        const seconds = info.retryAfter || 900;
        setLockTotal(seconds);
        countdown.start(seconds);
      }
      if (info.status === 401 || info.status === 429) {
        controls.start({ x: [0, -12, 12, -9, 9, -5, 5, 0], transition: { duration: 0.5 } });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to see what to plant and how your crops are doing.">
      <motion.form className="auth-form" onSubmit={handleSubmit} animate={controls} noValidate>
        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            className={`input ${showError ? "is-invalid" : ""}`}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
            disabled={locked}
            aria-invalid={Boolean(showError)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            className={`input ${showError ? "is-invalid" : ""}`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            disabled={locked}
            aria-invalid={Boolean(showError)}
          />
        </div>

        <AnimatePresence mode="wait" initial={false}>
          {showLocked && (
            <motion.div
              key="locked"
              className="lock-panel"
              role="alert"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <Icon name="lock" size={22} />
              <div>
                <strong>Too many attempts</strong>
                <p>For your safety, sign-in is paused. Try again in:</p>
              </div>
              <span className="lock-time" aria-live="off">
                {formatDuration(countdown.remaining)}
              </span>
              <div className="lock-track" aria-hidden="true">
                <motion.div
                  className="lock-fill"
                  animate={{ scaleX: countdown.remaining / lockTotal }}
                  transition={{ duration: 0.25, ease: "linear" }}
                />
              </div>
            </motion.div>
          )}
          {showError && (
            <motion.div
              key="error"
              className="form-error"
              role="alert"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <p>{error.message}</p>
              {error.attemptsRemaining != null && (
                <div className="attempts" aria-label={`${error.attemptsRemaining} of ${MAX_ATTEMPTS} attempts left`}>
                  {Array.from({ length: MAX_ATTEMPTS }, (_, i) => (
                    <motion.span
                      key={i}
                      className={`dot ${i < error.attemptsRemaining ? "on" : ""}`}
                      initial={{ scale: 0.6 }}
                      animate={{ scale: i < error.attemptsRemaining ? 1 : 0.8 }}
                      transition={{ type: "spring", stiffness: 500, damping: 20, delay: i * 0.04 }}
                    />
                  ))}
                  <span>{error.attemptsRemaining} attempts left</span>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          type="submit"
          className="btn btn-primary btn-block"
          disabled={locked || busy || !username || !password}
          whileTap={{ scale: 0.97 }}
        >
          {locked ? `Locked · ${formatDuration(countdown.remaining)}` : busy ? "Signing in…" : "Sign in"}
        </motion.button>
        <p className="auth-switch">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </motion.form>
    </AuthLayout>
  );
}