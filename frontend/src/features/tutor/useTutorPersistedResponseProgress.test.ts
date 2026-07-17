import { describe, expect, it } from "vitest";

import { type AgentTrace } from "../../api/agents";
import { toCompletedTutorResponseProgress } from "./useTutorPersistedResponseProgress";

describe("toCompletedTutorResponseProgress", () => {
  it("restores the safe trace summaries and recorded duration for a persisted answer", () => {
    const trace: AgentTrace = {
      trace_id: "trace-home-1",
      workflow: "home_tutor",
      artifact_type: "tutor_message",
      artifact_id: "message-1",
      course_id: null,
      status: "completed",
      summary: { duration_ms: 4_800 },
      steps: [
        {
          id: "step-1",
          agent_name: "context",
          step_index: 1,
          status: "completed",
          input_summary: "读取会话上下文",
          output_summary: "上下文已读取",
          duration_ms: 800,
          metadata: {},
          created_at: "2026-07-18T01:00:00Z"
        },
        {
          id: "step-2",
          agent_name: "review",
          step_index: 2,
          status: "completed",
          input_summary: null,
          output_summary: "已审核回答依据",
          duration_ms: 1_200,
          metadata: {},
          created_at: "2026-07-18T01:00:01Z"
        }
      ]
    };

    expect(toCompletedTutorResponseProgress(trace)).toEqual({
      startedAt: Date.parse("2026-07-18T01:00:00Z"),
      stages: ["读取会话上下文", "已审核回答依据"],
      durationMs: 4_800
    });
  });

  it("does not render a completed process when the trace has no safe step summary", () => {
    const trace: AgentTrace = {
      trace_id: "trace-empty",
      workflow: "home_tutor",
      artifact_type: "tutor_message",
      artifact_id: "message-2",
      course_id: null,
      status: "completed",
      steps: []
    };

    expect(toCompletedTutorResponseProgress(trace)).toBeNull();
  });
});
