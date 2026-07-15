import { type PracticeAnswerResult, type PracticeQuestion } from "../../api/practice";

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
  const gradedCount = questions.filter((question) => answerByQuestion.get(question.id)?.is_correct !== null
    && answerByQuestion.get(question.id)?.is_correct !== undefined).length;
  const wrongQuestionIds = questions
    .filter((question) => answerByQuestion.get(question.id)?.is_correct === false)
    .map((question) => question.id);

  return {
    correctCount,
    gradedCount,
    totalCount: questions.length,
    wrongQuestionIds
  };
}
