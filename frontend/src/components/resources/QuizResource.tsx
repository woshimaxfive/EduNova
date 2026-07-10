import { CheckCircle, Circle, Eye } from "@phosphor-icons/react";
import { useMemo, useState } from "react";

import { type ResourceQuizArtifact } from "../../api/resources";

export function QuizResource({ artifact }: { artifact: ResourceQuizArtifact }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string[] | string>>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const question = artifact.questions[activeIndex];
  const answer = answers[question.id];
  const selected = useMemo(() => (Array.isArray(answer) ? answer : answer ? [answer] : []), [answer]);

  function toggleOption(key: string) {
    if (question.type === "multiple_choice") {
      setAnswers((current) => {
        const currentValue = current[question.id];
        const values = Array.isArray(currentValue) ? currentValue : [];
        return {
          ...current,
          [question.id]: values.includes(key) ? values.filter((item) => item !== key) : [...values, key]
        };
      });
      return;
    }
    setAnswers((current) => ({ ...current, [question.id]: key }));
  }

  return (
    <div className="resource-quiz-shell">
      <div className="resource-quiz-progress" aria-label="练习题进度">
        {artifact.questions.map((item, index) => (
          <button
            className={index === activeIndex ? "active" : ""}
            key={item.id}
            type="button"
            aria-label={`查看第 ${index + 1} 题`}
            aria-pressed={index === activeIndex}
            onClick={() => setActiveIndex(index)}
          >
            {answers[item.id] ? <CheckCircle size={17} weight="fill" aria-hidden="true" /> : <Circle size={17} aria-hidden="true" />}
            <span>{index + 1}</span>
          </button>
        ))}
      </div>

      <section className="resource-quiz-question" aria-label={`第 ${activeIndex + 1} 题`}>
        <span>{question.type === "single_choice" ? "单选题" : question.type === "multiple_choice" ? "多选题" : "简答题"}</span>
        <h3>{question.prompt}</h3>
        {question.type === "short_answer" ? (
          <textarea
            aria-label="简答题回答"
            value={typeof answer === "string" ? answer : ""}
            onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))}
            placeholder="先写下你的理解，再查看参考解析"
          />
        ) : (
          <div className="resource-quiz-options">
            {question.options.map((option) => (
              <button
                className={selected.includes(option.key) ? "selected" : ""}
                key={option.key}
                type="button"
                aria-pressed={selected.includes(option.key)}
                onClick={() => toggleOption(option.key)}
              >
                <strong>{option.key}</strong>
                <span>{option.text}</span>
              </button>
            ))}
          </div>
        )}
        <button
          className="soft-button resource-reveal-answer"
          type="button"
          onClick={() => setRevealed((current) => ({ ...current, [question.id]: !current[question.id] }))}
        >
          <Eye size={17} aria-hidden="true" />
          <span>{revealed[question.id] ? "收起解析" : "查看答案与解析"}</span>
        </button>
        {revealed[question.id] ? (
          <div className="resource-quiz-explanation" role="status">
            <strong>参考答案：{Array.isArray(question.answer) ? question.answer.join("、") : question.answer}</strong>
            <p>{question.explanation}</p>
          </div>
        ) : null}
      </section>
    </div>
  );
}
