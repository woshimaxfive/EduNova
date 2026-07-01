import { type ActionNoticeState } from "./useActionNotice";

type ActionNoticeProps = {
  notice: ActionNoticeState | null;
  className?: string;
};

export function ActionNotice({ notice, className }: ActionNoticeProps) {
  if (!notice) {
    return null;
  }

  return (
    <p className={["action-notice", notice.tone, className].filter(Boolean).join(" ")} role="status">
      {notice.message}
    </p>
  );
}
