import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  AI_JOB_ENDPOINTS,
  createCourseBuilderJob,
  createResourceGenerationJob,
  streamAiJob
} from "./aiJobs";
import { apiClient } from "./client";
import { useAuthStore } from "../features/auth/authStore";
import { makeCompletedAiJob } from "../test/aiJobs";


describe("AI job API contracts", () => {
  const previousAdapter = apiClient.defaults.adapter;
  const previousFetch = globalThis.fetch;

  beforeEach(() => {
    useAuthStore.getState().setSession({
      token: "job-token",
      user: { id: 1, account: "student", displayName: "学生", role: "student" }
    });
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    globalThis.fetch = previousFetch;
    useAuthStore.getState().clearSession();
  });

  it("sends idempotency keys to both long-running creation endpoints", async () => {
    const calls: Array<{ url?: string; key?: string; data?: unknown }> = [];
    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        key: String(config.headers.get("Idempotency-Key") ?? ""),
        data: typeof config.data === "string" ? JSON.parse(config.data) : config.data
      });
      return {
        data: { data: makeCompletedAiJob(), trace_id: "trace_api" },
        status: 202,
        statusText: "Accepted",
        headers: {},
        config
      };
    };

    await createCourseBuilderJob({ material_ids: [11], course_title: "冲刺课" }, "course-key");
    await createResourceGenerationJob({ course_id: 8, resource_types: ["doc"], difficulty: "medium" }, "resource-key");

    expect(calls).toEqual([
      { url: AI_JOB_ENDPOINTS.courseBuilder, key: "course-key", data: { material_ids: [11], course_title: "冲刺课" } },
      { url: AI_JOB_ENDPOINTS.resourceGeneration, key: "resource-key", data: { course_id: 8, resource_types: ["doc"], difficulty: "medium" } }
    ]);
  });

  it("parses authenticated SSE snapshots and terminal events", async () => {
    const job = makeCompletedAiJob();
    const body = [
      `event: snapshot\ndata: ${JSON.stringify({ ...job, status: "running", progress_percent: 60 })}\n\n`,
      `event: done\ndata: ${JSON.stringify(job)}\n\n`,
      `event: error\ndata: ${JSON.stringify({ ...job, status: "failed" })}\n\n`
    ];
    const encoder = new TextEncoder();
    globalThis.fetch = vi.fn(async (_input, init) => {
      expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer job-token");
      return new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(body[0].slice(0, 37)));
          controller.enqueue(encoder.encode(body[0].slice(37) + body[1] + body[2]));
          controller.close();
        }
      }), { status: 200, headers: { "Content-Type": "text/event-stream" } });
    }) as typeof fetch;
    const events: string[] = [];

    await streamAiJob(job.job_id, (event, snapshot) => events.push(`${event}:${snapshot.progress_percent}`));

    expect(events).toEqual(["snapshot:60", "done:100"]);
  });
});
