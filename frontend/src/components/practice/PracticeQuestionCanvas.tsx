import { CaretDown, CaretUp, CheckCircle, WarningCircle } from "@phosphor-icons/react";

import { type PracticeAnswerResult, type PracticeQuestion } from "../../api/practice";
import { difficultyLabel } from "../../features/practice/practiceViewModel";

type PracticeQuestionCanvasProps = {
  question: PracticeQuestion;
  index: number;
  total: number;
  value: string;
  feedback: PracticeAnswerResult | null;
  completed: boolean;
  reviewExpanded: boolean;
  onAnswer: (value: string) => void;
  onToggleReview: () => void;
};

function answerParts(value: string) {
  try {
    const parsed = JSON.parse(value) as unknown;
    if (Array.isArray(parsed) && parsed.every((item) => typeof item === "string")) {
      return parsed.map((item) => item.trim()).filter(Boolean);
    }
  } catch {
    // Older drafts stored multiple selections as comma-separated text.
  }
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function correctParts(question: PracticeQuestion) {
  if (Array.isArray(question.correct_answer)) return question.correct_answer;
  return question.correct_answer ? [question.correct_answer] : [];
}

function optionId(question: PracticeQuestion, index: number) {
  return question.option_ids?.[index] ?? question.options[index] ?? String.fromCharCode(65 + index);
}

function optionLabel(question: PracticeQuestion, value: string) {
  const byId = question.option_ids?.findIndex((item) => item === value) ?? -1;
  return byId >= 0 ? question.options[byId] ?? value : value;
}

export function PracticeQuestionCanvas({
  question,
  index,
  total,
  value,
  feedback,
  completed,
  reviewExpanded,
  onAnswer,
  onToggleReview
}: PracticeQuestionCanvasProps) {
  const selected = answerParts(value);
  const correct = correctParts(question);
  const isChoice = question.question_type !== "short_answer";

  function selectOption(option: string) {
    if (completed) return;
    if (question.question_type === "single_choice") {
      onAnswer(option);
      return;
    }
    const next = selected.includes(option)
      ? selected.filter((item) => item !== option)
      : [...selected, option];
    onAnswer(JSON.stringify(next));
  }

  return (
    <article className="practice-question-canvas" aria-label={`第 ${index + 1} 题`}>
      <header>
        <div>
          <span>第 {index + 1} 题 / 共 {total} 题</span>
          <strong>{question.knowledge_point_title || "课程知识点"}</strong>
        </div>
        <div className="practice-question-tags">
          <span>{question.question_type === "single_choice" ? "单选" : question.question_type === "multiple_choice" ? "多选" : "简答"}</span>
          <span>{difficultyLabel(question.difficulty)}</span>
        </div>
      </header>

      <h2>{question.prompt}</h2>

      {isChoice ? (
        <div className="practice-choice-list" role="group" aria-label="答案选项">
          {question.options.map((option, optionIndex) => {
            const id = optionId(question, optionIndex);
            const isSelected = selected.includes(id) || selected.includes(option);
            const isCorrectOption = completed && (correct.includes(option) || (feedback?.is_correct === true && isSelected));
            const isWrongSelection = completed && isSelected && !isCorrectOption;
            return (
              <button
                className={`${isSelected ? "selected" : ""}${isCorrectOption ? " correct" : ""}${isWrongSelection ? " wrong" : ""}`}
                type="button"
                key={id}
                aria-pressed={isSelected}
                disabled={completed}
                onClick={() => selectOption(id)}
              >
                <span>{String.fromCharCode(65 + optionIndex)}</span>
                <strong>{option}</strong>
                {isCorrectOption ? <CheckCircle size={18} weight="fill" aria-label="正确答案" /> : null}
                {isWrongSelection ? <WarningCircle size={18} weight="fill" aria-label="错误选择" /> : null}
              </button>
            );
          })}
        </div>
      ) : (
        <label className="practice-short-answer">
          <span>写下答案或推导过程</span>
          <textarea
            rows={8}
            aria-label={`${question.id} 作答区`}
            value={value}
            onChange={(event) => onAnswer(event.target.value)}
            placeholder="先写出关键概念，再说明它们之间的关系。"
            disabled={completed}
          />
        </label>
      )}

      {completed && feedback ? (
        <section className={feedback.is_correct === null ? "practice-review pending" : feedback.is_correct ? "practice-review correct" : "practice-review wrong"} aria-label={`${question.id} 批改结果`}>
          <button type="button" aria-expanded={reviewExpanded} onClick={onToggleReview}>
            <span>
              {feedback.is_correct === true ? <CheckCircle size={22} weight="duotone" aria-hidden="true" /> : feedback.is_correct === false ? <WarningCircle size={22} weight="duotone" aria-hidden="true" /> : null}
              <span>
                <strong>{feedback.feedback.unanswered ? "本题未作答" : feedback.is_correct === null ? "简答题暂未评分" : `${feedback.is_correct ? "回答正确" : "需要复习"} · 得分 ${feedback.feedback.score}`}</strong>
                <small>{feedback.feedback.message}</small>
              </span>
            </span>
            {reviewExpanded ? <CaretUp size={17} aria-hidden="true" /> : <CaretDown size={17} aria-hidden="true" />}
          </button>
          {reviewExpanded ? (
            <div className="practice-review-detail">
              <dl>
                <div><dt>你的答案</dt><dd>{answerParts(feedback.answer_text ?? "").map((item) => optionLabel(question, item)).join("、") || "未作答"}</dd></div>
                {correct.length > 0 ? <div><dt>正确答案</dt><dd>{correct.join("、")}</dd></div> : null}
              </dl>
              <div>
                <strong>解析</strong>
                <p>{feedback.feedback.explanation || question.explanation || "暂无补充解析。"}</p>
              </div>
              {feedback.feedback.diagnosis ? (
                <div className="practice-review-diagnosis">
                  <strong>错因与复习动作</strong>
                  <p>{feedback.feedback.diagnosis.misconception}</p>
                  {feedback.feedback.diagnosis.missing_concepts.length > 0 ? (
                    <div>{feedback.feedback.diagnosis.missing_concepts.map((concept) => <span key={concept}>{concept}</span>)}</div>
                  ) : null}
                  <small>{feedback.feedback.diagnosis.recommended_action}</small>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}
    </article>
  );
}
