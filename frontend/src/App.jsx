import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import Icon from "./components/Icon.jsx";
import Navbar from "./components/Navbar.jsx";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import { LocationProvider } from "./context/LocationContext.jsx";
import { ToastProvider } from "./context/ToastContext.jsx";
import CropExplorer from "./pages/CropExplorer.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import History from "./pages/History.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Scanner from "./pages/Scanner.jsx";

function Splash() {
  return (
    <div className="splash" role="status" aria-label="Loading">
      <motion.span className="brand-mark brand-mark-lg" animate={{ scale: [1, 1.12, 1] }} transition={{ duration: 1.4, repeat: Infinity }}>
        <Icon name="leaf" size={28} />
      </motion.span>
    </div>
  );
}

function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Splash />;
  if (status === "anon") return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

function PublicOnly({ children }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Splash />;
  if (status === "authed") return <Navigate to={location.state?.from?.pathname || "/"} replace />;
  return children;
}

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
        <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/crops" element={<CropExplorer />} />
          <Route path="/scan" element={<Scanner />} />
          <Route path="/history" element={<History />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    // reducedMotion="user": people who turn on "reduce motion" in their OS get no
    // movement animations (fades still work). This one line makes every animation respect that.
    <MotionConfig reducedMotion="user">
      <ToastProvider>
        <AuthProvider>
          <LocationProvider>
            <a href="#main" className="skip-link">Skip to content</a>
            <Navbar />
            <AnimatedRoutes />
          </LocationProvider>
        </AuthProvider>
      </ToastProvider>
    </MotionConfig>
  );
}