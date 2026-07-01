import { useState } from "react";

export type ActionNoticeTone = "info" | "success" | "warning";

export type ActionNoticeState = {
  message: string;
  tone: ActionNoticeTone;
};

export function useActionNotice(initialNotice: ActionNoticeState | null = null) {
  const [notice, setNotice] = useState<ActionNoticeState | null>(initialNotice);

  function showNotice(message: string, tone: ActionNoticeTone = "info") {
    setNotice({ message, tone });
  }

  function clearNotice() {
    setNotice(null);
  }

  return { notice, showNotice, clearNotice };
}
