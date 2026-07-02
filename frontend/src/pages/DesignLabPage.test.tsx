import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { DesignLabPage } from "./DesignLabPage";

describe("DesignLabPage", () => {
  it("lets the student tune the home layout and export a JSON preset", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <DesignLabPage />
      </MemoryRouter>
    );

    const controls = screen.getByRole("region", { name: "主页调参控制台" });
    const preview = screen.getByRole("region", { name: "主页预览画布" });

    expect(screen.getByRole("heading", { name: "Design Lab v0" })).toBeInTheDocument();
    expect(within(preview).getByText("历史栏 240px")).toBeInTheDocument();

    fireEvent.change(within(controls).getByRole("slider", { name: "历史栏宽度" }), {
      target: { value: "320" }
    });
    await user.click(within(controls).getByRole("button", { name: "最近学习放到右侧" }));
    await user.click(screen.getByRole("button", { name: "复制配置" }));

    expect(within(preview).getByText("历史栏 320px")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("配置已生成");

    const exportedConfig = screen.getByRole("textbox", { name: "Design Lab 配置 JSON" });
    expect((exportedConfig as HTMLTextAreaElement).value).toContain('"historyWidth": 320');
    expect((exportedConfig as HTMLTextAreaElement).value).toContain('"recentLearningPosition": "side"');
  });
});
