import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SpeechRequestError, transcribeSpeech } from "../../api/speech";
import { useBrowserSpeech } from "./useBrowserSpeech";

vi.mock("../../api/speech", () => ({
  SpeechRequestError: class SpeechRequestError extends Error {
    constructor(message: string, readonly code = "SPEECH_PROVIDER_ERROR") {
      super(message);
    }
  },
  transcribeSpeech: vi.fn()
}));

describe("useBrowserSpeech server enhancement", () => {
  const trackStop = vi.fn();
  const localVoice = { name: "Local Chinese", lang: "zh-CN", localService: true } as SpeechSynthesisVoice;
  let voices: SpeechSynthesisVoice[];
  let synthesis: SpeechSynthesis;
  let utterances: SpeechSynthesisUtterance[];
  let autoEnd: boolean;

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
    voices = [localVoice];
    utterances = [];
    autoEnd = true;
    synthesis = Object.assign(new EventTarget(), {
      getVoices: () => voices, cancel: vi.fn(), pause: vi.fn(), resume: vi.fn(),
      speak: vi.fn((u: SpeechSynthesisUtterance) => {
        utterances.push(u);
        if (autoEnd) queueMicrotask(() => u.onend?.({} as SpeechSynthesisEvent));
      })
    }) as unknown as SpeechSynthesis;
    vi.stubGlobal("speechSynthesis", synthesis);
    vi.stubGlobal("SpeechSynthesisUtterance", class {
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(public text: string) {}
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(navigator, "mediaDevices");
    vi.unstubAllGlobals();
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

  it("reads with an explicitly local Chinese voice", async () => {
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));
    await act(async () => result.current.speak("## 你好 [来源1]", "one"));
    expect(utterances[0]?.text).toBe("你好");
    expect(utterances[0]?.voice).toBe(localVoice);
    expect(result.current.activeSpeechId).toBeNull();
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

  it("rejects online-only voices without sending text", async () => {
    voices = [{ ...localVoice, localService: false }];
    const notice = vi.fn();
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: notice }));
    await act(async () => result.current.speak("测试", "one"));
    expect(synthesis.speak).not.toHaveBeenCalled();
    expect(notice).toHaveBeenCalledWith(expect.stringContaining("未检测到本地中文声音"), "warning");
  });

  it("waits for asynchronous voiceschanged", async () => {
    voices = [];
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));
    await act(async () => {
      const pending = result.current.speak("测试", "one");
      voices = [localVoice];
      synthesis.dispatchEvent(new Event("voiceschanged"));
      await pending;
    });
    expect(utterances[0]?.voice).toBe(localVoice);
  });

  it("pauses, resumes and stops without continuing queued segments", async () => {
    autoEnd = false;
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));
    let pending: Promise<void>;
    act(() => { pending = result.current.speak("学习回答。".repeat(100), "long"); });
    act(() => result.current.pauseOrResumeSpeaking());
    expect(synthesis.pause).toHaveBeenCalledOnce();
    expect(result.current.isSpeechPaused).toBe(true);
    act(() => result.current.pauseOrResumeSpeaking());
    expect(synthesis.resume).toHaveBeenCalledOnce();
    await act(async () => { result.current.stopSpeaking(); await pending; });
    expect(utterances).toHaveLength(1);
    expect(result.current.activeSpeechId).toBeNull();
  });

  it("finishes long text in ordered bounded segments", async () => {
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));
    const text = "这是学习回答。".repeat(60);
    await act(async () => result.current.speak(text, "long"));
    expect(utterances.length).toBeGreaterThan(1);
    expect(utterances.every(u => u.text.length <= 180 && u.voice === localVoice)).toBe(true);
    expect(utterances.map(u => u.text).join("")).toBe(text);
  });

  it("clears native paused state before starting another answer", async () => {
    Object.defineProperty(synthesis, "paused", { configurable: true, value: true });
    const { result } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));
    await act(async () => result.current.speak("新回答", "next"));
    expect(synthesis.resume).toHaveBeenCalled();
    expect(utterances[0]?.text).toBe("新回答");
  });

  it("cancels pending voice discovery on unmount", async () => {
    voices = [];
    const { result, unmount } = renderHook(() => useBrowserSpeech({ onTranscript: vi.fn(), onNotice: vi.fn() }));
    const pending = result.current.speak("测试", "one");
    unmount();
    voices = [localVoice];
    synthesis.dispatchEvent(new Event("voiceschanged"));
    await pending;
    expect(synthesis.speak).not.toHaveBeenCalled();
  });
});
