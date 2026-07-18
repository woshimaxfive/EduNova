import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { synthesizeSpeech, transcribeSpeech } from "../../api/speech";
import { useBrowserSpeech } from "./useBrowserSpeech";

vi.mock("../../api/speech", () => ({
  transcribeSpeech: vi.fn(),
  synthesizeSpeech: vi.fn()
}));

describe("useBrowserSpeech server enhancement", () => {
  let processor: { onaudioprocess: ((event: { inputBuffer: { getChannelData: () => Float32Array } }) => void) | null };
  const trackStop = vi.fn();
  const audioPlay = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
    processor = { onaudioprocess: null };
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: trackStop }] }) }
    });
    class FakeAudioContext {
      sampleRate = 48000;
      destination = {};
      createMediaStreamSource() {
        return { connect: vi.fn(), disconnect: vi.fn() };
      }
      createScriptProcessor() {
        return Object.assign(processor, { connect: vi.fn(), disconnect: vi.fn() });
      }
      close() {
        return Promise.resolve();
      }
    }
    Object.defineProperty(globalThis, "AudioContext", { configurable: true, value: FakeAudioContext });
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:speech") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    class FakeAudio {
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      pause = vi.fn();
      play = audioPlay;
    }
    Object.defineProperty(globalThis, "Audio", { configurable: true, value: FakeAudio });
  });

  afterEach(() => {
    Reflect.deleteProperty(navigator, "mediaDevices");
  });

  it("records PCM, sends it to Xfyun endpoint, and writes the transcript", async () => {
    vi.mocked(transcribeSpeech).mockResolvedValue({ transcript: "数据结构", provider: "xfyun", duration_ms: 200 });
    const onTranscript = vi.fn();
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript, onNotice: vi.fn() }));

    await act(async () => result.current.toggleListening());
    expect(result.current.isListening).toBe(true);
    processor.onaudioprocess?.({ inputBuffer: { getChannelData: () => new Float32Array(9600).fill(0.1) } });
    act(() => result.current.stopListening());

    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith("数据结构"));
    expect(transcribeSpeech).toHaveBeenCalledTimes(1);
    expect(vi.mocked(transcribeSpeech).mock.calls[0]?.[0].type).toBe("application/octet-stream");
    expect(trackStop).toHaveBeenCalled();
  });

  it("plays server-generated audio for read aloud", async () => {
    vi.mocked(synthesizeSpeech).mockResolvedValue(new Blob(["mp3"], { type: "audio/mpeg" }));
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));

    await act(async () => result.current.speak("## 你好 [来源1]", "message-1"));

    expect(synthesizeSpeech).toHaveBeenCalledWith("你好");
    expect(audioPlay).toHaveBeenCalledTimes(1);
    expect(result.current.activeSpeechId).toBe("message-1");
  });
});
