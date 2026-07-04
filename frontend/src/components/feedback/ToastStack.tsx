import { X } from "@phosphor-icons/react";

import { type FeedbackTone } from "./InlineFeedback";

export type ToastMessage = {
  id: string;
  message: string;
  tone: FeedbackTone;
};

type ToastStackProps = {
  toast: ToastMessage | null;
  onDismiss: () => void;
};

export function ToastStack({ toast, onDismiss }: ToastStackProps) {
  if (!toast) {
    return null;
  }

  return (
    <div className="toast-stack" aria-live="polite" aria-label="操作反馈">
      <div className={`toast-message toast-${toast.tone}`} role="alert">
        <span>{toast.message}</span>
        <button type="button" aria-label="关闭提示" onClick={onDismiss}>
          <X size={15} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
