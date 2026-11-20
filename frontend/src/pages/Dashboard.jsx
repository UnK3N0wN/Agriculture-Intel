import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { api, fetchRecommendations, getApiError } from "../api.js";
import AuthedImage from "../components/AuthedImage.jsx";
import Icon from "../components/Icon.jsx";
import LocationPicker from "../components/LocationPicker.jsx";
import { CountUp, ScoreRing } from "../components/Meters.jsx";
import PageTransition from "../components/PageTransition.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useFarmLocation } from "../context/LocationContext.jsx";
import { cap, formatDate } from "../lib/utils.js";

const container = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
const rise = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function Dashboard() {
  const { user } = useAuth();
  const { location } = useFarmLocation();
  const [recs, setRecs] = useState({ loading: false, data: null, error: "" });
  const [history, setHistory] = useState({ loading: true, count: 0, items: [] });

  useEffect(() => {
    const controller = new AbortController();
    api
      .get("/scans/history/", { signal: controller.signal })
      .then(({ data }) => setHistory({ loading: false, count: data.count, items: data.results.slice(0, 3) }))
      .catch((err) => {
        if (err?.code !== "ERR_CANCELED") setHistory({ loading: false, count: 0, items: [] });
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!location) {
      setRecs({ loading: false, data: null, error: "" });
      return undefined;
    }
    const controller = new AbortController();
    setRecs((r) => ({ ...r, loading: true, error: "" }));
    fetchRecommendations({ lat: location.latitude, lon: location.longitude, limit: 50 }, controller.signal)
      .then((data) => setRecs({ loading: false, data, error: "" }))
      .catch((err) => {
        if (err?.code === "ERR_CANCELED") return;
        setRecs({ loading: false, data: null, error: getApiError(err).message });
      });
    return () => controller.abort();
  }, [location?.latitude, location?.longitude]); // eslint-disable-line react-hooks/exhaustive-deps

  const data = recs.data;
  const top = data ? data.results.slice(0, 3) : [];

  return (
    <PageTransition>
      <motion.div variants={container} initial="hidden" animate="show">
        <motion.header className="page-head" variants={rise}>
          <p className="eyebrow">{greeting()}</p>
          <h1>{user.username}, here&apos;s your farm at a glance</h1>
        </motion.header>

        <motion.div variants={rise}>
          <LocationPicker />
        </motion.div>

        <motion.div className="stats-grid" variants={rise}>
          <div className="card stat-tile">
            <span className="stat-label">Crops that fit now</span>
            <strong className="stat-value">{data ? <CountUp value={data.count} /> : "–"}</strong>
          </div>
          <div className="card stat-tile">
            <span className="stat-label">Best match</span>
            <strong className="stat-value stat-text">{top[0]?.name || "–"}</strong>
          </div>
          <div className="card stat-tile">
            <span className="stat-label">Season</span>
            <strong className="stat-value stat-text">{data ? data.season.name : "–"}</strong>
          </div>
          <div className="card stat-tile">
            <span className="stat-label">Scans so far</span>
            <strong className="stat-value">{history.loading ? "–" : <CountUp value={history.count} />}</strong>
          </div>
        </motion.div>

        <div className="grid-2">
          <motion.section className="card" variants={rise} aria-labelledby="top-crops">
            <div className="card-head">
              <h2 id="top-crops">Best crops right now</h2>
              <Link to="/crops" className="link-arrow">See all →</Link>
            </div>
            {!location && <p className="muted">Choose a location above to see recommendations.</p>}
            {recs.loading && <div className="skeleton skeleton-block" aria-label="Loading recommendations" />}
            {recs.error && <p className="form-error" role="alert">{recs.error}</p>}
            {data && (
              <>
                <p className="muted small">
                  {data.location.region} · {data.month_name} ·{" "}
                  {data.weather_used ? `${data.weather.avg_temp_c}°C average` : "season-based estimate"}
                </p>
                <ul className="mini-list">
                  {top.map((crop) => (
                    <li key={crop.slug}>
                      <ScoreRing value={crop.score} size={60} stroke={11} />
                      <div>
                        <strong>{crop.name}</strong>
                        <span className="muted small">
                          {cap(crop.label)} fit · sow {crop.sow_window}
                        </span>
                      </div>
                    </li>
                  ))}
                  {!top.length && <li className="muted">No crops match this location yet.</li>}
                </ul>
              </>
            )}
          </motion.section>

          <motion.section className="card" variants={rise} aria-labelledby="recent-scans">
            <div className="card-head">
              <h2 id="recent-scans">Recent scans</h2>
              <Link to="/history" className="link-arrow">History →</Link>
            </div>
            {!history.loading && !history.items.length && (
              <p className="muted">No scans yet. Photograph a leaf and we&apos;ll tell you what&apos;s wrong.</p>
            )}
            <ul className="mini-list">
              {history.items.map((scan) => (
                <li key={scan.id}>
                  <AuthedImage className="thumb" src={scan.image_url} alt="Scanned leaf" />
                  <div>
                    <strong>{scan.common_name || "Unidentified"}</strong>
                    <span className="muted small">
                      {cap(scan.health_status)} · {formatDate(scan.created_at)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </motion.section>
        </div>

        <motion.div className="grid-2" variants={rise}>
          <motion.div whileHover={{ y: -4 }} whileTap={{ scale: 0.99 }}>
            <Link to="/crops" className="action-card">
              <Icon name="leaf" size={28} />
              <div>
                <strong>Explore crops</strong>
                <span>Rank every crop for your location and month.</span>
              </div>
            </Link>
          </motion.div>
          <motion.div whileHover={{ y: -4 }} whileTap={{ scale: 0.99 }}>
            <Link to="/scan" className="action-card action-card-alt">
              <Icon name="camera" size={28} />
              <div>
                <strong>Scan a leaf</strong>
                <span>Upload a photo for a diagnosis and treatment plan.</span>
              </div>
            </Link>
          </motion.div>
        </motion.div>
      </motion.div>
    </PageTransition>
  );
}