import { type PracticeAnswerResult, type PracticeQuestion } from "../../api/practice";

export type PracticeNextAction = {
  kind: "knowledge" | "path" | "course" | "new_practice";
  label: string;
  href: string | null;
};

export function difficultyLabel(value: string | null | undefined) {
  if (value === "easy") return "基础";
  if (value === "hard") return "进阶";
  if (value === "adaptive") return "智能适配";
  return "中等";
}

export function isAnswered(value: string | null | undefined) {
  return Boolean(value?.trim());
}

export function practiceResultSummary(questions: PracticeQuestion[], answers: PracticeAnswerResult[]) {
  const answerByQuestion = new Map(answers.map((answer) => [answer.question_id, answer]));
  const correctCount = questions.filter((question) => answerByQuestion.get(question.id)?.is_correct === true).length;
  const wrongQuestionIds = questions
    .filter((question) => answerByQuestion.get(question.id)?.is_correct === false)
    .map((question) => question.id);

  return {
    correctCount,
    totalCount: questions.length,
    wrongQuestionIds
  };
}

export function firstWrongKnowledgePoint(questions: PracticeQuestion[], answers: PracticeAnswerResult[]) {
  const wrongIds = new Set(
    answers.filter((answer) => answer.is_correct === false).map((answer) => answer.question_id)
  );
  return questions.find((question) => wrongIds.has(question.id) && question.knowledge_point_id)?.knowledge_point_id ?? null;
}

export function buildPracticeNextAction(input: {
  courseId: number;
  wrongKnowledgePointId: string | null;
  pathReplanned: boolean;
  courseReturnHref: string | null;
}): PracticeNextAction {
  if (input.wrongKnowledgePointId) {
    return {
      kind: "knowledge",
      label: "学习薄弱知识点",
      href: `/app/courses/${input.courseId}?knowledge_point_id=${input.wrongKnowledgePointId}`
    };
  }
  if (input.pathReplanned) {
    return {
      kind: "path",
      label: "继续更新后的路径",
      href: `/app/path?course_id=${input.courseId}`
    };
  }
  if (input.courseReturnHref) {
    return {
      kind: "course",
      label: "返回来源回答",
      href: input.courseReturnHref
    };
  }
  return {
    kind: "new_practice",
    label: "开始新练习",
    href: null
  };
}
