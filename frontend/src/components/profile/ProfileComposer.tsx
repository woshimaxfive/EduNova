import { PaperPlaneTilt, Sparkle } from "@phosphor-icons/react";
import type { KeyboardEvent, RefObject } from "react";

import { profileQuestionGuidance, type ProfileDimensionKey } from "../../features/profile/profileViewModel";

type ProfileComposerProps = {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  nextQuestion: string;
  nextQuestionDimension?: ProfileDimensionKey | null;
  isUpdating: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ProfileComposer({ inputRef, value, nextQuestion, nextQuestionDimension, isUpdating, onChange, onSubmit }: ProfileComposerProps) {
  const questionGuidance = profileQuestionGuidance(nextQuestionDimension);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (value.trim() && !isUpdating) onSubmit();
    }
  }

  return (
    <footer className="profile-composer">
      <div className="profile-next-question">
        <Sparkle size={16} weight="duotone" aria-hidden="true" />
        <span>
          <small>建议补充{questionGuidance ? ` · ${questionGuidance.label}` : ""}</small>
          <strong>{nextQuestion}</strong>
          <em>{questionGuidance?.guidance ?? "用自己的话描述当前情况即可，不需要使用专业术语。"}</em>
          <span className="profile-question-examples">
            可以说：{questionGuidance?.examples ?? "当前目标、已有基础、学习困难或学习安排。"}
          </span>
        </span>
      </div>
      <div className="profile-composer-box">
        <textarea
          ref={inputRef}
          rows={2}
          value={value}
          aria-label="画像问题回答"
          placeholder="用自己的话回答即可"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button type="button" aria-label="更新画像" disabled={!value.trim() || isUpdating} onClick={onSubmit}>
          <PaperPlaneTilt size={18} weight="fill" aria-hidden="true" />
          <span>{isUpdating ? "正在更新" : "发送"}</span>
        </button>
      </div>
    </footer>
  );
}
