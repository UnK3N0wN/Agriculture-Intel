import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Link } from "react-router-dom";
import { api, getApiError } from "../api.js";
import AuthedImage from "../components/AuthedImage.jsx";
import DiagnosisReport from "../components/DiagnosisReport.jsx";
import Drawer from "../components/Drawer.jsx";
import Icon from "../components/Icon.jsx";
import { ScoreRing } from "../components/Meters.jsx";
import PageTransition from "../components/PageTransition.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { cap, formatDate } from "../lib/utils.js";

const FILTERS = [
  { value: "", label: "All" },
  { value: "healthy", label: "Healthy" },
  { value: "unhealthy", label: "Needs attention" },
  { value: "unknown", label: "Unclear" },
];

export default function History() {
  const toast = useToast();
  const [state, setState] = useState({ items: [], count: 0, page: 1, hasMore: false, loading: true, loadingMore: false, error: "" });
  const [filter, setFilter] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api
      .get("/scans/history/", { params: { page: 1 }, signal: controller.signal })
      .then(({ data }) =>
        setState({ items: data.results, count: data.count, page: 1, hasMore: Boolean(data.next), loading: false, loadingMore: false, error: "" })
      )
      .catch((err) => {
        if (err?.code === "ERR_CANCELED") return;
        setState((s) => ({ ...s, loading: false, error: getApiError(err).message }));
      });
    return () => controller.abort();
  }, []);

  async function loadMore() {
    setState((s) => ({ ...s, loadingMore: true }));
    try {
      const nextPage = state.page + 1;
      const { data } = await api.get("/scans/history/", { params: { page: nextPage } });
      setState((s) => {
        const known = new Set(s.items.map((item) => item.id));
        return {
          ...s,
          items: [...s.items, ...data.results.filter((item) => !known.has(item.id))],
          page: nextPage,
          hasMore: Boolean(data.next),
          loadingMore: false,
        };
      });
    } catch (err) {
      setState((s) => ({ ...s, loadingMore: false }));
      toast.push({ type: "error", title: "Couldn't load more", message: getApiError(err).message });
    }
  }

  const visible = useMemo(
    () => (filter ? state.items.filter((item) => item.health_status === filter) : state.items),
    [state.items, filter]
  );
  const selected = state.items.find((item) => item.id === selectedId) || null;

  function closeDrawer() {
    setSelectedId(null);
    setConfirming(false);
  }

  async function handleDelete() {
    if (!selected || deleting) return;
    setDeleting(true);
    try {
      await api.delete(`/scans/history/${selected.id}/`);
      setState((s) => ({ ...s, items: s.items.filter((item) => item.id !== selected.id), count: s.count - 1 }));
      closeDrawer();
      toast.push({ type: "success", title: "Scan deleted", message: "The diagnosis and its photo were removed." });
    } catch (err) {
      toast.push({ type: "error", title: "Couldn't delete", message: getApiError(err).message });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <PageTransition>
      <header className="page-head">
        <p className="eyebrow">History</p>
        <h1>Your past scans</h1>
        <p className="lede">{state.loading ? "Loading…" : `${state.count} scan${state.count === 1 ? "" : "s"} saved. Only you can see them.`}</p>
      </header>

      <div className="chip-row" role="group" aria-label="Filter scans">
        {FILTERS.map((f) => (
          <motion.button key={f.value || "all"} type="button" className="chip" aria-pressed={filter === f.value} whileTap={{ scale: 0.94 }} onClick={() => setFilter(f.value)}>
            {f.label}
          </motion.button>
        ))}
      </div>

      {state.error && <p className="form-error" role="alert">{state.error}</p>}

      {state.loading && (
        <ul className="history-grid" aria-label="Loading scans">
          {Array.from({ length: 6 }, (_, i) => (
            <li key={i} className="history-card skeleton skeleton-card" />
          ))}
        </ul>
      )}

      {!state.loading && !state.error && !visible.length && (
        <div className="empty">
          <Icon name="camera" size={34} />
          <p>{state.items.length ? "No scans match this filter." : "You haven't scanned anything yet."}</p>
          {!state.items.length && <Link to="/scan" className="btn btn-primary">Scan your first leaf</Link>}
        </div>
      )}

      <motion.ul className="history-grid" layout>
        <AnimatePresence mode="popLayout" initial={false}>
          {visible.map((scan, index) => (
            <motion.li
              key={scan.id}
              layout
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0, transition: { delay: Math.min(index, 8) * 0.04 } }}
              exit={{ opacity: 0, scale: 0.9 }}
            >
              <motion.button type="button" className="history-card" onClick={() => setSelectedId(scan.id)} whileHover={{ y: -4 }} whileTap={{ scale: 0.98 }} aria-label={`${scan.common_name || "Scan"} from ${formatDate(scan.created_at)}. Open report`}>
                <AuthedImage className="history-thumb" src={scan.image_url} alt="" />
                <div className="history-info">
                  <span className={`badge badge-${scan.health_status}`}>{cap(scan.health_status)}</span>
                  <strong>{scan.common_name || "Unidentified"}</strong>
                  <span className="muted small">
                    {scan.crop_hint ? `${scan.crop_hint} · ` : ""}
                    {formatDate(scan.created_at)}
                  </span>
                </div>
                <ScoreRing value={Math.round(scan.confidence * 100)} size={48} stroke={12} />
              </motion.button>
            </motion.li>
          ))}
        </AnimatePresence>
      </motion.ul>

      {state.hasMore && (
        <div className="load-more">
          <button type="button" className="btn btn-ghost" onClick={loadMore} disabled={state.loadingMore}>
            {state.loadingMore ? "Loading…" : "Load more"}
          </button>
        </div>
      )}

      <Drawer open={Boolean(selected)} onClose={closeDrawer} label="Scan report">
        {selected && (
          <div>
            <DiagnosisReport key={selected.id} diagnosis={selected} split={false} />
            <div className="danger-zone">
              {!confirming ? (
                <button type="button" className="btn btn-ghost btn-block" onClick={() => setConfirming(true)}>
                  <Icon name="trash" size={18} />
                  Delete this scan
                </button>
              ) : (
                <div className="confirm-row" role="alert">
                  <p>Delete this scan and its photo permanently?</p>
                  <button type="button" className="btn btn-danger" onClick={handleDelete} disabled={deleting}>
                    {deleting ? "Deleting…" : "Yes, delete"}
                  </button>
                  <button type="button" className="btn btn-ghost" onClick={() => setConfirming(false)}>
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </PageTransition>
  );
}