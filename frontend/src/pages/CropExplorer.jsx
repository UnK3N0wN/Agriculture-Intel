import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { fetchRecommendations, getApiError } from "../api.js";
import CropDrawer from "../components/CropDrawer.jsx";
import Icon from "../components/Icon.jsx";
import LocationPicker from "../components/LocationPicker.jsx";
import ClimateChart from "../components/ClimateChart.jsx";
import CropIcon from "../components/CropIcon.jsx";
import { ScoreRing } from "../components/Meters.jsx";
import PageTransition from "../components/PageTransition.jsx";
import { useFarmLocation } from "../context/LocationContext.jsx";
import { CATEGORIES, MONTHS, cap, scoreTone } from "../lib/utils.js";

const grid = { hidden: {}, show: { transition: { staggerChildren: 0.05, delayChildren: 0.05 } } };
const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } } };

export default function CropExplorer() {
  const { location } = useFarmLocation();
  const currentMonth = new Date().getMonth() + 1;
  const [month, setMonth] = useState(currentMonth);
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const [state, setState] = useState({ loading: false, data: null, error: "", version: 0 });
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!location) return undefined;
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true, error: "" }));
    fetchRecommendations(
      { lat: location.latitude, lon: location.longitude, month, category, limit: 50 },
      controller.signal
    )
      .then((data) => setState((s) => ({ loading: false, data, error: "", version: s.version + 1 })))
      .catch((err) => {
        if (err?.code === "ERR_CANCELED") return;
        setState((s) => ({ ...s, loading: false, error: getApiError(err).message }));
      });
    return () => controller.abort();
  }, [location?.latitude, location?.longitude, month, category]); // eslint-disable-line react-hooks/exhaustive-deps

  const { data } = state;
  const results = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    return q ? data.results.filter((crop) => crop.name.toLowerCase().includes(q)) : data.results;
  }, [data, query]);

  return (
    <PageTransition>
      <header className="page-head">
        <p className="eyebrow">Crop Explorer</p>
        <h1>What should you plant?</h1>
        <p className="lede">Every crop is scored for your location, the month, and (for the current month) real weather.</p>
      </header>

      <LocationPicker />

      {location && (
        <>
          <div className="toolbar">
            <div className="field">
              <label htmlFor="month">Month</label>
              <select id="month" className="input" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
                {MONTHS.map((name, index) => (
                  <option key={name} value={index + 1}>
                    {name}{index + 1 === currentMonth ? " (now)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="field field-grow">
              <label htmlFor="crop-search">Search</label>
              <div className="input-icon">
                <Icon name="search" size={18} />
                <input id="crop-search" className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find a crop…" />
              </div>
            </div>
          </div>

          <div className="chip-row" role="group" aria-label="Filter by category">
            {["", ...CATEGORIES].map((value) => (
              <motion.button
                key={value || "all"}
                type="button"
                className="chip"
                aria-pressed={category === value}
                whileTap={{ scale: 0.94 }}
                onClick={() => setCategory(value)}
              >
                {value ? cap(value) : "All"}
              </motion.button>
            ))}
          </div>

          {data && (
            <motion.div className="season-banner" key={`${data.month}-${data.season.key}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <div>
                <strong>{data.location.region}</strong> · {data.month_name} · {data.season.name}
              </div>
              <div className="weather-chips">
                {data.weather_used ? (
                  <>
                    <span className="pill">🌡 {data.weather.avg_temp_c}°C average</span>
                    <span className="pill">🌧 ~{data.weather.avg_monthly_rain_mm} mm/month</span>
                  </>
                ) : (
                  <span className="pill">Scored on {data.scoring_basis}</span>
                )}
              </div>
            </motion.div>
          )}
          {data && <ClimateChart climate={data.climate} month={month} place={location.label} />}

          {state.error && <p className="form-error" role="alert">{state.error}</p>}

          {state.loading && !data && (
            <ul className="crop-grid" aria-label="Loading crops">
              {Array.from({ length: 6 }, (_, i) => (
                <li key={i} className="crop-card skeleton skeleton-card" />
              ))}
            </ul>
          )}

          {data && (
            <motion.ul
              key={state.version}
              className={`crop-grid ${state.loading ? "is-refreshing" : ""}`}
              variants={grid}
              initial="hidden"
              animate="show"
              aria-label="Recommended crops"
            >
              {results.map((crop) => (
                <motion.li key={crop.slug} variants={fadeUp}>
                  <motion.button
                    type="button"
                    className={`crop-card tone-${scoreTone(crop.score)}`}
                    onClick={() => setSelected(crop)}
                    whileHover={{ y: -5 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ type: "spring", stiffness: 400, damping: 28 }}
                    aria-label={`${crop.name}, suitability ${crop.score} out of 100. Open details`}
                  >
                    <div className="crop-card-top">
                      <CropIcon slug={crop.slug} category={crop.category} />
                      <div className="crop-card-title">
                        <h3>{crop.name}</h3>
                        <p className="muted small">
                          {cap(crop.category)} · {cap(crop.water_need)} water
                        </p>
                      </div>
                      <ScoreRing value={crop.score} size={60} stroke={11} />
                    </div>
                    <p className="crop-card-note">
                      Sow {crop.sow_window} · {crop.season_label}
                    </p>
                    <span className={`pill tone-${scoreTone(crop.score)}`}>{cap(crop.label)} fit</span>
                  </motion.button>
                </motion.li>
              ))}
              {!results.length && (
                <li className="empty">
                  <Icon name="leaf" size={32} />
                  <p>No crops match. Try another month, category or search.</p>
                  {data.not_applicable_count > 0 && (
                    <p className="muted small">{data.not_applicable_count} crops have no sowing rule for this climate.</p>
                  )}
                </li>
              )}
            </motion.ul>
          )}
        </>
      )}

      <CropDrawer item={selected} onClose={() => setSelected(null)} climate={data?.location} />
    </PageTransition>
  );
}