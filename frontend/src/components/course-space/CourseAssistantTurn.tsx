import { type ReactNode } from "react";

import { MarkdownMessage } from "../feedback/MarkdownMessage";

type CourseAssistantTurnProps = {
  content: string;
  actions?: ReactNode;
  detail?: ReactNode;
};

export function CourseAssistantTurn({ content, actions, detail }: CourseAssistantTurnProps) {
  return (
    <article className="course-message assistant course-assistant-turn">
      <MarkdownMessage content={content} />
      {actions}
      {detail ? <div className="course-turn-detail">{detail}</div> : null}
    </article>
  );
}
