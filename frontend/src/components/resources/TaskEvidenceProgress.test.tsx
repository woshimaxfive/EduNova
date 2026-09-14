import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { apiClient } from "../../api/client";
import { TaskEvidenceProgress } from "./TaskEvidenceProgress";

afterEach(() => vi.restoreAllMocks());

function Location() {
  const location = useLocation();
  return <output>{location.pathname}{location.search}</output>;
}

function setup(blocked = false) {
  vi.spyOn(apiClient, "get").mockResolvedValue({ data: { data: {
    user_reported_completed: true, activity_completed: false, assessment_passed: false, mastered: false,
    mastery_score: null, blocked_reasons: blocked ? ["资源版本已变化"] : [], next_step: "take_assessment"
  } } });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><TaskEvidenceProgress taskId={3} resourceId={11} courseId="2" isQuiz /><Location /></MemoryRouter>
  </QueryClientProvider>);
}

it("keeps user completion separate and opens the exact bound assessment", async () => {
  const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: { data: { id: "6" } } });
  setup();
  expect(await screen.findByText(/用户标记：已学 · 活动完成：未完成/)).toBeVisible();
  expect(screen.getByText(/评估：未通过 · 掌握：尚未掌握/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "进入绑定测验" }));
  expect(post).toHaveBeenCalledWith("/paths/tasks/3/resources/11/practice");
  expect(await screen.findByText("/app/practice?course_id=2&session_id=6")).toBeVisible();
});

it("blocks assessment launch when server evidence reports a version conflict", async () => {
  const post = vi.spyOn(apiClient, "post");
  setup(true);
  expect(await screen.findByText("资源版本已变化")).toBeVisible();
  expect(screen.getByRole("button", { name: "进入绑定测验" })).toBeDisabled();
  expect(post).not.toHaveBeenCalled();
});
