import { useCallback, useEffect, useRef, useState } from "react";

import { synthesizeSpeech, transcribeSpeech } from "../../api/speech";

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
  context: AudioContext;
  stream: MediaStream;
  source: MediaStreamAudioSourceNode;
  processor: ScriptProcessorNode;
  chunks: Float32Array[];
  timeoutId: number;
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
  const pcm = new Int16Array(outputLength);
  for (let index = 0; index < outputLength; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.max(start + 1, Math.min(input.length, Math.floor((index + 1) * ratio)));
    let sum = 0;
    for (let cursor = start; cursor < end; cursor += 1) sum += input[cursor] ?? 0;
    const sample = Math.max(-1, Math.min(1, sum / (end - start)));
    pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return new Blob([pcm.buffer], { type: "application/octet-stream" });
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
  const serverAsrUnavailableRef = useRef(false);
  const serverTtsUnavailableRef = useRef(false);
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [activeSpeechId, setActiveSpeechId] = useState<string | null>(null);

  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const stopSpeaking = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = null;
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setActiveSpeechId(null);
  }, []);

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
    if (!capture) return;
    captureRef.current = null;
    window.clearTimeout(capture.timeoutId);
    capture.processor.disconnect();
    capture.source.disconnect();
    capture.stream.getTracks().forEach((track) => track.stop());
    await capture.context.close();
    setIsListening(false);
    const audio = toPcm16k(capture.chunks, capture.context.sampleRate);
    if (audio.size < 3200) {
      optionsRef.current.onNotice("录音时间太短，请重新说一遍。", "warning");
      return;
    }
    setIsTranscribing(true);
    try {
      const result = await transcribeSpeech(audio);
      optionsRef.current.onTranscript(result.transcript);
    } catch {
      serverAsrUnavailableRef.current = true;
      optionsRef.current.onNotice("讯飞语音识别暂时不可用，下次将切换浏览器识别。", "warning");
    } finally {
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
      && typeof AudioContext !== "undefined";
    if (!canCapture || serverAsrUnavailableRef.current) {
      startBrowserRecognition();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      const context = new AudioContext();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const chunks: Float32Array[] = [];
      processor.onaudioprocess = (event) => chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      source.connect(processor);
      processor.connect(context.destination);
      const timeoutId = window.setTimeout(() => void finishServerRecording(), 60000);
      captureRef.current = { context, stream, source, processor, chunks, timeoutId };
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
    utterance.onend = () => setActiveSpeechId(null);
    utterance.onerror = () => setActiveSpeechId(null);
    setActiveSpeechId(speechId);
    window.speechSynthesis.speak(utterance);
  }, []);

  const speak = useCallback(async (content: string, speechId: string) => {
    const cleaned = cleanSpeechText(content);
    if (!cleaned) return;
    stopSpeaking();
    const canUseServer = typeof navigator !== "undefined" && Boolean(navigator.mediaDevices);
    if (!canUseServer || serverTtsUnavailableRef.current) {
      speakWithBrowser(cleaned, speechId);
      return;
    }
    setActiveSpeechId(speechId);
    try {
      const blob = await synthesizeSpeech(cleaned);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audioUrlRef.current = url;
      audio.onended = stopSpeaking;
      audio.onerror = () => {
        serverTtsUnavailableRef.current = true;
        stopSpeaking();
        speakWithBrowser(cleaned, speechId);
      };
      await audio.play();
    } catch {
      serverTtsUnavailableRef.current = true;
      stopSpeaking();
      speakWithBrowser(cleaned, speechId);
    }
  }, [speakWithBrowser, stopSpeaking]);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    const capture = captureRef.current;
    if (capture) {
      window.clearTimeout(capture.timeoutId);
      capture.processor.disconnect();
      capture.source.disconnect();
      capture.stream.getTracks().forEach((track) => track.stop());
      void capture.context.close();
    }
    audioRef.current?.pause();
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  return { isListening, isTranscribing, activeSpeechId, toggleListening, stopListening, speak, stopSpeaking };
}
