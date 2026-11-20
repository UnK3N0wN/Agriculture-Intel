import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { getApiError } from "../api.js";
import { useFarmLocation } from "../context/LocationContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useGeolocation } from "../hooks/useGeolocation.js";
import Icon from "./Icon.jsx";

const PRESETS = [
  { label: "Bengaluru, India", latitude: 12.9716, longitude: 77.5946 },
  { label: "Delhi, India", latitude: 28.6139, longitude: 77.209 },
  { label: "Pune, India", latitude: 18.5204, longitude: 73.8567 },
  { label: "Nairobi, Kenya", latitude: -1.2921, longitude: 36.8219 },
  { label: "Sydney, Australia", latitude: -33.8688, longitude: 151.2093 },
  { label: "Des Moines, USA", latitude: 41.5868, longitude: -93.625 },
];

function parseCoordinates(latText, lonText) {
  if (latText.trim() === "" || lonText.trim() === "") return { error: "Enter both latitude and longitude." };
  const latitude = Number(latText);
  const longitude = Number(lonText);
  if (Number.isNaN(latitude) || Number.isNaN(longitude)) return { error: "Latitude and longitude must be numbers." };
  if (latitude < -90 || latitude > 90) return { error: "Latitude must be between -90 and 90." };
  if (longitude < -180 || longitude > 180) return { error: "Longitude must be between -180 and 180." };
  return { latitude: Number(latitude.toFixed(4)), longitude: Number(longitude.toFixed(4)) };
}

export default function LocationPicker() {
  const { location, setLocation, saveToProfile, saving } = useFarmLocation();
  const toast = useToast();
  const geo = useGeolocation();
  const [open, setOpen] = useState(!location);
  const [label, setLabel] = useState("");
  const [latText, setLatText] = useState("");
  const [lonText, setLonText] = useState("");
  const [manualError, setManualError] = useState("");

  // Close the panel once a location exists.
  useEffect(() => {
    if (location) setOpen(false);
  }, [location]);

  // Browser location arrived.
  useEffect(() => {
    if (geo.status === "granted" && geo.coords) {
      setLocation({ ...geo.coords, label: "My current location", source: "gps" });
    }
  }, [geo.status, geo.coords, setLocation]);

  function submitManual(event) {
    event.preventDefault();
    const parsed = parseCoordinates(latText, lonText);
    if (parsed.error) {
      setManualError(parsed.error);
      return;
    }
    setManualError("");
    setLocation({
      latitude: parsed.latitude,
      longitude: parsed.longitude,
      label: label.trim() || "My farm",
      source: "manual",
    });
  }

  async function handleSave() {
    try {
      await saveToProfile();
      toast.push({ type: "success", title: "Location saved", message: "We'll use it next time you sign in." });
    } catch (err) {
      toast.push({ type: "error", title: "Couldn't save location", message: getApiError(err).message });
    }
  }

  return (
    <section className="card location-card" aria-label="Your location">
      <div className="location-summary">
        <span className="location-pin">
          <Icon name="pin" size={22} />
        </span>
        {location ? (
          <div className="location-text">
            <strong>{location.label}</strong>
            <span className="muted">
              {location.latitude.toFixed(3)}°, {location.longitude.toFixed(3)}°{" "}
              {location.saved ? "· saved to your profile" : ""}
            </span>
          </div>
        ) : (
          <div className="location-text">
            <strong>Where is your land?</strong>
            <span className="muted">We use your location to find crops that suit your climate and season.</span>
          </div>
        )}
        <div className="location-actions">
          {location && !location.saved && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleSave} disabled={saving}>
              {saving ? "Saving…" : "Save as my farm"}
            </button>
          )}
          {location && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
            >
              {open ? "Close" : "Change"}
            </button>
          )}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="panel"
            className="location-panel"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28 }}
          >
            <div className="location-panel-inner">
              <button
                type="button"
                className="btn btn-primary"
                onClick={geo.request}
                disabled={geo.status === "locating"}
              >
                <Icon name="pin" size={18} />
                {geo.status === "locating" ? "Finding you…" : "Use my current location"}
              </button>
              <p className="hint" aria-live="polite">
                {geo.error || "Your browser will ask for permission. Nothing is saved unless you choose to."}
              </p>

              <div className="divider">
                <span>or pick a place</span>
              </div>
              <div className="preset-row">
                {PRESETS.map((preset) => (
                  <motion.button
                    key={preset.label}
                    type="button"
                    className="chip"
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setLocation({ ...preset, source: "preset" })}
                  >
                    {preset.label}
                  </motion.button>
                ))}
              </div>

              <div className="divider">
                <span>or type coordinates</span>
              </div>
              <form className="coord-form" onSubmit={submitManual} noValidate>
                <div className="field">
                  <label htmlFor="loc-label">Name (optional)</label>
                  <input id="loc-label" className="input" value={label} maxLength={120} onChange={(e) => setLabel(e.target.value)} placeholder="North field" />
                </div>
                <div className="field">
                  <label htmlFor="loc-lat">Latitude</label>
                  <input id="loc-lat" className="input" inputMode="decimal" value={latText} onChange={(e) => setLatText(e.target.value)} placeholder="12.9716" />
                </div>
                <div className="field">
                  <label htmlFor="loc-lon">Longitude</label>
                  <input id="loc-lon" className="input" inputMode="decimal" value={lonText} onChange={(e) => setLonText(e.target.value)} placeholder="77.5946" />
                </div>
                <button type="submit" className="btn btn-ghost">
                  Use these
                </button>
              </form>
              {manualError && (
                <p className="field-error" role="alert">
                  {manualError}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}