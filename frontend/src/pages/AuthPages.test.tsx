import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type InternalAxiosRequestConfig } from "axios";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AUTH_ENDPOINTS } from "../api/auth";
import { apiClient } from "../api/client";
import { useAuthStore } from "../features/auth/authStore";
import { LoginPage } from "./LoginPage";
import { RegisterPage } from "./RegisterPage";

describe("auth entry pages", () => {
  const originalAdapter = apiClient.defaults.adapter;

  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("keeps login focused on returning users without a shared demo-student shortcut", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "进入你的学习空间" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "创建学生账号" })).toHaveAttribute("href", "/register");
    expect(screen.queryByRole("button", { name: /演示学生/ })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "邮箱" })).toHaveValue("");
    expect(screen.getByLabelText("密码")).toHaveValue("");
    expect(screen.queryByDisplayValue("demo@edunova.local")).not.toBeInTheDocument();
  });

  it("logs in through the backend auth API and stores the returned session", async () => {
    const user = userEvent.setup();
    const calls: Array<{ url?: string; method?: string; data?: unknown }> = [];

    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
      calls.push({
        url: config.url,
        method: config.method,
        data: typeof config.data === "string" ? JSON.parse(config.data) : config.data
      });

      return {
        data: {
          data: {
            access_token: "jwt-token",
            token_type: "bearer",
            user: {
              id: 7,
              email: "student@edunova.local",
              display_name: "真实学生",
              role: "student",
              starter_mode: "ai_intro"
            }
          },
          trace_id: "trace_login"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    await user.type(screen.getByRole("textbox", { name: "邮箱" }), "student@edunova.local");
    await user.type(screen.getByLabelText("密码"), "Password123");
    await user.click(screen.getByRole("button", { name: "登录" }));

    expect(calls).toEqual([
      {
        url: AUTH_ENDPOINTS.login,
        method: "post",
        data: {
          email: "student@edunova.local",
          password: "Password123"
        }
      }
    ]);
    expect(useAuthStore.getState()).toMatchObject({
      token: "jwt-token",
      user: {
        id: 7,
        email: "student@edunova.local",
        displayName: "真实学生",
        starterMode: "ai_intro"
      },
      isAuthenticated: true
    });
  });

  it("shows backend login errors without writing a session", async () => {
    const user = userEvent.setup();

    apiClient.defaults.adapter = async () =>
      Promise.reject({
        response: {
          status: 401,
          data: {
            error: {
              code: "UNAUTHORIZED",
              message: "邮箱或密码不正确"
            }
          }
        }
      });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    await user.type(screen.getByRole("textbox", { name: "邮箱" }), "student@edunova.local");
    await user.type(screen.getByLabelText("密码"), "WrongPassword123");
    await user.click(screen.getByRole("button", { name: "登录" }));

    expect(await screen.findByText("邮箱或密码不正确")).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("registers through the backend API then logs in with the new account", async () => {
    const user = userEvent.setup();
    const calls: Array<{ url?: string; method?: string; data?: unknown }> = [];

    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
      calls.push({
        url: config.url,
        method: config.method,
        data: typeof config.data === "string" ? JSON.parse(config.data) : config.data
      });

      if (config.url === AUTH_ENDPOINTS.register) {
        return {
          data: {
            data: {
              id: 11,
              email: "blank@edunova.local",
              display_name: "空白学习者",
              role: "student",
              starter_mode: "blank"
            },
            trace_id: "trace_register"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: {
          data: {
            access_token: "new-jwt-token",
            token_type: "bearer",
            user: {
              id: 11,
              email: "blank@edunova.local",
              display_name: "空白学习者",
              role: "student",
              starter_mode: "blank"
            }
          },
          trace_id: "trace_login_after_register"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "准备你的学习空间" })).toBeInTheDocument();

    const blankMode = screen.getByRole("radio", { name: /空白开始/ });
    const aiIntroMode = screen.getByRole("radio", { name: /带一个示例课程开始/ });

    expect(blankMode).toHaveAttribute("value", "blank");
    expect(aiIntroMode).toHaveAttribute("value", "ai_intro");
    expect(aiIntroMode).toBeChecked();

    await user.click(blankMode);
    await user.clear(screen.getByRole("textbox", { name: "昵称" }));
    await user.type(screen.getByRole("textbox", { name: "昵称" }), "空白学习者");
    await user.type(screen.getByRole("textbox", { name: "邮箱" }), "blank@edunova.local");
    await user.type(screen.getByLabelText("密码"), "Demo123456");
    await user.type(screen.getByLabelText("确认密码"), "Demo123456");
    await user.click(screen.getByRole("button", { name: "创建并进入" }));

    expect(calls).toEqual([
      {
        url: AUTH_ENDPOINTS.register,
        method: "post",
        data: {
          display_name: "空白学习者",
          email: "blank@edunova.local",
          password: "Demo123456",
          starter_mode: "blank"
        }
      },
      {
        url: AUTH_ENDPOINTS.login,
        method: "post",
        data: {
          email: "blank@edunova.local",
          password: "Demo123456"
        }
      }
    ]);
    expect(useAuthStore.getState().token).toBe("new-jwt-token");
    expect(useAuthStore.getState().user).toMatchObject({
      displayName: "空白学习者",
      email: "blank@edunova.local",
      starterMode: "blank"
    });
  });
});
