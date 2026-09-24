import { useCallback, useEffect, useRef, useState } from "react";

import { SpeechRequestError, transcribeSpeech } from "../../api/speech";

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
  const captureRef = useRef<AudioCapture | null>(null);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const playbackTokenRef = useRef(0);
  const playbackResolveRef = useRef<(() => void) | null>(null);
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
    window.speechSynthesis?.cancel();
    if (window.speechSynthesis?.paused) window.speechSynthesis.resume();
    utteranceRef.current = null;
    setActiveSpeechId(null);
    setIsSpeechPaused(false);
  }, []);

  const pauseOrResumeSpeaking = useCallback(() => {
    if (!activeSpeechId || typeof window === "undefined") return;
    const synthesis = window.speechSynthesis;
    if (!synthesis || !utteranceRef.current) return;
    if (isSpeechPaused) synthesis.resume();
    else synthesis.pause();
    setIsSpeechPaused(!isSpeechPaused);
  }, [activeSpeechId, isSpeechPaused]);

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
      const message = error instanceof SpeechRequestError
        ? error.message
        : "录音处理失败，请重新录制。";
      optionsRef.current.onNotice(message, "warning");
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
    if (!canCapture) {
      optionsRef.current.onNotice("当前页面无法录音，请使用HTTPS或本机地址并允许麦克风权限。", "warning");
      return;
    }
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
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
      stream?.getTracks().forEach((track) => track.stop());
      if (captureRef.current) window.clearTimeout(captureRef.current.timeoutId);
      captureRef.current = null;
      optionsRef.current.onNotice("无法使用麦克风，请检查权限后重试。", "warning");
    }
  }, [finishServerRecording, isListening, isTranscribing, stopListening]);

  const speak = useCallback(async (content: string, speechId: string) => {
    const cleaned = cleanSpeechText(content);
    if (!cleaned) return;
    stopSpeaking();
    const synthesis = window.speechSynthesis;
    if (!synthesis || typeof SpeechSynthesisUtterance === "undefined") {
      optionsRef.current.onNotice("当前浏览器不支持本地朗读，请使用 Chrome 或 Edge 并安装中文语音。", "warning");
      return;
    }
    const token = playbackTokenRef.current;
    const chooseVoice = () => {
      const local = synthesis.getVoices().filter((voice) => voice.localService && /^zh[-_]/i.test(voice.lang));
      return local.find((voice) => /^zh[-_]CN$/i.test(voice.lang)) ?? local[0];
    };
    let voice = chooseVoice();
    if (!voice) {
      // Voice lists may arrive asynchronously. Never select a remote/default voice.
      await new Promise<void>((resolve) => {
        const finish = () => {
          window.clearTimeout(timeout);
          synthesis.removeEventListener("voiceschanged", changed);
          resolve();
        };
        const changed = () => { if (chooseVoice()) finish(); };
        const timeout = window.setTimeout(finish, 1500);
        synthesis.addEventListener("voiceschanged", changed);
        playbackResolveRef.current = finish;
        changed();
      });
      if (token !== playbackTokenRef.current) return;
      playbackResolveRef.current = null;
      voice = chooseVoice();
    }
    if (!voice) {
      optionsRef.current.onNotice("未检测到本地中文声音，请先在系统中安装中文语音；不会使用在线声音。", "warning");
      return;
    }
    setActiveSpeechId(speechId);
    setIsSpeechPaused(false);
    try {
      for (const part of splitSpeechForPlayback(cleaned)) {
        if (token !== playbackTokenRef.current) return;
        const utterance = new SpeechSynthesisUtterance(part);
        utterance.voice = voice;
        utterance.lang = voice.lang;
        utterance.rate = 1;
        utteranceRef.current = utterance;
        await new Promise<void>((resolve, reject) => {
          playbackResolveRef.current = resolve;
          utterance.onend = () => resolve();
          utterance.onerror = () => reject(new Error("Local speech playback failed"));
          synthesis.speak(utterance);
        });
        if (token !== playbackTokenRef.current) return;
        playbackResolveRef.current = null;
      }
      utteranceRef.current = null;
      setActiveSpeechId(null);
      setIsSpeechPaused(false);
    } catch {
      if (token !== playbackTokenRef.current) return;
      stopSpeaking();
      optionsRef.current.onNotice("本地朗读暂不可用，请稍后重试。", "warning");
    }
  }, [stopSpeaking]);

  useEffect(() => () => {
    const capture = captureRef.current;
    if (capture) {
      window.clearTimeout(capture.timeoutId);
      if (capture.recorder.state !== "inactive") capture.recorder.stop();
      capture.stream.getTracks().forEach((track) => track.stop());
    }
    playbackTokenRef.current += 1;
    playbackResolveRef.current?.();
    window.speechSynthesis?.cancel();
    utteranceRef.current = null;
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
