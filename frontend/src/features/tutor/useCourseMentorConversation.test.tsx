import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTutorSession, listTutorSessions, streamTutorMessage } from "../../api/tutor";
import { useCourseMentorConversation } from "./useCourseMentorConversation";

vi.mock("../../api/tutor", () => ({
  createTutorSession: vi.fn(),
  getTutorSession: vi.fn(),
  listTutorSessions: vi.fn(),
  streamTutorMessage: vi.fn()
}));

vi.mock("../speech/useBrowserSpeech", () => ({
  useBrowserSpeech: () => ({
    isListening: false,
    isTranscribing: false,
    activeSpeechId: null,
    isSpeechPaused: false,
    toggleListening: vi.fn(),
    stopListening: vi.fn(),
    speak: vi.fn(),
    stopSpeaking: vi.fn(),
    pauseOrResumeSpeaking: vi.fn()
  })
}));

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>;
}

describe("useCourseMentorConversation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listTutorSessions).mockResolvedValue({ data: [], trace_id: "trace-sessions" });
    vi.mocked(createTutorSession).mockResolvedValue({
      data: {
        id: "s1", course_id: "7", scope: "course", title: "资源提问", mode: "chat",
        archived_from_home: false, selected_material_ids: [], created_at: "2026-07-18T00:00:00Z", updated_at: "2026-07-18T00:00:00Z"
      },
      trace_id: "trace-create"
    });
    vi.mocked(streamTutorMessage).mockResolvedValue({
      session: {
        id: "s1", course_id: "7", scope: "course", title: "资源提问", mode: "chat",
        archived_from_home: false, selected_material_ids: [], created_at: "2026-07-18T00:00:00Z", updated_at: "2026-07-18T00:00:00Z"
      },
      messages: []
    });
  });

  it("creates a normal course session and locks the selected resource into the request", async () => {
    const onSessionChange = vi.fn();
    const { result } = renderHook(() => useCourseMentorConversation({
      courseId: 7,
      requestedSessionId: null,
      contextResourceId: 701,
      enabled: true,
      onSessionChange
    }), { wrapper });

    await waitFor(() => expect(listTutorSessions).toHaveBeenCalled());
    act(() => result.current.setPrompt("这份资源的第二步为什么这样做？"));
    await act(async () => result.current.send());

    expect(createTutorSession).toHaveBeenCalledWith(expect.objectContaining({ scope: "course", course_id: 7 }));
    expect(streamTutorMessage).toHaveBeenCalledWith(
      "s1",
      { message: "这份资源的第二步为什么这样做？", context_resource_id: 701 },
      expect.any(Object)
    );
    expect(onSessionChange).toHaveBeenCalledWith("s1");
  });
});
