import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SpeechRequestError, synthesizeSpeech, transcribeSpeech } from "../../api/speech";
import { useBrowserSpeech } from "./useBrowserSpeech";

vi.mock("../../api/speech", () => ({
  SpeechRequestError: class SpeechRequestError extends Error {
    constructor(message: string, readonly code = "SPEECH_PROVIDER_ERROR") {
      super(message);
    }
  },
  transcribeSpeech: vi.fn(),
  synthesizeSpeech: vi.fn()
}));

describe("useBrowserSpeech server enhancement", () => {
  const trackStop = vi.fn();
  const audioPlay = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: trackStop }] }) }
    });
    class FakeAudioContext {
      decodeAudioData() {
        return Promise.resolve({
          sampleRate: 48000,
          getChannelData: () => new Float32Array(9600).fill(0.1)
        });
      }
      close() {
        return Promise.resolve();
      }
    }
    Object.defineProperty(globalThis, "AudioContext", { configurable: true, value: FakeAudioContext });
    class FakeMediaRecorder extends EventTarget {
      static isTypeSupported() { return true; }
      state: RecordingState = "inactive";
      mimeType = "audio/webm;codecs=opus";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      start() { this.state = "recording"; }
      stop() {
        this.ondataavailable?.({ data: new Blob(["recording"]) });
        this.state = "inactive";
        this.dispatchEvent(new Event("stop"));
      }
    }
    Object.defineProperty(globalThis, "MediaRecorder", { configurable: true, value: FakeMediaRecorder });
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:speech") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    class FakeAudio {
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      pause = vi.fn();
      play = () => {
        audioPlay();
        queueMicrotask(() => this.onended?.());
        return Promise.resolve();
      };
    }
    Object.defineProperty(globalThis, "Audio", { configurable: true, value: FakeAudio });
  });

  afterEach(() => {
    Reflect.deleteProperty(navigator, "mediaDevices");
  });

  it("records with MediaRecorder, converts to PCM, and writes the transcript", async () => {
    vi.mocked(transcribeSpeech).mockResolvedValue({ transcript: "数据结构", provider: "sherpa_onnx", duration_ms: 200 });
    const onTranscript = vi.fn();
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript, onNotice: vi.fn() }));

    await act(async () => result.current.toggleListening());
    expect(result.current.isListening).toBe(true);
    act(() => result.current.stopListening());

    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith("数据结构"));
    expect(transcribeSpeech).toHaveBeenCalledTimes(1);
    expect(vi.mocked(transcribeSpeech).mock.calls[0]?.[0].type).toBe("application/octet-stream");
    expect(trackStop).toHaveBeenCalled();
  });

  it("shows the safe empty-transcript reason without disabling the server", async () => {
    vi.mocked(transcribeSpeech).mockRejectedValue(new SpeechRequestError("没有识别到有效语音，请重试。", "SPEECH_EMPTY_TRANSCRIPT"));
    const onNotice = vi.fn();
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice }));

    await act(async () => result.current.toggleListening());
    act(() => result.current.stopListening());

    await waitFor(() => expect(onNotice).toHaveBeenCalledWith(
      "没有识别到有效语音，请重试。",
      "warning"
    ));
  });

  it("plays server-generated audio for read aloud", async () => {
    vi.mocked(synthesizeSpeech).mockResolvedValue(new Blob(["wav"], { type: "audio/wav" }));
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));

    await act(async () => result.current.speak("## 你好 [来源1]", "message-1"));

    expect(synthesizeSpeech).toHaveBeenCalledWith("你好");
    expect(audioPlay).toHaveBeenCalledTimes(1);
    expect(result.current.activeSpeechId).toBe(null);
  });

  it("does not call browser cloud recognition when the microphone fails", async () => {
    const cloudRecognition = vi.fn();
    Object.defineProperty(window, "webkitSpeechRecognition", { configurable: true, value: cloudRecognition });
    vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(new Error("permission denied"));
    const onNotice = vi.fn();
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice }));
    await act(async () => result.current.toggleListening());
    expect(cloudRecognition).not.toHaveBeenCalled();
    expect(onNotice).toHaveBeenCalledWith("无法使用麦克风，请检查权限后重试。", "warning");
    Reflect.deleteProperty(window, "webkitSpeechRecognition");
  });

  it("does not use browser online voices after local synthesis fails and allows retry", async () => {
    const cloudSpeak = vi.fn();
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: { speak: cloudSpeak } });
    vi.mocked(synthesizeSpeech).mockRejectedValueOnce(new Error("unavailable"))
      .mockResolvedValueOnce(new Blob(["wav"], { type: "audio/wav" }));
    const onNotice = vi.fn();
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice }));
    await act(async () => result.current.speak("测试", "test"));
    expect(cloudSpeak).not.toHaveBeenCalled();
    expect(onNotice).toHaveBeenCalledWith("本地朗读暂不可用，请稍后重试。", "warning");
    await act(async () => result.current.speak("重试", "test"));
    expect(audioPlay).toHaveBeenCalledTimes(1);
    Reflect.deleteProperty(window, "speechSynthesis");
  });

  it("starts long read-aloud in short chunks instead of waiting for the full answer", async () => {
    vi.mocked(synthesizeSpeech).mockResolvedValue(new Blob(["wav"], { type: "audio/wav" }));
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));

    await act(async () => result.current.speak("这是需要朗读的学习回答。".repeat(30), "message-long"));

    expect(vi.mocked(synthesizeSpeech).mock.calls.length).toBeGreaterThan(1);
    expect(vi.mocked(synthesizeSpeech).mock.calls[0]?.[0].length).toBeLessThanOrEqual(40);
    expect(audioPlay.mock.calls.length).toBe(vi.mocked(synthesizeSpeech).mock.calls.length);
  });
});
