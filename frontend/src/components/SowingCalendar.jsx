import { motion } from "motion/react";
import { MONTHS } from "../lib/utils.js";

function inWindow(rule, month) {
  return rule.sow_start_month <= rule.sow_end_month
    ? month >= rule.sow_start_month && month <= rule.sow_end_month
    : month >= rule.sow_start_month || month <= rule.sow_end_month;
}

export default function SowingCalendar({ rules, climate, currentMonth }) {
  const applicable = rules.filter(
    (r) =>
      (r.hemisphere === climate.hemisphere || r.hemisphere === "ANY") &&
      (r.climate_zone === climate.climate_zone || r.climate_zone === "any")
  );
  if (!applicable.length) return null;

  const active = MONTHS.filter((_, i) => applicable.some((r) => inWindow(r, i + 1)));
  return (
    <section aria-label="Sowing calendar">
      <h3>Sowing calendar</h3>
      <div className="calendar" role="img" aria-label={`Usual sowing months: ${active.join(", ")}`}>
        {MONTHS.map((name, i) => {
          const month = i + 1;
          const on = applicable.some((r) => inWindow(r, month));
          return (
            <motion.div
              key={name}
              className={`cal-cell ${on ? "on" : ""} ${month === currentMonth ? "now" : ""}`}
              initial={{ scaleY: 0.2, opacity: 0 }}
              animate={{ scaleY: 1, opacity: 1 }}
              transition={{ delay: i * 0.03, type: "spring", stiffness: 300, damping: 20 }}
              title={name}
            >
              {name.slice(0, 1)}
            </motion.div>
          );
        })}
      </div>
      <p className="muted small">Highlighted months are the usual sowing window for your climate zone. The outlined month is now.</p>
    </section>
  );
}