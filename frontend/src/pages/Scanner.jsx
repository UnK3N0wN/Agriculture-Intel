import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Link } from "react-router-dom";
import AnalyzingView from "../components/AnalyzingView.jsx";
import DiagnosisReport from "../components/DiagnosisReport.jsx";
import Icon from "../components/Icon.jsx";
import PageTransition from "../components/PageTransition.jsx";
import ScannerZone from "../components/ScannerZone.jsx";
import { useCountdown } from "../hooks/useCountdown.js";
import { useScanJob } from "../hooks/useScanJob.js";
import { formatDuration } from "../lib/utils.js";

const HINT_RE = /^[\w ,.'()-]{0,100}$/;
const stage = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.15 } },
};

export default function Scanner() {
  const job = useScanJob();
  const countdown = useCountdown();
  const [file, setFile] = useState(null);
  const [hint, setHint] = useState("");
  const [localError, setLocalError] = useState("");

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl]
  );

  // When the server says "wait N seconds", start a visible countdown.
  useEffect(() => {
    if (job.error?.retryAfter) countdown.start(job.error.retryAfter);
  }, [job.error]); // eslint-disable-line react-hooks/exhaustive-deps

  const current =
    job.phase === "done" ? "result" : job.phase === "submitting" || job.phase === "analyzing" ? "analyzing" : "input";
  const hintOk = HINT_RE.test(hint);
  const canSubmit = Boolean(file) && hintOk && !countdown.active && current === "input";
  const errorMessage = localError || (job.phase === "failed" ? job.error?.message : "");

  function pick(next) {
    setLocalError("");
    setFile(next);
  }

  function startOver() {
    job.reset();
    setFile(null);
    setHint("");
    setLocalError("");
  }

  return (
    <PageTransition>
      <header className="page-head">
        <p className="eyebrow">Disease Scanner</p>
        <h1>Check a leaf</h1>
        <p className="lede">Upload one clear photo of an affected leaf. You&apos;ll get a likely diagnosis and what to do about it.</p>
      </header>

      <AnimatePresence mode="wait" initial={false}>
        {current === "input" && (
          <motion.section key="input" className="scanner-input" variants={stage} initial="initial" animate="animate" exit="exit">
            <ScannerZone file={file} previewUrl={previewUrl} onFile={pick} onClear={() => pick(null)} onReject={setLocalError} />

            <div className="card scanner-form">
              <div className="field">
                <label htmlFor="crop-hint">Crop name (optional)</label>
                <input
                  id="crop-hint"
                  className={`input ${hintOk ? "" : "is-invalid"}`}
                  value={hint}
                  maxLength={100}
                  onChange={(e) => setHint(e.target.value)}
                  placeholder="Tomato, rice, chilli…"
                />
                <p className="hint">Helps the analysis. Letters, numbers and basic punctuation only.</p>
                {!hintOk && <p className="field-error">Remove special characters from the crop name.</p>}
              </div>

              {errorMessage && (
                <motion.p className="form-error" role="alert" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
                  {errorMessage}
                </motion.p>
              )}

              <motion.button type="button" className="btn btn-primary btn-block" disabled={!canSubmit} onClick={() => job.submit(file, hint.trim())} whileTap={{ scale: 0.97 }}>
                <Icon name="search" size={18} />
                {countdown.active ? `Try again in ${formatDuration(countdown.remaining)}` : "Analyze photo"}
              </motion.button>
              <p className="fine-print">Photos are re-encoded and stripped of location data before they&apos;re stored privately.</p>
            </div>
          </motion.section>
        )}

        {current === "analyzing" && (
          <motion.section key="analyzing" variants={stage} initial="initial" animate="animate" exit="exit">
            <AnalyzingView previewUrl={previewUrl} phase={job.phase} jobStatus={job.jobStatus} attempts={job.attempts} />
          </motion.section>
        )}

        {current === "result" && job.result && (
          <motion.section key="result" variants={stage} initial="initial" animate="animate" exit="exit">
            <DiagnosisReport diagnosis={job.result} imageSrc={previewUrl} />
            <div className="report-actions">
              <button type="button" className="btn btn-primary" onClick={startOver}>
                <Icon name="camera" size={18} />
                Scan another leaf
              </button>
              <Link to="/history" className="btn btn-ghost">
                View history
              </Link>
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </PageTransition>
  );
}