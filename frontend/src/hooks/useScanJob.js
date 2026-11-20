import { useCallback, useEffect, useRef, useState } from "react";
import { api, getApiError } from "../api.js";

const POLL_MS = 3000;
const GIVE_UP_MS = 3 * 60 * 1000;
const MAX_POLL_FAILURES = 3;
const IDLE = { phase: "idle", taskId: null, jobStatus: null, attempts: 0, result: null, error: null };

export function useScanJob() {
  const [state, setState] = useState(IDLE);
  const runRef = useRef(0); // bumping this number "cancels" every older run
  const timerRef = useRef(null);
  const abortRef = useRef(null);

  const stop = useCallback(() => {
    runRef.current += 1;
    clearTimeout(timerRef.current);
    abortRef.current?.abort();
  }, []);

  useEffect(() => stop, [stop]); // cleanup when the page is left

  const reset = useCallback(() => {
    stop();
    setState(IDLE);
  }, [stop]);

  const submit = useCallback(
    async (file, cropHint) => {
      stop();
      const run = runRef.current;
      setState({ ...IDLE, phase: "submitting" });

      const form = new FormData();
      form.append("image", file);
      if (cropHint) form.append("crop_hint", cropHint);

      let task;
      try {
        const { data } = await api.post("/scans/", form, { timeout: 60000 });
        task = data;
      } catch (err) {
        if (runRef.current === run) setState({ ...IDLE, phase: "failed", error: getApiError(err) });
        return;
      }
      if (runRef.current !== run) return;
      setState({ ...IDLE, phase: "analyzing", taskId: task.task_id, jobStatus: task.status });

      const startedAt = Date.now();
      let failures = 0;

      const poll = async () => {
        if (runRef.current !== run) return;
        abortRef.current = new AbortController();
        let delay = POLL_MS;
        try {
          const { data } = await api.get(`/scans/status/${task.task_id}/`, {
            signal: abortRef.current.signal,
          });
          if (runRef.current !== run) return;
          failures = 0;

          if (data.status === "succeeded" && data.result) {
            setState({
              ...IDLE,
              phase: "done",
              taskId: task.task_id,
              jobStatus: data.status,
              attempts: data.attempts,
              result: data.result,
            });
            return;
          }
          if (data.status === "failed") {
            setState({
              ...IDLE,
              phase: "failed",
              taskId: task.task_id,
              error: {
                code: data.error?.code || "analysis_failed",
                message: data.error?.message || "We couldn't analyze this image. Please try again.",
                retryAfter: 0,
              },
            });
            return;
          }
          setState((s) => ({ ...s, jobStatus: data.status, attempts: data.attempts }));
        } catch (err) {
          if (err?.code === "ERR_CANCELED" || runRef.current !== run) return;
          const info = getApiError(err);
          failures += 1;
          if (info.status === 404 || failures >= MAX_POLL_FAILURES) {
            setState({ ...IDLE, phase: "failed", error: info });
            return;
          }
          if (info.retryAfter) delay = info.retryAfter * 1000;
        }

        if (Date.now() - startedAt > GIVE_UP_MS) {
          setState({
            ...IDLE,
            phase: "failed",
            error: {
              code: "timeout",
              message: "This is taking longer than usual. Your scan may still finish, so check History in a minute.",
              retryAfter: 0,
            },
          });
          return;
        }
        timerRef.current = setTimeout(poll, delay);
      };

      poll();
    },
    [stop]
  );

  return { ...state, submit, reset };
}