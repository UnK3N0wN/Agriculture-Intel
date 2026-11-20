import { useCallback, useEffect, useState } from "react";

// Counts down from a number of seconds. Uses the clock (not a counter), so it stays
// accurate even when the browser slows down a background tab.
export function useCountdown() {
  const [endsAt, setEndsAt] = useState(null);
  const [remaining, setRemaining] = useState(0);

  const start = useCallback((seconds) => {
    const safe = Math.max(1, Math.ceil(seconds));
    setEndsAt(Date.now() + safe * 1000);
    setRemaining(safe);
  }, []);

  useEffect(() => {
    if (!endsAt) return undefined;
    const tick = () => {
      const left = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
      setRemaining(left);
      if (left === 0) setEndsAt(null);
    };
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [endsAt]);

  return { remaining, start, active: remaining > 0 };
}