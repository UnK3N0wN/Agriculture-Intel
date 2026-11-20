export const MONTHS = Array.from({ length: 12 }, (_, i) =>
  new Date(2000, i, 1).toLocaleString("en", { month: "long" })
);

export const CATEGORIES = ["cereal", "pulse", "vegetable", "fruit", "oilseed", "fibre", "spice", "other"];

export function cap(text) {
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

export function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.ceil(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const mm = String(m).padStart(h ? 2 : 1, "0");
  const rr = String(r).padStart(2, "0");
  return h ? `${h}:${mm}:${rr}` : `${mm}:${rr}`;
}

export function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return "";
  }
}

// 0-100 score -> colour family. CSS classes "tone-good" etc. turn this into colours.
export function scoreTone(score) {
  if (score >= 80) return "good";
  if (score >= 60) return "ok";
  if (score >= 40) return "warn";
  return "bad";
}

export const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

export function validateImage(file) {
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) return "Please choose a JPEG, PNG or WebP photo.";
  if (file.size === 0) return "That file is empty.";
  if (file.size > MAX_IMAGE_BYTES) return "That photo is larger than 8 MB. Please choose a smaller one.";
  return "";
}