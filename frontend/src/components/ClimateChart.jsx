import { motion, useReducedMotion } from "motion/react";
import { MONTHS } from "../lib/utils.js";

const W = 480;
const H = 150;
const PAD = 22;

export default function ClimateChart({ climate, month, place }) {
  const reduce = useReducedMotion();
  if (!climate || !climate.monthly?.length) return null;

  const slot = (W - PAD * 2) / 12;
  const chartHeight = H - 44;
  const maxRain = Math.max(...climate.monthly.map((m) => m.rain_mm), 1);
  const temps = climate.monthly.map((m) => m.temp_c);
  const tMin = Math.min(...temps) - 2;
  const tMax = Math.max(...temps) + 2;
  const x = (i) => PAD + slot * i + slot / 2;
  const yTemp = (t) => 14 + chartHeight * (1 - (t - tMin) / (tMax - tMin));
  const line = climate.monthly.map((m, i) => `${x(i)},${yTemp(m.temp_c)}`).join(" ");

  return (
    <figure className="climate-chart">
      <figcaption>
        Typical climate{place ? ` at ${place}` : ""}: rain (bars) and temperature (line), {climate.years}-year average
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Monthly rainfall and temperature chart">
        {climate.monthly.map((m, i) => {
          const h = Math.max(2, (m.rain_mm / maxRain) * chartHeight);
          return (
            <motion.rect
              key={m.month}
              className={`cc-bar ${m.month === month ? "is-selected" : ""}`}
              x={x(i) - slot * 0.34}
              y={H - 22 - h}
              width={slot * 0.68}
              height={h}
              rx="3"
              style={{ originY: 1, transformBox: "fill-box" }}
              initial={{ scaleY: reduce ? 1 : 0 }}
              animate={{ scaleY: 1 }}
              transition={{ delay: i * 0.04, duration: 0.5, ease: "easeOut" }}
            >
              <title>{`${MONTHS[i]}: ${m.rain_mm} mm rain, ${m.temp_c} °C`}</title>
            </motion.rect>
          );
        })}
        <motion.polyline
          className="cc-line"
          points={line}
          initial={{ pathLength: reduce ? 1 : 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: reduce ? 0 : 1.2, ease: "easeOut", delay: 0.3 }}
        />
        {MONTHS.map((name, i) => (
          <text key={name} className="cc-label" x={x(i)} y={H - 6}>
            {name.slice(0, 1)}
          </text>
        ))}
      </svg>
    </figure>
  );
}