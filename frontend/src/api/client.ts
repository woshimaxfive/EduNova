import axios from "axios";

import { PATHS } from "../app/routePaths";
import { useAuthStore } from "../features/auth/authStore";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1",
  timeout: 20000
});

// Model-backed synchronous compatibility endpoints can legitimately span several
// provider attempts. Keep ordinary APIs fail-fast, while preventing the browser
// from reporting a failure before the server finishes an atomic write.
export const MODEL_OPERATION_TIMEOUT_MS = 180000;

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().clearSession();
      if (typeof window !== "undefined" && window.location.pathname.startsWith(PATHS.app)) {
        window.location.assign(PATHS.login);
      }
    }
    return Promise.reject(error);
  }
);
