import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  api,
  clearImageCache,
  isSessionInvalid,
  loginRequest,
  logoutRequest,
  refreshAccessToken,
  registerRequest,
  tokens,
} from "../api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | authed | anon

  // On page load: if a refresh token exists, quietly turn it into a session.
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!tokens.refresh) {
        setStatus("anon");
        return;
      }
      try {
        await refreshAccessToken();
        const { data } = await api.get("/auth/me/");
        if (!cancelled) {
          setUser(data);
          setStatus("authed");
        }
      } catch (err) {
        if (isSessionInvalid(err)) tokens.clear();
        if (!cancelled) {
          setUser(null);
          setStatus("anon");
        }
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  // api.js announces "your session is over" with this event.
  useEffect(() => {
    const onExpired = () => {
      clearImageCache();
      setUser(null);
      setStatus("anon");
    };
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  const login = useCallback(async (username, password) => {
    const data = await loginRequest(username, password);
    tokens.save({ access: data.access, refresh: data.refresh });
    setUser(data.user);
    setStatus("authed");
    return data.user;
  }, []);

  const register = useCallback(async (payload) => {
    const data = await registerRequest(payload);
    tokens.save({ access: data.access, refresh: data.refresh });
    setUser(data.user);
    setStatus("authed");
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    await logoutRequest();
    tokens.clear();
    clearImageCache();
    setUser(null);
    setStatus("anon");
  }, []);

  const updateMe = useCallback(async (patch) => {
    const { data } = await api.patch("/auth/me/", patch);
    setUser(data);
    return data;
  }, []);

  const value = useMemo(
    () => ({ user, status, login, register, logout, updateMe }),
    [user, status, login, register, logout, updateMe]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}