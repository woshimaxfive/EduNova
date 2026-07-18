import { useCallback, useEffect, useRef, useState } from "react";

import { SpeechRequestError, synthesizeSpeech, transcribeSpeech } from "../../api/speech";

type RecognitionResultEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type RecognitionErrorEvent = { error?: string };
type Recognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
};
type RecognitionConstructor = new () => Recognition;
type SpeechWindow = Window & typeof globalThis & {
  SpeechRecognition?: RecognitionConstructor;
  webkitSpeechRecognition?: RecognitionConstructor;
};
type AudioCapture = {
  recorder: MediaRecorder;
  stream: MediaStream;
  chunks: Blob[];
  timeoutId: number;
  finishing: boolean;
};

export type SpeechNoticeTone = "info" | "success" | "warning";

export function cleanSpeechText(value: string) {
  return value
    .replace(/```[\s\S]*?```/g, " 已省略代码块。 ")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/!\[[^\]]*]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)]\([^)]*\)/g, "$1")
    .replace(/(^|\s)[#>*_`~-]+/g, " ")
    .replace(/\[(?:\d+|来源[^\]]*)]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function toPcm16k(chunks: Float32Array[], sourceRate: number): Blob {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const input = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    input.set(chunk, offset);
    offset += chunk.length;
  }
  const ratio = sourceRate / 16000;
  const outputLength = Math.max(0, Math.floor(input.length / ratio));
  const resampled = new Float32Array(outputLength);
  let peak = 0;
  for (let index = 0; index < outputLength; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.max(start + 1, Math.min(input.length, Math.floor((index + 1) * ratio)));
    let sum = 0;
    for (let cursor = start; cursor < end; cursor += 1) sum += input[cursor] ?? 0;
    const sample = Math.max(-1, Math.min(1, sum / (end - start)));
    resampled[index] = sample;
    peak = Math.max(peak, Math.abs(sample));
  }
  const gain = peak >= 0.003 && peak < 0.2 ? Math.min(8, 0.8 / peak) : 1;
  const pcm = new Int16Array(outputLength);
  for (let index = 0; index < outputLength; index += 1) {
    const sample = Math.max(-1, Math.min(1, (resampled[index] ?? 0) * gain));
    pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return new Blob([pcm.buffer], { type: "application/octet-stream" });
}

async function decodeRecordingToPcm16k(recording: Blob): Promise<Blob> {
  const context = new AudioContext();
  try {
    const buffer = await context.decodeAudioData(await recording.arrayBuffer());
    return toPcm16k([new Float32Array(buffer.getChannelData(0))], buffer.sampleRate);
  } finally {
    await context.close();
  }
}

function splitSpeechForPlayback(content: string, maxCharacters = 180): string[] {
  const sentences = content.match(/[^。！？；.!?;]+[。！？；.!?;]?/g) ?? [content];
  const chunks: string[] = [];
  let current = "";
  for (const sentence of sentences) {
    let remaining = sentence.trim();
    while (remaining.length > maxCharacters) {
      if (current) chunks.push(current);
      chunks.push(remaining.slice(0, maxCharacters));
      current = "";
      remaining = remaining.slice(maxCharacters);
    }
    if (!remaining) continue;
    if (current && current.length + remaining.length > maxCharacters) {
      chunks.push(current);
      current = remaining;
    } else {
      current += remaining;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

export function useBrowserSpeech(options: {
  onTranscript: (text: string) => void;
  onNotice: (message: string, tone: SpeechNoticeTone) => void;
}) {
  const optionsRef = useRef(options);
  const recognitionRef = useRef<Recognition | null>(null);
  const captureRef = useRef<AudioCapture | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const playbackTokenRef = useRef(0);
  const playbackResolveRef = useRef<(() => void) | null>(null);
  const serverAsrUnavailableRef = useRef(false);
  const serverTtsUnavailableRef = useRef(false);
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [activeSpeechId, setActiveSpeechId] = useState<string | null>(null);
  const [isSpeechPaused, setIsSpeechPaused] = useState(false);

  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const stopSpeaking = useCallback(() => {
    playbackTokenRef.current += 1;
    playbackResolveRef.current?.();
    playbackResolveRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = null;
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setActiveSpeechId(null);
    setIsSpeechPaused(false);
  }, []);

  const pauseOrResumeSpeaking = useCallback(() => {
    if (!activeSpeechId || typeof window === "undefined") return;
    if (audioRef.current) {
      if (audioRef.current.paused) {
        void audioRef.current.play().then(() => setIsSpeechPaused(false)).catch(() => {
          optionsRef.current.onNotice("朗读继续播放失败，请重新朗读。", "warning");
          stopSpeaking();
        });
      } else {
        audioRef.current.pause();
        setIsSpeechPaused(true);
      }
      return;
    }
    if ("speechSynthesis" in window) {
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
        setIsSpeechPaused(false);
      } else {
        window.speechSynthesis.pause();
        setIsSpeechPaused(true);
      }
    }
  }, [activeSpeechId, stopSpeaking]);

  const startBrowserRecognition = useCallback(() => {
    if (typeof window === "undefined") return;
    const speechWindow = window as SpeechWindow;
    const Constructor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Constructor) {
      optionsRef.current.onNotice("当前浏览器不支持语音输入，请使用键盘输入。", "warning");
      return;
    }
    const recognition = new Constructor();
    recognition.lang = "zh-CN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const text = Array.from(event.results).map((result) => result[0]?.transcript ?? "").join("").trim();
      if (text) optionsRef.current.onTranscript(text);
    };
    recognition.onerror = () => {
      setIsListening(false);
      optionsRef.current.onNotice("语音输入暂时不可用，请改用键盘输入。", "warning");
    };
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();
  }, []);

  const finishServerRecording = useCallback(async () => {
    const capture = captureRef.current;
    if (!capture || capture.finishing) return;
    capture.finishing = true;
    captureRef.current = null;
    window.clearTimeout(capture.timeoutId);
    setIsListening(false);
    try {
      if (capture.recorder.state !== "inactive") {
        await new Promise<void>((resolve) => {
          capture.recorder.addEventListener("stop", () => resolve(), { once: true });
          capture.recorder.stop();
        });
      }
      capture.stream.getTracks().forEach((track) => track.stop());
      const recording = new Blob(capture.chunks, { type: capture.recorder.mimeType });
      const audio = await decodeRecordingToPcm16k(recording);
      if (audio.size < 3200) {
        optionsRef.current.onNotice("录音时间太短，请重新说一遍。", "warning");
        return;
      }
      setIsTranscribing(true);
      const result = await transcribeSpeech(audio);
      optionsRef.current.onTranscript(result.transcript);
    } catch (error) {
      const canRetryServer = error instanceof SpeechRequestError
        && ["SPEECH_EMPTY_TRANSCRIPT", "SPEECH_INVALID_AUDIO"].includes(error.code);
      serverAsrUnavailableRef.current = !canRetryServer;
      const message = error instanceof SpeechRequestError
        ? error.message
        : "录音处理失败，请重新录制。";
      optionsRef.current.onNotice(
        canRetryServer ? message : `${message} 再次点击将使用浏览器识别。`,
        "warning"
      );
    } finally {
      capture.stream.getTracks().forEach((track) => track.stop());
      setIsTranscribing(false);
    }
  }, []);

  const stopListening = useCallback(() => {
    if (captureRef.current) {
      void finishServerRecording();
      return;
    }
    recognitionRef.current?.stop();
    setIsListening(false);
  }, [finishServerRecording]);

  const toggleListening = useCallback(async () => {
    if (isListening) {
      stopListening();
      return;
    }
    if (isTranscribing) return;
    const canCapture = typeof navigator !== "undefined"
      && Boolean(navigator.mediaDevices?.getUserMedia)
      && typeof AudioContext !== "undefined"
      && typeof MediaRecorder !== "undefined";
    if (!canCapture || serverAsrUnavailableRef.current) {
      startBrowserRecognition();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      const preferredType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = preferredType ? new MediaRecorder(stream, { mimeType: preferredType }) : new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      const timeoutId = window.setTimeout(() => void finishServerRecording(), 60000);
      captureRef.current = { recorder, stream, chunks, timeoutId, finishing: false };
      recorder.start(250);
      setIsListening(true);
    } catch {
      serverAsrUnavailableRef.current = true;
      startBrowserRecognition();
    }
  }, [finishServerRecording, isListening, isTranscribing, startBrowserRecognition, stopListening]);

  const speakWithBrowser = useCallback((content: string, speechId: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
      optionsRef.current.onNotice("当前浏览器不支持朗读回答。", "warning");
      setActiveSpeechId(null);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(content);
    utterance.lang = "zh-CN";
    utterance.rate = 0.95;
    const voices = typeof window.speechSynthesis.getVoices === "function"
      ? window.speechSynthesis.getVoices()
      : [];
    utterance.voice = voices.find((voice) => /xiaoxiao|yunxi|natural|online/i.test(voice.name) && voice.lang.startsWith("zh"))
      ?? voices.find((voice) => voice.lang.startsWith("zh"))
      ?? null;
    utterance.onend = () => {
      setActiveSpeechId(null);
      setIsSpeechPaused(false);
    };
    utterance.onerror = () => {
      setActiveSpeechId(null);
      setIsSpeechPaused(false);
      setIsSpeechPaused(false);
    };
    setActiveSpeechId(speechId);
    setIsSpeechPaused(false);
    window.speechSynthesis.speak(utterance);
  }, []);

  const speak = useCallback(async (content: string, speechId: string) => {
    const cleaned = cleanSpeechText(content);
    if (!cleaned) return;
    stopSpeaking();
    if (serverTtsUnavailableRef.current) {
      speakWithBrowser(cleaned, speechId);
      return;
    }
    const parts = splitSpeechForPlayback(cleaned);
    const playbackToken = ++playbackTokenRef.current;
    setActiveSpeechId(speechId);
    setIsSpeechPaused(false);
    let partIndex = 0;
    try {
      const requestPart = async (text: string) => {
        try {
          return { blob: await synthesizeSpeech(text), error: null };
        } catch (error) {
          return { blob: null, error };
        }
      };
      let pending = requestPart(parts[0] ?? cleaned);
      for (partIndex = 0; partIndex < parts.length; partIndex += 1) {
        const result = await pending;
        if (result.error || !result.blob) throw result.error ?? new Error("speech synthesis returned no audio");
        const blob = result.blob;
        if (playbackToken !== playbackTokenRef.current) return;
        if (partIndex + 1 < parts.length) pending = requestPart(parts[partIndex + 1] ?? "");
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;
        audioUrlRef.current = url;
        await new Promise<void>((resolve, reject) => {
          playbackResolveRef.current = resolve;
          audio.onended = () => resolve();
          audio.onerror = () => reject(new Error("audio playback failed"));
          void audio.play().catch(reject);
        });
        playbackResolveRef.current = null;
        audio.pause();
        URL.revokeObjectURL(url);
        audioRef.current = null;
        audioUrlRef.current = null;
        if (playbackToken !== playbackTokenRef.current) return;
      }
      setActiveSpeechId(null);
    } catch {
      serverTtsUnavailableRef.current = true;
      stopSpeaking();
      speakWithBrowser(parts.slice(partIndex).join("") || cleaned, speechId);
    }
  }, [speakWithBrowser, stopSpeaking]);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    const capture = captureRef.current;
    if (capture) {
      window.clearTimeout(capture.timeoutId);
      if (capture.recorder.state !== "inactive") capture.recorder.stop();
      capture.stream.getTracks().forEach((track) => track.stop());
    }
    audioRef.current?.pause();
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  return {
    isListening,
    isTranscribing,
    activeSpeechId,
    isSpeechPaused,
    toggleListening,
    stopListening,
    speak,
    stopSpeaking,
    pauseOrResumeSpeaking
  };
}
