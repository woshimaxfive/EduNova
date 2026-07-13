import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AGENT_ENDPOINTS } from "../../api/agents";
import { apiClient } from "../../api/client";
import type { ProfileEventResponse } from "../../api/profiles";
import { ProfileDrawer } from "./ProfileDrawer";

const candidateEvent: ProfileEventResponse = {
  id: "event-candidate",
  dimension: "profile_chat",
  change_summary: "发现可能存在反向传播薄弱点",
  evidence_json: {
    source_type: "practice_assessment",
    updated_dimensions: [],
    candidate_dimensions: ["weak_points"]
  },
  source_type: "practice_assessment",
  status: "candidate",
  confidence_score: 0.71,
  agent_trace_id: "trace-candidate",
  created_at: "2026-07-13T08:00:00Z"
};

let previousAdapter = apiClient.defaults.adapter;

function renderDrawer() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>打开证据</button>
        <ProfileDrawer
          mode={open ? "event" : null}
          dimension={null}
          event={candidateEvent}
          relatedEvents={[]}
          onClose={() => setOpen(false)}
          onOpenEvent={() => undefined}
        />
      </>
    );
  }

  return render(<QueryClientProvider client={queryClient}><Harness /></QueryClientProvider>);
}

describe("ProfileDrawer", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    apiClient.defaults.adapter = async (config) => {
      if (config.url === AGENT_ENDPOINTS.trace("trace-candidate")) {
        return {
          data: {
            data: {
              trace_id: "trace-candidate",
              workflow: "profile",
              artifact_type: "profile_event",
              artifact_id: "event-candidate",
              course_id: null,
              status: "completed",
              steps: [{
                id: "step-gate",
                agent_name: "evidence_gate",
                step_index: 2,
                status: "completed",
                input_summary: "检查候选证据",
                output_summary: "证据尚未达到长期画像门槛",
                duration_ms: 12,
                metadata: {},
                created_at: "2026-07-13T08:00:00Z"
              }]
            },
            trace_id: "trace-candidate"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      throw new Error(`Unexpected request: ${config.url}`);
    };
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("keeps candidate evidence separate and replays its own ProfileGraph", async () => {
    const user = userEvent.setup();
    renderDrawer();

    await user.click(screen.getByRole("button", { name: "打开证据" }));
    const dialog = screen.getByRole("dialog", { name: "证据详情" });
    expect(dialog).toHaveTextContent("候选证据");
    expect(dialog).toHaveTextContent("本次没有直接写入长期画像");
    expect(dialog).toHaveTextContent("薄弱点");

    await user.click(screen.getByRole("button", { name: "回放 ProfileGraph" }));
    expect(await screen.findByText("evidence_gate")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "回放 ProfileGraph执行轨迹" })).toHaveTextContent("证据尚未达到长期画像门槛");
  });

  it("traps focus in the overlay and restores it after Escape", async () => {
    const user = userEvent.setup();
    renderDrawer();
    const trigger = screen.getByRole("button", { name: "打开证据" });

    await user.click(trigger);
    const closeButton = screen.getByRole("button", { name: "关闭证据详情" });
    await waitFor(() => expect(closeButton).toHaveFocus());

    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByRole("button", { name: "回放 ProfileGraph" })).toHaveFocus();
    await user.keyboard("{Tab}");
    expect(closeButton).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
