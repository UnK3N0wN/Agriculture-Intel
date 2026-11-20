import { useEffect, useState } from "react";
import { api, getApiError } from "../api.js";
import { useToast } from "../context/ToastContext.jsx";
import { MONTHS, cap } from "../lib/utils.js";
import Drawer from "./Drawer.jsx";
import Icon from "./Icon.jsx";
import SowingCalendar from "./SowingCalendar.jsx";
import { MeterBar, ScoreRing } from "./Meters.jsx";

const shortMonth = (n) => MONTHS[n - 1].slice(0, 3);

function CropDetail({ item, climate }) {
  const toast = useToast();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api
      .get(`/crops/${item.slug}/`, { signal: controller.signal })
      .then(({ data }) => setDetail(data))
      .catch((err) => {
        if (err?.code !== "ERR_CANCELED") setError(getApiError(err).message);
      });
    return () => controller.abort();
  }, [item.slug]);

  async function toggleBookmark() {
    if (!detail || busy) return;
    setBusy(true);
    try {
      if (detail.bookmarked) await api.delete(`/crops/${item.slug}/bookmark/`);
      else await api.post(`/crops/${item.slug}/bookmark/`, {});
      setDetail((d) => ({ ...d, bookmarked: !d.bookmarked }));
    } catch (err) {
      toast.push({ type: "error", title: "Couldn't update bookmark", message: getApiError(err).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="crop-detail">
      <header>
        <p className="eyebrow">
          {cap(item.category)} · {cap(item.water_need)} water need
        </p>
        <h2>{item.name}</h2>
        <p className={`provenance ${item.data?.verified ? "ok" : ""}`}>
          {item.data?.verified ? "Verified reference data" : `Reference data (${item.data?.source || "demo"}), not yet verified`}
        </p>
        {detail?.scientific_name && <p className="muted"><em>{detail.scientific_name}</em></p>}
      </header>

      <div className="score-hero">
        <ScoreRing value={item.score} size={120} stroke={9} caption="suitability" />
        <div>
          <strong className={`tone-${item.label === "excellent" ? "good" : item.label === "good" ? "ok" : item.label === "fair" ? "warn" : "bad"} label-text`}>
            {cap(item.label)} fit
          </strong>
          <p className="muted">
            {item.season_label} sowing window: {item.sow_window}
          </p>
        </div>
      </div>

      <section aria-label="Score breakdown">
        <h3>Score breakdown</h3>
        <MeterBar label="Season" value={item.components.season} />
        <MeterBar label="Temperature" value={item.components.temperature} />
        <MeterBar label="Rainfall" value={item.components.rainfall} />
      </section>

      <section aria-label="Why this score">
        <h3>Why this score</h3>
        <ul className="reasons">
          {item.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </section>

      {error && <p className="form-error" role="alert">{error}</p>}
      {!detail && !error && <div className="skeleton skeleton-block" aria-label="Loading details" />}
      {detail && (
        <>
          {detail.description && <p>{detail.description}</p>}
          <dl className="facts">
            <div><dt>Ideal temperature</dt><dd>{detail.temp_opt_min_c}–{detail.temp_opt_max_c} °C</dd></div>
            <div><dt>Tolerates</dt><dd>{detail.temp_min_c}–{detail.temp_max_c} °C</dd></div>
            <div><dt>Rain per month</dt><dd>{detail.rain_min_mm}–{detail.rain_max_mm} mm</dd></div>
            <div><dt>Growing time</dt><dd>{detail.growing_days_min}–{detail.growing_days_max} days</dd></div>
            {detail.soil_types.length > 0 && <div><dt>Soils</dt><dd>{detail.soil_types.join(", ")}</dd></div>}
          </dl>
          
          {detail.seasonal_rules.length > 0 && climate && (
            <SowingCalendar rules={detail.seasonal_rules} climate={climate} currentMonth={new Date().getMonth() + 1} />
          )}

          {detail.seasonal_rules.length > 0 && (
            <section aria-label="Sowing windows">
              <h3>Sowing windows</h3>
              <div className="table-wrap">
                <table className="rules-table">
                  <thead>
                    <tr><th>Season</th><th>Zone</th><th>Sow</th></tr>
                  </thead>
                  <tbody>
                    {detail.seasonal_rules.map((rule) => (
                      <tr key={`${rule.hemisphere}-${rule.climate_zone}-${rule.season_label}`}>
                        <td>{rule.season_label}</td>
                        <td>{cap(rule.climate_zone)} ({rule.hemisphere})</td>
                        <td>{shortMonth(rule.sow_start_month)}–{shortMonth(rule.sow_end_month)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <button type="button" className={`btn ${detail.bookmarked ? "btn-primary" : "btn-ghost"} btn-block`} onClick={toggleBookmark} disabled={busy} aria-pressed={detail.bookmarked}>
            <Icon name="bookmark" size={18} />
            {detail.bookmarked ? "Bookmarked" : "Bookmark this crop"}
          </button>
        </>
      )}
      <p className="fine-print">Sample crop data for learning. Check sowing dates with your local agricultural office before planting.</p>
    </article>
  );
}

export default function CropDrawer({ item, onClose, climate }) {
  // Keep showing the last crop while the drawer slides out.
  const [shown, setShown] = useState(item);
  useEffect(() => {
    if (item) setShown(item);
  }, [item]);

  return (
    <Drawer open={Boolean(item)} onClose={onClose} label={shown ? `${shown.name} details` : "Crop details"}>
      {shown && <CropDetail key={shown.slug} item={shown} climate={climate} />}
    </Drawer>
  );
}