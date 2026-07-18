import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TutorResponseProgress } from "./TutorResponseProgress";

describe("TutorResponseProgress", () => {
  it("shows the current safe stage while an answer is streaming", () => {
    render(<TutorResponseProgress state={{ startedAt: 0, stages: ["正在读取会话上下文", "正在检索课程资料"] }} />);

    expect(screen.getByRole("status", { name: "AI 正在完成这一步" })).toHaveTextContent("AI 正在完成这一步");
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

    const trigger = screen.getByRole("button", { name: /协作完成/ });
    expect(screen.queryByRole("list")).not.toBeInTheDocument();

    await user.click(trigger);

    expect(screen.getByRole("list")).toHaveTextContent("正在组织回答");
  });
});
