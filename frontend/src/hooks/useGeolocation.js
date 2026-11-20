import { useCallback, useState } from "react";

export function useGeolocation() {
  const [state, setState] = useState({ status: "idle", coords: null, error: "" });

  const request = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setState({ status: "unsupported", coords: null, error: "This browser can't share your location." });
      return;
    }
    setState({ status: "locating", coords: null, error: "" });
    navigator.geolocation.getCurrentPosition(
      (position) =>
        setState({
          status: "granted",
          error: "",
          coords: {
            latitude: Number(position.coords.latitude.toFixed(4)),
            longitude: Number(position.coords.longitude.toFixed(4)),
          },
        }),
      (err) => {
        const denied = err.code === err.PERMISSION_DENIED;
        setState({
          status: denied ? "denied" : "error",
          coords: null,
          error: denied
            ? "Location permission was blocked. You can enter it manually below."
            : err.code === err.TIMEOUT
              ? "Finding your location took too long. Try again or enter it manually."
              : "We couldn't work out your location. Please enter it manually.",
        });
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 }
    );
  }, []);

  return { ...state, request };
}