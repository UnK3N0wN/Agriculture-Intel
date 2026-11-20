import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

const MESSAGES = [
  "Looking closely at the leaf…",
  "Checking colour and spot patterns…",
  "Comparing with known diseases and pests…",
  "Preparing treatment and prevention advice…",
];

export default function AnalyzingView({ previewUrl, phase, jobStatus, attempts }) {
  const reduce = useReducedMotion();
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % MESSAGES.length), 2600);
    return () => clearInterval(id);
  }, []);

  let message = MESSAGES[index];
  if (phase === "submitting") message = "Uploading your photo securely…";
  else if (jobStatus === "queued") message = "Waiting for a free analyst…";
  else if (attempts > 1) message = `The service was busy. Trying again (attempt ${attempts})…`;

  return (
    <div className="analyzing">
      <div className={`scan-frame ${reduce ? "is-static" : ""}`}>
        {previewUrl && <img src={previewUrl} alt="The leaf being analyzed" />}
        <span className="corner tl" />
        <span className="corner tr" />
        <span className="corner bl" />
        <span className="corner br" />
        {!reduce && (
          <motion.div
            className="scan-line"
            initial={{ top: "4%" }}
            animate={{ top: "96%" }}
            transition={{ duration: 1.8, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}
          />
        )}
      </div>

      <div className="analyzing-text">
        <AnimatePresence mode="wait" initial={false}>
          <motion.p key={message} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
            {message}
          </motion.p>
        </AnimatePresence>
        <div className="dots" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              animate={reduce ? { opacity: 1 } : { opacity: [0.25, 1, 0.25], scale: [0.8, 1.1, 0.8] }}
              transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
        </div>
        <p className="sr-only" role="status">
          Analyzing your photo. This usually takes a few seconds.
        </p>
        <p className="muted small">This usually takes 5 to 20 seconds.</p>
      </div>
    </div>
  );
}