import { create } from "zustand";

export const AUTH_STORAGE_KEY = "edunova.auth";

export type StudentUser = {
  id: number;
  account: string;
  displayName: string;
  role: "student" | "admin";
  starterMode?: "blank" | "data_structures";
};

export type AuthSession = {
  token: string;
  user: StudentUser;
};

type AuthState = {
  token: string | null;
  user: StudentUser | null;
  isAuthenticated: boolean;
  setSession: (session: AuthSession) => void;
  clearSession: () => void;
};

function readStoredSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthSession) : null;
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

const storedSession = typeof localStorage === "undefined" ? null : readStoredSession();

export const useAuthStore = create<AuthState>((set) => ({
  token: storedSession?.token ?? null,
  user: storedSession?.user ?? null,
  isAuthenticated: Boolean(storedSession?.token),
  setSession: (session) => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
    set({
      token: session.token,
      user: session.user,
      isAuthenticated: true
    });
  },
  clearSession: () => {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    set({
      token: null,
      user: null,
      isAuthenticated: false
    });
  }
}));
