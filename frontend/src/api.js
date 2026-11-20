import axios from "axios";

const API_ROOT = `${import.meta.env.VITE_API_BASE_URL || ""}/api`;
const REFRESH_KEY = "agri.refresh";

// The short-lived access token lives only in memory. The refresh token is kept in
// localStorage so a page reload can sign you back in.
let accessToken = null;

export const tokens = {
  get access() {
    return accessToken;
  },
  get refresh() {
    try {
      return localStorage.getItem(REFRESH_KEY);
    } catch {
      return null;
    }
  },
  save({ access, refresh }) {
    if (access) accessToken = access;
    if (refresh) {
      try {
        localStorage.setItem(REFRESH_KEY, refresh);
      } catch {
        /* storage blocked: the session lasts until reload */
      }
    }
  },
  clear() {
    accessToken = null;
    try {
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      /* ignore */
    }
  },
};

// api.js lives outside React, so it talks to the UI with browser events.
const emit = (name, detail) => window.dispatchEvent(new CustomEvent(name, { detail }));

const bare = axios.create({ baseURL: API_ROOT, timeout: 20000 }); // no interceptors (used for refresh)
export const api = axios.create({ baseURL: API_ROOT, timeout: 30000 });

// ------------------------------------------------------------------ errors
const FALLBACK = {
  400: "That didn't look right. Please check and try again.",
  401: "Please sign in again.",
  403: "You don't have permission to do that.",
  404: "We couldn't find that.",
  413: "That file is too large.",
  429: "Too many requests. Please wait a moment.",
};

function fallbackMessage(status) {
  if (FALLBACK[status]) return FALLBACK[status];
  return status >= 500
    ? "Something went wrong on our side. Please try again."
    : "Something went wrong. Please try again.";
}

const NON_FIELD_KEYS = ["code", "detail", "attempts_remaining", "retry_after_seconds"];

export function buildApiError(response) {
  const data = response.data && typeof response.data === "object" ? response.data : {};
  const headerWait = Number(response.headers?.["retry-after"]);
  const retryAfter =
    Number(data.retry_after_seconds) || (Number.isFinite(headerWait) && headerWait > 0 ? headerWait : 0);

  let message = typeof data.detail === "string" ? data.detail : "";
  const fields = {};
  for (const [key, value] of Object.entries(data)) {
    if (NON_FIELD_KEYS.includes(key)) continue;
    const text = Array.isArray(value) ? value.join(" ") : typeof value === "string" ? value : "";
    if (text) fields[key] = text;
  }
  if (!message) message = Object.values(fields)[0] || fallbackMessage(response.status);

  return {
    status: response.status,
    code: data.code || `http_${response.status}`,
    message,
    retryAfter,
    attemptsRemaining: typeof data.attempts_remaining === "number" ? data.attempts_remaining : null,
    fields,
  };
}

export function getApiError(error) {
  if (error?.apiError) return error.apiError;
  return {
    status: 0,
    code: "unknown",
    message: error?.message || "Something went wrong. Please try again.",
    retryAfter: 0,
    attemptsRemaining: null,
    fields: {},
  };
}

// True when the server (not just the network) says this login session is finished.
export function isSessionInvalid(error) {
  const status = error?.response?.status;
  return Boolean(error?.noSession) || status === 400 || status === 401;
}

// ------------------------------------------------------- silent token refresh
// One shared promise = the "request queue": every request that gets a 401 while a
// refresh is running waits for that same refresh, then replays with the new token.
let refreshPromise = null;

export function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refresh = tokens.refresh;
      if (!refresh) throw Object.assign(new Error("No session"), { noSession: true });
      const { data } = await bare.post("/auth/refresh/", { refresh });
      tokens.save({ access: data.access, refresh: data.refresh || refresh });
      return data.access;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

api.interceptors.request.use((config) => {
  if (!config.skipAuth && tokens.access) {
    config.headers.Authorization = `Bearer ${tokens.access}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (axios.isCancel(error) || !error.config) return Promise.reject(error);
    const { response, config } = error;

    // No response at all: offline, server down, or timeout.
    if (!response) {
      if (!config.silentNetwork) emit("api:network");
      error.apiError = {
        status: 0,
        code: "network_error",
        message: "We can't reach the server. Check your connection and try again.",
        retryAfter: 0,
        attemptsRemaining: null,
        fields: {},
      };
      return Promise.reject(error);
    }

    // 401: try ONE silent refresh, then replay the original request.
    if (response.status === 401 && !config.skipAuth && !config._retried && tokens.refresh) {
      config._retried = true;
      try {
        const access = await refreshAccessToken();
        config.headers.Authorization = `Bearer ${access}`;
        return api(config);
      } catch (refreshError) {
        if (isSessionInvalid(refreshError)) {
          tokens.clear();
          emit("auth:expired");
        }
        error.apiError = buildApiError(response);
        return Promise.reject(error);
      }
    }

    const apiError = buildApiError(response);
    error.apiError = apiError;
    if (response.status === 429 && !config.silent429) emit("api:rate-limit", apiError);
    if (response.status === 403 && !config.silent403) emit("api:forbidden", apiError);
    return Promise.reject(error);
  }
);

// ------------------------------------------------------------ small helpers
export async function loginRequest(username, password) {
  const { data } = await api.post("/auth/login/", { username, password }, { skipAuth: true, silent429: true });
  return data;
}

export async function registerRequest(payload) {
  const { data } = await api.post("/auth/register/", payload, { skipAuth: true });
  return data;
}

export async function logoutRequest() {
  const refresh = tokens.refresh;
  if (!refresh) return;
  try {
    await api.post("/auth/logout/", { refresh }, { skipAuth: true, silentNetwork: true, silent429: true });
  } catch {
    /* the local session is cleared anyway */
  }
}

export function fetchRecommendations(params, signal) {
  const query = { ...params, category: params.category || undefined };
  return api.get("/crops/recommend/", { params: query, signal }).then((response) => response.data);
}

// Scan photos are private, so <img src> can't load them directly (it can't send the
// login token). We download them with the token and show a temporary local URL.
const imageCache = new Map();

export function fetchImageObjectUrl(imageUrl) {
  if (!imageCache.has(imageUrl)) {
    const path = imageUrl.replace(/^\/api/, "");
    const promise = api
      .get(path, { responseType: "blob", silent429: true })
      .then((response) => URL.createObjectURL(response.data));
    promise.catch(() => imageCache.delete(imageUrl));
    imageCache.set(imageUrl, promise);
  }
  return imageCache.get(imageUrl);
}

export function clearImageCache() {
  for (const promise of imageCache.values()) {
    promise.then((url) => URL.revokeObjectURL(url)).catch(() => {});
  }
  imageCache.clear();
}