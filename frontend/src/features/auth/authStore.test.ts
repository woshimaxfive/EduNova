import { beforeEach, describe, expect, it } from "vitest";

import { mapApiUserToStudentUser } from "./authMappers";
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
        account: "demo",
        displayName: "演示学生",
        role: "student"
      }
    });

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) ?? "{}")).toMatchObject({
      version: 1,
      state: {
        token: "demo-token",
        user: { displayName: "演示学生" }
      }
    });
  });

  it("hydrates the legacy unversioned auth session", async () => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({
      token: "legacy-token",
      user: { id: 2, account: "legacy", displayName: "旧用户", role: "student" }
    }));

    await useAuthStore.persist.rehydrate();

    expect(useAuthStore.getState()).toMatchObject({ token: "legacy-token", isAuthenticated: true });
  });

  it("maps backend auth users into the frontend session shape", () => {
    expect(
      mapApiUserToStudentUser({
        id: 12,
        account: "student",
        display_name: "真实学生",
        role: "student",
        starter_mode: "data_structures"
      })
    ).toEqual({
      id: 12,
      account: "student",
      displayName: "真实学生",
      role: "student",
      starterMode: "data_structures"
    });
  });
});
