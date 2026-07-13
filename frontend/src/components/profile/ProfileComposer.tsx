import { PaperPlaneTilt, Sparkle } from "@phosphor-icons/react";
import type { KeyboardEvent, RefObject } from "react";

type ProfileComposerProps = {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  nextQuestion: string;
  isUpdating: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ProfileComposer({ inputRef, value, nextQuestion, isUpdating, onChange, onSubmit }: ProfileComposerProps) {
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
        <span>下一问：{nextQuestion}</span>
      </div>
      <div className="profile-composer-box">
        <textarea
          ref={inputRef}
          rows={2}
          value={value}
          aria-label="画像问题回答"
          placeholder="告诉 EduNova 你的目标、基础或最近遇到的困难"
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
