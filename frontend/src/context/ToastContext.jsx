import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import Icon from "../components/Icon.jsx";
import { formatDuration } from "../lib/utils.js";

const ToastContext = createContext(null);

function ToastItem({ toast, onClose }) {
  const lifetime = toast.retryAfter ? Math.min(toast.retryAfter, 300) : 5;
  const [left, setLeft] = useState(lifetime);

  useEffect(() => {
    const endsAt = Date.now() + lifetime * 1000;
    const id = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
      setLeft(remaining);
      if (remaining === 0) onClose(toast.id);
    }, 250);
    return () => clearInterval(id);
  }, [lifetime, onClose, toast.id]);

  const icon = toast.type === "success" ? "check" : "alert";
  return (
    <motion.div
      layout
      className={`toast toast-${toast.type}`}
      initial={{ opacity: 0, x: 48, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 48, scale: 0.95 }}
      transition={{ type: "spring", stiffness: 380, damping: 30 }}
    >
      <span className="toast-icon">
        <Icon name={icon} size={18} />
      </span>
      <div className="toast-body">
        <strong>{toast.title}</strong>
        {toast.message && <p>{toast.message}</p>}
        {toast.retryAfter > 0 && (
          <p className="toast-timer">
            Try again in <strong>{formatDuration(left)}</strong>
          </p>
        )}
      </div>
      <button type="button" className="icon-btn" onClick={() => onClose(toast.id)} aria-label="Dismiss notification">
        <Icon name="x" size={16} />
      </button>
      {toast.retryAfter > 0 && (
        <motion.div
          className="toast-bar"
          initial={{ scaleX: 1 }}
          animate={{ scaleX: 0 }}
          transition={{ duration: lifetime, ease: "linear" }}
        />
      )}
    </motion.div>
  );
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), []);

  const push = useCallback((toast) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((list) =>
      [...list.filter((t) => !toast.key || t.key !== toast.key), { id, type: "info", ...toast }].slice(-4)
    );
    return id;
  }, []);

  // Events fired from api.js
  useEffect(() => {
    const onRate = (event) => {
      const info = event.detail || {};
      push({
        key: "rate",
        type: "warning",
        title: info.code === "daily_cap_reached" ? "Daily limit reached" : "Slow down a little",
        message: info.message,
        retryAfter: info.retryAfter || 0,
      });
    };
    const onForbidden = (event) =>
      push({
        key: "forbidden",
        type: "error",
        title: "Not allowed",
        message: event.detail?.message || "You don't have permission to do that.",
      });
    const onNetwork = () =>
      push({
        key: "network",
        type: "error",
        title: "Can't reach the server",
        message: "Check your internet connection and try again.",
      });
    window.addEventListener("api:rate-limit", onRate);
    window.addEventListener("api:forbidden", onForbidden);
    window.addEventListener("api:network", onNetwork);
    return () => {
      window.removeEventListener("api:rate-limit", onRate);
      window.removeEventListener("api:forbidden", onForbidden);
      window.removeEventListener("api:network", onNetwork);
    };
  }, [push]);

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" role="region" aria-label="Notifications" aria-live="polite">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onClose={dismiss} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside <ToastProvider>");
  return context;
}