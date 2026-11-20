import { useEffect } from "react";
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { scoreTone } from "../lib/utils.js";

export function CountUp({ value, duration = 0.9 }) {
  const reduce = useReducedMotion();
  const motionValue = useMotionValue(reduce ? value : 0);
  const rounded = useTransform(motionValue, (v) => Math.round(v));

  useEffect(() => {
    if (reduce) {
      motionValue.set(value);
      return undefined;
    }
    const controls = animate(motionValue, value, { duration, ease: "easeOut" });
    return () => controls.stop();
  }, [value, reduce, duration, motionValue]);

  return <motion.span>{rounded}</motion.span>;
}

export function ScoreRing({ value, size = 96, stroke = 9, caption, tone }) {
  const reduce = useReducedMotion();
  const score = Math.max(0, Math.min(100, Math.round(value ?? 0)));
  const color = tone || scoreTone(score);
  const radius = 50 - stroke / 2;

  return (
    <div
      className={`ring tone-${color}`}
      style={{ width: size, height: size, "--ring": `${size}px` }}
      role="img"
      aria-label={`${caption || "Score"}: ${score} out of 100`}
    >
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle className="ring-track" cx="50" cy="50" r={radius} strokeWidth={stroke} fill="none" />
        <g transform="rotate(-90 50 50)">
          <motion.circle
            className="ring-fill"
            cx="50"
            cy="50"
            r={radius}
            strokeWidth={stroke}
            fill="none"
            strokeLinecap="round"
            style={{ opacity: score === 0 ? 0 : 1 }}
            initial={{ pathLength: reduce ? score / 100 : 0 }}
            animate={{ pathLength: score / 100 }}
            transition={{ duration: reduce ? 0 : 1, ease: "easeOut" }}
          />
        </g>
      </svg>
      <div className="ring-text">
        <strong>
          <CountUp value={score} />
        </strong>
        {caption && <span>{caption}</span>}
      </div>
    </div>
  );
}

export function MeterBar({ label, value }) {
  const reduce = useReducedMotion();
  const known = typeof value === "number";
  const tone = known ? scoreTone(value) : "none";

  return (
    <div className={`meter tone-${tone}`}>
      <div className="meter-head">
        <span>{label}</span>
        <span>{known ? `${value}%` : "No data"}</span>
      </div>
      <div
        className="meter-track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={known ? value : undefined}
        aria-valuetext={known ? `${value} percent` : "No data"}
      >
        <motion.div
          className="meter-fill"
          initial={{ width: reduce || !known ? `${known ? value : 0}%` : "0%" }}
          animate={{ width: `${known ? value : 0}%` }}
          transition={{ duration: reduce ? 0 : 0.8, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}