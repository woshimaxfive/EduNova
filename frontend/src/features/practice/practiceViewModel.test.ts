import { describe, expect, it } from "vitest";

import type { PracticeQuestion } from "../../api/practice";
import { buildPracticeNextAction, difficultyLabel, isAnswered, practiceResultSummary } from "./practiceViewModel";

describe("practice view model", () => {
  it("derives labels and answer state", () => {
    expect(difficultyLabel("adaptive")).toBe("智能适配");
    expect(difficultyLabel("hard")).toBe("进阶");
    expect(isAnswered("  ")).toBe(false);
    expect(isAnswered("答案")).toBe(true);
  });

  it("calculates deterministic result counts", () => {
    const questions: PracticeQuestion[] = [
      { id: "q1", question_type: "single_choice", knowledge_point_id: "1", knowledge_point_title: "A", prompt: "A", options: [], correct_answer: null, keywords: [], explanation: "", difficulty: "easy" },
      { id: "q2", question_type: "short_answer", knowledge_point_id: "2", knowledge_point_title: "B", prompt: "B", options: [], correct_answer: null, keywords: [], explanation: "", difficulty: "medium" }
    ];
    const result = practiceResultSummary(questions, [
      { question_id: "q1", answer_text: "a", is_correct: true, feedback: { score: 100, message: "", matched_keywords: [], missing_keywords: [], explanation: "" } },
      { question_id: "q2", answer_text: "b", is_correct: false, feedback: { score: 0, message: "", matched_keywords: [], missing_keywords: [], explanation: "" } }
    ]);
    expect(result).toEqual({ correctCount: 1, totalCount: 2, wrongQuestionIds: ["q2"] });
  });

  it("uses the fixed next-action priority", () => {
    expect(buildPracticeNextAction({ courseId: 8, wrongKnowledgePointId: "42", pathReplanned: true, courseReturnHref: "/course" })).toEqual({
      kind: "knowledge",
      label: "学习薄弱知识点",
      href: "/app/courses/8?knowledge_point_id=42"
    });
    expect(buildPracticeNextAction({ courseId: 8, wrongKnowledgePointId: null, pathReplanned: true, courseReturnHref: "/course" }).kind).toBe("path");
    expect(buildPracticeNextAction({ courseId: 8, wrongKnowledgePointId: null, pathReplanned: false, courseReturnHref: "/course" }).kind).toBe("course");
    expect(buildPracticeNextAction({ courseId: 8, wrongKnowledgePointId: null, pathReplanned: false, courseReturnHref: null }).kind).toBe("new_practice");
  });
});
