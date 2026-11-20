import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "./AuthContext.jsx";

const LocationContext = createContext(null);

export function LocationProvider({ children }) {
  const { user, updateMe } = useAuth();
  const [location, setLocationState] = useState(null); // { latitude, longitude, label, source, saved }
  const [saving, setSaving] = useState(false);

  // Start from the location saved in the user's profile (if any).
  useEffect(() => {
    if (!user) {
      setLocationState(null);
      return;
    }
    const profile = user.profile;
    if (profile && profile.latitude != null && profile.longitude != null) {
      setLocationState(
        (current) =>
          current || {
            latitude: profile.latitude,
            longitude: profile.longitude,
            label: profile.location_label || "Saved location",
            source: "profile",
            saved: true,
          }
      );
    }
  }, [user]);

  const setLocation = useCallback((next) => setLocationState({ saved: false, ...next }), []);

  const saveToProfile = useCallback(async () => {
    if (!location) return;
    setSaving(true);
    try {
      await updateMe({
        profile: {
          location_label: (location.label || "").slice(0, 120),
          latitude: location.latitude,
          longitude: location.longitude,
        },
      });
      setLocationState((current) => (current ? { ...current, saved: true } : current));
    } finally {
      setSaving(false);
    }
  }, [location, updateMe]);

  const value = useMemo(
    () => ({ location, setLocation, saveToProfile, saving }),
    [location, setLocation, saveToProfile, saving]
  );
  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>;
}

export function useFarmLocation() {
  const context = useContext(LocationContext);
  if (!context) throw new Error("useFarmLocation must be used inside <LocationProvider>");
  return context;
}