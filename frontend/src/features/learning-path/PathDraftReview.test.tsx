import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";
import { apiClient } from "../../api/client";
import { PathDraftReview } from "./PathDraftReview";

const original = apiClient.defaults.adapter;
afterEach(() => { apiClient.defaults.adapter = original; });

function setup(active: string | null, base: number | null, conflict = false) {
  const calls: unknown[] = [];
  let approved = false;
  const path = { id: "8", title: "复习安排", goal: "掌握队列", status: "draft", plan_json: { revision_of: base } };
  apiClient.defaults.adapter = async (config) => {
    let data: unknown;
    if (config.url === "/paths/drafts") data = approved ? [] : [path];
    else if (config.url === "/paths/8") data = { path, tasks: [{ id: "11", title: "队列复习", reason: "上次练习较弱" }] };
    else if (config.url === "/paths/8/approve") {
      calls.push(JSON.parse(config.data));
      if (conflict) throw new Error("409 conflict");
      approved = true;
      data = {};
    } else throw new Error(`Unexpected ${config.url}`);
    return { data: { data }, status: 200, statusText: "OK", headers: {}, config };
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><PathDraftReview courseId={1} activePathId={active} currentReady /></QueryClientProvider>);
  return calls;
}

describe("PathDraftReview", () => {
  it.each([["7", 7], [null, null]] as const)("previews persisted drafts and approves against base %s", async (active, base) => {
    const calls = setup(active, base);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /查看草稿/ }));
    expect(await screen.findByText("队列复习")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /开始学习/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认并启用此计划" }));
    await waitFor(() => expect(calls).toEqual([{ expected_active_path_id: base }]));
    await waitFor(() => expect(screen.queryByRole("button", { name: /查看草稿/ })).not.toBeInTheDocument());
  });

  it("prevents a stale draft from replacing the current plan", async () => {
    const calls = setup("9", 7);
    await userEvent.click(await screen.findByRole("button", { name: /查看草稿/ }));
    expect(await screen.findByRole("button", { name: "确认并启用此计划" })).toBeDisabled();
    expect(calls).toEqual([]);
  });

  it("keeps the preview and reports concurrent approval failure", async () => {
    setup("7", 7, true);
    await userEvent.click(await screen.findByRole("button", { name: /查看草稿/ }));
    await userEvent.click(await screen.findByRole("button", { name: "确认并启用此计划" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("确认失败");
    expect(screen.getByText("队列复习")).toBeInTheDocument();
  });
});
