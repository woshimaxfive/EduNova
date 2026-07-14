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
  return (
    <Toast.Provider duration={3600} swipeDirection="right">
      <Toast.Root
        key={toast?.id ?? "empty-toast"}
        className={`toast-message toast-${toast?.tone ?? "info"}`}
        open={toast !== null}
        onOpenChange={(open) => { if (!open) onDismiss(); }}
        type={toast?.tone === "warning" ? "foreground" : "background"}
        role="alert"
      >
        <Toast.Description>{toast?.message}</Toast.Description>
        <Toast.Close asChild>
          <button type="button" aria-label="关闭提示"><X size={15} aria-hidden="true" /></button>
        </Toast.Close>
      </Toast.Root>
      <Toast.Viewport className="toast-stack" aria-label="操作反馈" />
    </Toast.Provider>
  );
}
import * as Toast from "@radix-ui/react-toast";
