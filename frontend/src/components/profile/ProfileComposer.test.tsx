import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfileComposer } from "./ProfileComposer";

describe("ProfileComposer", () => {
  it("explains what to answer without showing examples", () => {
    render(
      <ProfileComposer
        inputRef={createRef<HTMLTextAreaElement>()}
        value=""
        nextQuestion="遇到新概念时，你通常怎样理解得最快？"
        nextQuestionDimension="cognitive_style"
        isUpdating={false}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByText("建议补充 · 认知风格")).toBeInTheDocument();
    expect(screen.getByText("描述你理解、分析和整理新知识时的习惯即可。")).toBeInTheDocument();
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
  });
});
