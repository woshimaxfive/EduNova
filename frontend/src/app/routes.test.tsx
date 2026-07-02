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

  it("redirects unauthenticated app routes to the calm login entry", async () => {
    render(
      <MemoryRouter initialEntries={["/app/studio"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "进入你的学习空间" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /演示学生/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "创建学生账号" })).toHaveAttribute("href", "/register");
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

    expect(await screen.findByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).toBeInTheDocument();
  });

  it("renders the protected course space for an authenticated student", async () => {
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
      <MemoryRouter initialEntries={["/app/courses/course-ai"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "人工智能导论" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "课程对话空间" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "知识学习画布" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "证据与 Agent 轨迹" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Studio 生成区" })).toBeInTheDocument();
  });

  it("treats the retired design lab route as not found", async () => {
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
      <MemoryRouter initialEntries={["/app/design-lab"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "没有找到这个学习入口" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "回到学习空间" })).toBeInTheDocument();
  });
});
