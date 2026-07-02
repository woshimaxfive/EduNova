import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PATHS } from "../../app/routePaths";
import { TopNavigation } from "./TopNavigation";

describe("TopNavigation", () => {
  it("keeps only global spaces in the primary app navigation", () => {
    render(
      <MemoryRouter>
        <TopNavigation />
      </MemoryRouter>
    );

    const appNavigation = screen.getByRole("navigation", { name: "应用导航" });
    const expectedRoutes = [
      ["学习空间", PATHS.app],
      ["资料库", PATHS.library],
      ["Studio", PATHS.studio]
    ] as const;

    for (const [label, path] of expectedRoutes) {
      expect(within(appNavigation).getByRole("link", { name: label })).toHaveAttribute("href", path);
    }

    expect(within(appNavigation).queryByRole("link", { name: "画像" })).not.toBeInTheDocument();
    expect(within(appNavigation).queryByRole("link", { name: "辅导" })).not.toBeInTheDocument();
    expect(within(appNavigation).queryByRole("link", { name: "练习" })).not.toBeInTheDocument();
    expect(within(appNavigation).queryByRole("link", { name: "报告" })).not.toBeInTheDocument();
    expect(within(appNavigation).queryByRole("link", { name: "设置" })).not.toBeInTheDocument();
  });

  it("keeps profile reports and settings available from the personal menu", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <TopNavigation />
      </MemoryRouter>
    );

    await user.click(screen.getByRole("button", { name: "打开个人菜单" }));

    const personalMenu = screen.getByRole("menu", { name: "个人菜单" });
    const expectedRoutes = [
      ["学习画像", PATHS.profile],
      ["学习报告", PATHS.reports],
      ["系统设置", PATHS.settings]
    ] as const;

    for (const [label, path] of expectedRoutes) {
      expect(within(personalMenu).getByRole("menuitem", { name: label })).toHaveAttribute("href", path);
    }
  });
});
