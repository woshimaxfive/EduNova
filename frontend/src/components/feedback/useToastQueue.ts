import { useRef, useState } from "react";

import { type FeedbackTone } from "./InlineFeedback";
import { type ToastMessage } from "./ToastStack";

const TOAST_DURATION_MS = 3600;

export function useToastQueue() {
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const timeoutRef = useRef<number | null>(null);

  function clearTimer() {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }

  function dismissToast() {
    clearTimer();
    setToast(null);
  }

  function showToast(message: string, tone: FeedbackTone = "info") {
    clearTimer();
    setToast({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      message,
      tone
    });
    timeoutRef.current = window.setTimeout(() => {
      setToast(null);
      timeoutRef.current = null;
    }, TOAST_DURATION_MS);
  }

  return { toast, showToast, dismissToast };
}
