import { motion } from "motion/react";

export default function DashboardHero({ username, location, data }) {
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const excellent = data ? data.results.filter((c) => c.score >= 80).length : 0;
  const top = data?.results?.[0];

  const headline = data
    ? `${data.month_name} at ${location.label}: ${data.season.name}`
    : "Find what grows best on your land";
  const lede = data
    ? excellent > 0
      ? `${excellent} crop${excellent === 1 ? "" : "s"} look excellent right now. Top pick: ${top?.name}.`
      : "No crop is an excellent fit this month. Here are the best available options."
    : "Set your location and we will rank every crop for your climate and the month.";

  return (
    <motion.section
      className="hero"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="hero-text">
        <p className="eyebrow">
          {greet}, {username}
        </p>
        <h1>{headline}</h1>
        <p className="lede">{lede}</p>
        {data && (
          <div className="hero-chips">
            <span className="pill">{data.location.region}</span>
            {data.weather_used && <span className="pill">🌡 {data.weather.avg_temp_c}°C now</span>}
            <span className="pill">Scored on {data.scoring_basis}</span>
          </div>
        )}
      </div>

      <motion.svg
        className="hero-sun"
        viewBox="0 0 100 100"
        aria-hidden="true"
        animate={{ rotate: 360 }}
        transition={{ duration: 80, repeat: Infinity, ease: "linear" }}
      >
        <circle cx="50" cy="50" r="18" fill="currentColor" />
        {Array.from({ length: 12 }, (_, i) => {
          const a = (i * 30 * Math.PI) / 180;
          return (
            <line
              key={i}
              x1={50 + 28 * Math.cos(a)}
              y1={50 + 28 * Math.sin(a)}
              x2={50 + 40 * Math.cos(a)}
              y2={50 + 40 * Math.sin(a)}
              stroke="currentColor"
              strokeWidth="4"
              strokeLinecap="round"
            />
          );
        })}
      </motion.svg>

      <svg className="hero-hills" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden="true">
        <path className="hill-back" d="M0 70 C 200 20, 400 20, 600 60 S 1000 100, 1200 40 L1200 120 L0 120 Z" />
        <path className="hill-mid" d="M0 90 C 250 50, 450 60, 650 85 S 1000 110, 1200 70 L1200 120 L0 120 Z" />
        <path className="hill-front" d="M0 108 C 300 84, 600 100, 900 96 S 1120 100, 1200 92 L1200 120 L0 120 Z" />
      </svg>
    </motion.section>
  );
}