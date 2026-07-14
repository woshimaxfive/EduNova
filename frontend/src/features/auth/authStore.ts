import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

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

const legacyCompatibleStorage: StateStorage = {
  getItem(name) {
    const raw = localStorage.getItem(name);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as { state?: unknown; version?: number } & Partial<AuthSession>;
      if ("state" in parsed) return raw;
      if (typeof parsed.token === "string" && parsed.user) {
        return JSON.stringify({
          state: { token: parsed.token, user: parsed.user, isAuthenticated: true },
          version: 0
        });
      }
    } catch {
      localStorage.removeItem(name);
    }
    return null;
  },
  setItem: (name, value) => localStorage.setItem(name, value),
  removeItem: (name) => localStorage.removeItem(name)
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setSession: (session) => set({ token: session.token, user: session.user, isAuthenticated: true }),
      clearSession: () => {
        set({ token: null, user: null, isAuthenticated: false });
        void useAuthStore.persist.clearStorage();
      }
    }),
    {
      name: AUTH_STORAGE_KEY,
      version: 1,
      storage: createJSONStorage(() => legacyCompatibleStorage),
      partialize: ({ token, user, isAuthenticated }) => ({ token, user, isAuthenticated }),
      migrate: (persisted) => {
        const state = persisted as Partial<AuthState> | undefined;
        return {
          token: state?.token ?? null,
          user: state?.user ?? null,
          isAuthenticated: Boolean(state?.token)
        };
      }
    }
  )
);
