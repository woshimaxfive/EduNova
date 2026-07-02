import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { useAuthStore } from "../features/auth/authStore";
import { LoginPage } from "./LoginPage";
import { RegisterPage } from "./RegisterPage";

describe("auth entry pages", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clearSession();
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
  });

  it("lets registration choose blank or the built-in AI intro starter course", async () => {
    const user = userEvent.setup();

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

    expect(useAuthStore.getState().user).toMatchObject({
      displayName: "空白学习者",
      email: "blank@edunova.local",
      starterMode: "blank"
    });
  });
});
