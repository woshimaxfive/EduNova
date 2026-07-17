import { useCallback, useEffect, useRef, useState } from "react";

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

export function useBrowserSpeech(options: {
  onTranscript: (text: string) => void;
  onNotice: (message: string, tone: SpeechNoticeTone) => void;
}) {
  const recognitionRef = useRef<Recognition | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [activeSpeechId, setActiveSpeechId] = useState<string | null>(null);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setActiveSpeechId(null);
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
      return;
    }
    if (typeof window === "undefined") return;
    const speechWindow = window as SpeechWindow;
    const Constructor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Constructor) {
      options.onNotice("当前浏览器不支持语音输入，请使用键盘输入。", "warning");
      return;
    }
    const recognition = new Constructor();
    recognition.lang = "zh-CN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const text = Array.from(event.results).map((result) => result[0]?.transcript ?? "").join("").trim();
      if (text) {
        options.onTranscript(text);
      }
    };
    recognition.onerror = () => {
      setIsListening(false);
      options.onNotice("语音输入暂时不可用，请改用键盘输入。", "warning");
    };
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();
  }, [isListening, options, stopListening]);

  const speak = useCallback((content: string, speechId: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
      options.onNotice("当前浏览器不支持朗读回答。", "warning");
      return;
    }
    stopSpeaking();
    const utterance = new SpeechSynthesisUtterance(cleanSpeechText(content));
    utterance.lang = "zh-CN";
    utterance.onend = () => setActiveSpeechId(null);
    utterance.onerror = () => setActiveSpeechId(null);
    setActiveSpeechId(speechId);
    window.speechSynthesis.speak(utterance);
  }, [options, stopSpeaking]);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  return { isListening, activeSpeechId, toggleListening, stopListening, speak, stopSpeaking };
}
