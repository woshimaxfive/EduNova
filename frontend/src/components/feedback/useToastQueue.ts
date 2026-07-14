import { useState } from "react";

import { type FeedbackTone } from "./InlineFeedback";
import { type ToastMessage } from "./ToastStack";

export function useToastQueue() {
  const [toast, setToast] = useState<ToastMessage | null>(null);

  function dismissToast() {
    setToast(null);
  }

  function showToast(message: string, tone: FeedbackTone = "info") {
    setToast({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      message,
      tone
    });
  }

  return { toast, showToast, dismissToast };
}
