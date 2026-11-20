import { motion } from "motion/react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Icon from "./Icon.jsx";

const LINKS = [
  { to: "/", label: "Dashboard", icon: "grid", end: true },
  { to: "/crops", label: "Crops", icon: "leaf" },
  { to: "/scan", label: "Scanner", icon: "camera" },
  { to: "/history", label: "History", icon: "clock" },
];

export default function Navbar() {
  const { user, status, logout } = useAuth();
  const navigate = useNavigate();
  if (status !== "authed" || !user) return null;

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <motion.header
      className="navbar"
      initial={{ y: -28, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      <div className="navbar-inner">
        <NavLink to="/" className="brand" aria-label="AgriIntel home">
          <span className="brand-mark">
            <Icon name="leaf" size={20} />
          </span>
          AgriIntel
        </NavLink>

        <nav className="nav-links" aria-label="Main">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className="nav-link">
              {({ isActive }) => (
                <>
                  {isActive && <motion.span layoutId="nav-pill" className="nav-pill" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
                  <span className="nav-label">
                    <Icon name={link.icon} size={17} />
                    {link.label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="nav-user">
          <span className="avatar" aria-hidden="true">
            {user.username.slice(0, 1).toUpperCase()}
          </span>
          <span className="nav-username">{user.username}</span>
          <button type="button" className="icon-btn" onClick={handleLogout} aria-label="Sign out">
            <Icon name="logout" size={18} />
          </button>
        </div>
      </div>
    </motion.header>
  );
}