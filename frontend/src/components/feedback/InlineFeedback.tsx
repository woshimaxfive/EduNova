export type FeedbackTone = "info" | "success" | "warning";

type InlineFeedbackProps = {
  message: string | null;
  tone?: FeedbackTone;
  className?: string;
};

export function InlineFeedback({ message, tone = "info", className }: InlineFeedbackProps) {
  if (!message) {
    return null;
  }

  return (
    <p className={["inline-feedback", `inline-feedback-${tone}`, className].filter(Boolean).join(" ")} role={tone === "warning" ? "alert" : "note"}>
      {message}
    </p>
  );
}
