import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AppRoutes } from "./routes";
import { useAuthStore } from "../features/auth/authStore";

describe("EduNova routes", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("redirects unauthenticated app routes to the premium login entry", async () => {
    render(
      <MemoryRouter initialEntries={["/app/studio"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "进入你的 AI 学习空间" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "体验演示学生" })).toBeInTheDocument();
  });

  it("redirects authenticated students away from public entry pages", async () => {
    useAuthStore.getState().setSession({
      token: "demo-token",
      user: {
        id: 1,
        email: "demo@edunova.local",
        displayName: "演示学生",
        role: "student"
      }
    });

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "今天的 AI 学习空间" })).toBeInTheDocument();
  });
});
