import { beforeEach, describe, expect, it } from "vitest";

import { AUTH_STORAGE_KEY, useAuthStore } from "./authStore";

describe("authStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  it("persists the demo student session for route guards", () => {
    useAuthStore.getState().setSession({
      token: "demo-token",
      user: {
        id: 1,
        email: "demo@edunova.local",
        displayName: "演示学生",
        role: "student"
      }
    });

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) ?? "{}")).toMatchObject({
      token: "demo-token",
      user: { displayName: "演示学生" }
    });
  });
});
