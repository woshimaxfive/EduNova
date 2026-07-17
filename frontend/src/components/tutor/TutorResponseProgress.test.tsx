import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TutorResponseProgress } from "./TutorResponseProgress";

describe("TutorResponseProgress", () => {
  it("shows the current safe stage while an answer is streaming", () => {
    render(<TutorResponseProgress state={{ startedAt: 0, stages: ["正在读取会话上下文", "正在检索课程资料"] }} />);

    expect(screen.getByRole("status", { name: "正在协作回答" })).toHaveTextContent("正在协作回答");
    expect(screen.getAllByText("正在检索课程资料")).toHaveLength(2);
  });

  it("collapses completed stages until the learner asks to view them", async () => {
    const user = userEvent.setup();
    render(
      <TutorResponseProgress
        completed
        durationMs={11_000}
        state={{ startedAt: 0, stages: ["正在读取会话上下文", "正在检索课程资料", "正在组织回答"] }}
      />
    );

    const trigger = screen.getByRole("button", { name: "协作完成 · 用时 11 秒" });
    expect(screen.queryByRole("list", { name: "本次协作步骤" })).not.toBeInTheDocument();

    await user.click(trigger);

    expect(screen.getByRole("list", { name: "本次协作步骤" })).toHaveTextContent("正在组织回答");
  });
});
