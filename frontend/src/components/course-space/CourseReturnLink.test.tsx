import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { CourseReturnLink } from "./CourseReturnLink";

describe("CourseReturnLink", () => {
  it("restores the source course session, answer, and knowledge point", () => {
    render(
      <MemoryRouter initialEntries={["/app/practice?course_id=808&return_to=course&course_session_id=77&course_message_id=99&knowledge_point_id=401"]}>
        <CourseReturnLink courseId={808} />
      </MemoryRouter>
    );

    expect(screen.getByRole("link", { name: "返回课程空间继续学习" })).toHaveAttribute(
      "href",
      "/app/courses/808?course_session_id=77&course_message_id=99&knowledge_point_id=401"
    );
  });

  it("stays hidden for ordinary page navigation or another course", () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={["/app/practice?course_id=808"]}>
        <CourseReturnLink courseId={808} />
      </MemoryRouter>
    );
    expect(screen.queryByRole("link", { name: "返回课程空间继续学习" })).not.toBeInTheDocument();

    rerender(
      <MemoryRouter initialEntries={["/app/practice?course_id=808&return_to=course"]}>
        <CourseReturnLink courseId={809} />
      </MemoryRouter>
    );
    expect(screen.queryByRole("link", { name: "返回课程空间继续学习" })).not.toBeInTheDocument();
  });

  it("supports a compact icon entry without losing its accessible name", () => {
    render(
      <MemoryRouter initialEntries={["/app/path?course_id=808&return_to=course"]}>
        <CourseReturnLink courseId={808} compact />
      </MemoryRouter>
    );

    expect(screen.getByRole("link", { name: "返回课程空间" })).toHaveClass("course-return-link-compact");
  });
});
