import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PATHS } from "../../app/routePaths";
import { TopNavigation } from "./TopNavigation";

describe("TopNavigation", () => {
  it("exposes every primary student route in the visible app navigation", () => {
    render(
      <MemoryRouter>
        <TopNavigation />
      </MemoryRouter>
    );

    const appNavigation = screen.getByRole("navigation", { name: "应用导航" });
    const expectedRoutes = [
      ["学习空间", PATHS.app],
      ["资料库", PATHS.library],
      ["Studio", PATHS.studio],
      ["画像", PATHS.profile],
      ["辅导", PATHS.tutor],
      ["练习", PATHS.practice],
      ["报告", PATHS.reports],
      ["设置", PATHS.settings]
    ] as const;

    for (const [label, path] of expectedRoutes) {
      expect(within(appNavigation).getByRole("link", { name: label })).toHaveAttribute("href", path);
    }
  });
});
