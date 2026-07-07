import { apiClient } from "./client";
import { type ApiEnvelope, type ApiUser } from "../types/api";

export const AUTH_ENDPOINTS = {
  register: "/auth/register",
  login: "/auth/login",
  me: "/auth/me",
  logout: "/auth/logout"
} as const;

export type RegisterRequest = {
  email: string;
  password: string;
  display_name: string;
  starter_mode?: "blank" | "ai_intro";
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type UpdateCurrentUserRequest = {
  display_name: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  user: ApiUser;
};

export async function register(payload: RegisterRequest) {
  const response = await apiClient.post<ApiEnvelope<ApiUser>>(AUTH_ENDPOINTS.register, payload);
  return response.data;
}

export async function login(payload: LoginRequest) {
  const response = await apiClient.post<ApiEnvelope<LoginResponse>>(AUTH_ENDPOINTS.login, payload);
  return response.data;
}

export async function getCurrentUser() {
  const response = await apiClient.get<ApiEnvelope<ApiUser>>(AUTH_ENDPOINTS.me);
  return response.data;
}

export async function updateCurrentUser(payload: UpdateCurrentUserRequest) {
  const response = await apiClient.patch<ApiEnvelope<ApiUser>>(AUTH_ENDPOINTS.me, payload);
  return response.data;
}

export async function logout() {
  const response = await apiClient.post<ApiEnvelope<{ ok: true }>>(AUTH_ENDPOINTS.logout);
  return response.data;
}
