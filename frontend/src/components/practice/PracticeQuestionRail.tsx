import { Check, Circle, X } from "@phosphor-icons/react";

import { type PracticeAnswerResult, type PracticeQuestion } from "../../api/practice";
import { isAnswered } from "../../features/practice/practiceViewModel";

type PracticeQuestionRailProps = {
  questions: PracticeQuestion[];
  answers: Record<string, string>;
  evaluatedAnswers: PracticeAnswerResult[];
  activeQuestionId: string | null;
  completed: boolean;
  onSelect: (questionId: string) => void;
};

export function PracticeQuestionRail({
  questions,
  answers,
  evaluatedAnswers,
  activeQuestionId,
  completed,
  onSelect
}: PracticeQuestionRailProps) {
  const evaluatedByQuestion = new Map(evaluatedAnswers.map((answer) => [answer.question_id, answer]));

  return (
    <aside className="practice-question-rail" aria-label="题目导航">
      <div className="practice-rail-heading">
        <span>题目</span>
        <strong>{questions.length}</strong>
      </div>
      <nav>
        {questions.map((question, index) => {
          const evaluated = evaluatedByQuestion.get(question.id);
          const answered = isAnswered(answers[question.id]);
          const status = completed
            ? evaluated?.is_correct === true
              ? "correct"
              : evaluated?.is_correct === false
                ? "wrong"
                : "pending"
            : answered
              ? "answered"
              : "unanswered";
          const isActive = question.id === activeQuestionId;
          return (
            <button
              className={`${status}${isActive ? " active" : ""}`}
              type="button"
              key={question.id}
              aria-current={isActive ? "step" : undefined}
              aria-label={`第 ${index + 1} 题，${completed ? (status === "correct" ? "正确" : status === "wrong" ? "错误" : "暂未评分") : (answered ? "已答" : "未答")}`}
              onClick={() => onSelect(question.id)}
            >
              <span>{index + 1}</span>
              {status === "correct" ? <Check size={14} weight="bold" aria-hidden="true" /> : null}
              {status === "wrong" ? <X size={14} weight="bold" aria-hidden="true" /> : null}
              {status === "pending" ? <Circle size={11} weight="fill" aria-hidden="true" /> : null}
              {status === "answered" ? <Check size={14} weight="bold" aria-hidden="true" /> : null}
              {status === "unanswered" ? <Circle size={11} weight="fill" aria-hidden="true" /> : null}
            </button>
          );
        })}
      </nav>
      <div className="practice-rail-legend" aria-label="题目状态图例">
        <span><i className="answered" />已答</span>
        <span><i />未答</span>
        {completed ? <span><i className="wrong" />需复习</span> : null}
        {completed ? <span><i className="pending" />暂未评分</span> : null}
      </div>
    </aside>
  );
}
