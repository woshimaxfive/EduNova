import { type ReactNode } from "react";

import { MarkdownMessage } from "../feedback/MarkdownMessage";

type CourseAssistantTurnProps = {
  messageId?: string;
  content: string;
  progress?: ReactNode;
  actions?: ReactNode;
  detail?: ReactNode;
};

export function CourseAssistantTurn({ messageId, content, progress, actions, detail }: CourseAssistantTurnProps) {
  return (
    <article id={messageId ? `course-message-${messageId}` : undefined} className="course-message assistant course-assistant-turn">
      {progress}
      {content ? <MarkdownMessage content={content} /> : null}
      {actions}
      {detail ? <div className="course-turn-detail">{detail}</div> : null}
    </article>
  );
}
