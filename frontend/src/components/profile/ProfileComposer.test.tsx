import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfileComposer } from "./ProfileComposer";

describe("ProfileComposer", () => {
  it("explains what to answer with non-interactive text examples", () => {
    render(
      <ProfileComposer
        inputRef={createRef<HTMLTextAreaElement>()}
        value=""
        nextQuestion="遇到新知识时，你通常怎样更容易弄懂？"
        nextQuestionDimension="cognitive_style"
        isUpdating={false}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByText("建议补充 · 理解习惯")).toBeInTheDocument();
    expect(screen.getByText("说说面对新知识时，你通常会先做什么、怎样逐步理解。")).toBeInTheDocument();
    expect(screen.getByText("可以说：先看整体框架、逐步推导、通过类比理解，或者边做边总结。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /先看整体框架/ })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("用自己的话回答即可")).toBeInTheDocument();
  });

  it("uses neutral guidance for a legacy response without a dimension key", () => {
    render(
      <ProfileComposer
        inputRef={createRef<HTMLTextAreaElement>()}
        value=""
        nextQuestion="最近有什么想补充的？"
        isUpdating={false}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByText("建议补充")).toBeInTheDocument();
    expect(screen.getByText("用自己的话描述当前情况即可，不需要使用专业术语。")).toBeInTheDocument();
    expect(screen.getByText("可以说：当前目标、已有基础、学习困难或学习安排。")).toBeInTheDocument();
  });
});
