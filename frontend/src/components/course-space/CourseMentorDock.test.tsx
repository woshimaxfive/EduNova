import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { CourseMentorDock } from "./CourseMentorDock";

function MentorHarness() {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  return (
    <CourseMentorDock
      open={open}
      courseTitle="数据结构"
      pointTitle="二叉树遍历"
      resourceTitle="遍历顺序图解"
      masteryScore={42}
      weaknessCount={1}
      recommendation={null}
      messages={[{ id: "m1", role: "assistant", content: "先比较前序和中序。" }]}
      prompt={prompt}
      isSending={false}
      feedback={null}
      isListening={false}
      isTranscribing={false}
      isSpeaking={false}
      isSpeechPaused={false}
      onOpenChange={setOpen}
      onPromptChange={setPrompt}
      onPromptKeyDown={vi.fn()}
      onSend={vi.fn()}
      onToggleListening={vi.fn()}
      onReadLatest={vi.fn()}
      onPauseOrResume={vi.fn()}
      onStopSpeaking={vi.fn()}
    />
  );
}

describe("CourseMentorDock", () => {
  it("opens as a nonmodal course assistant and quick questions only fill the draft", async () => {
    const user = userEvent.setup();
    render(<MentorHarness />);

    await user.click(screen.getByRole("button", { name: "打开课程助教" }));
    expect(screen.getByText("EduNova 课程助教")).toBeInTheDocument();
    expect(screen.getByText("数据结构 · 遍历顺序图解")).toBeInTheDocument();
    expect(screen.getByText("42 分")).toBeInTheDocument();
    expect(screen.getByText("先比较前序和中序。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "解释这份资源的核心内容" }));
    expect(screen.getByRole("textbox", { name: "继续问当前内容" })).toHaveValue("解释这份资源的核心内容");
    expect(screen.getByRole("button", { name: "朗读最新回答" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "语音输入" })).toBeInTheDocument();
  });
});
