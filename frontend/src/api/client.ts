import axios from "axios";

import { PATHS } from "../app/routePaths";
import { useAuthStore } from "../features/auth/authStore";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
  timeout: 20000
});

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
