import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { makeCompletedAiJob } from "../../test/aiJobs";
import { AiJobProgress } from "./AiJobProgress";

describe("AiJobProgress", () => {
  it("keeps the path task context in a section resource result link", () => {
    const job = makeCompletedAiJob({
      request: { course_id: 808, path_task_id: 61 },
      result: { resource_ids: [901], path_task_id: "61" }
    });

    render(<MemoryRouter><AiJobProgress job={job} /></MemoryRouter>);

    expect(screen.getByText("本节资源生成")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看结果" })).toHaveAttribute(
      "href",
      "/app/studio?course_id=808&resource_id=901&path_task_id=61"
    );
  });

  it("links completed practice and report jobs to their durable results", () => {
    const { rerender } = render(
      <MemoryRouter>
        <AiJobProgress job={makeCompletedAiJob({
          workflow: "practice_generation",
          request: { course_id: 808 },
          result: { course_id: 808, session_id: 501 }
        })} />
      </MemoryRouter>
    );

    expect(screen.getByText("练习生成")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看结果" })).toHaveAttribute(
      "href",
      "/app/practice?course_id=808&session_id=501"
    );

    rerender(
      <MemoryRouter>
        <AiJobProgress job={makeCompletedAiJob({
          workflow: "report_generation",
          request: { course_id: 808 },
          result: { course_id: 808, report_id: 701 }
        })} />
      </MemoryRouter>
    );
    expect(screen.getByText("学习报告生成")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看结果" })).toHaveAttribute(
      "href",
      "/app/reports?course_id=808"
    );
  });
});
