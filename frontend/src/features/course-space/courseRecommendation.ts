import { type CourseMasteryPoint, type CourseWeaknessReviewItem } from "../../api/courses";
import { type LearningPathTask } from "../../api/paths";
import { type PracticeSessionDetail } from "../../api/practice";
import { type RagSearchResultItem } from "../../api/rag";
import { type AssessmentReport } from "../../api/reports";
import { type ResourceDifficulty } from "../../api/resources";

export type CourseRecommendationKind =
  | "confirm_weakness"
  | "continue_path"
  | "practice_weakness"
  | "study_point"
  | "generate_resource"
  | "report";

export type CourseLearningRecommendation = {
  kind: CourseRecommendationKind;
  label: string;
  reason: string;
  knowledgePointId: string | null;
};

export type CourseRecommendationInput = {
  weaknesses: CourseWeaknessReviewItem[];
  pathTasks: LearningPathTask[];
  masteryPoints: CourseMasteryPoint[];
  latestCitations: RagSearchResultItem[];
  latestPractice: PracticeSessionDetail | null;
  latestReport: AssessmentReport | null;
};

export function buildCourseLearningRecommendation(input: CourseRecommendationInput): CourseLearningRecommendation {
  const pendingWeakness = input.weaknesses.find((item) => item.status === "pending");
  if (pendingWeakness) {
    return {
      kind: "confirm_weakness",
      label: `确认薄弱点：${pendingWeakness.title}`,
      reason: "先确认问答或练习识别出的薄弱点，再安排针对性学习。",
      knowledgePointId: pendingWeakness.knowledge_point_id
    };
  }

  const currentTask = input.pathTasks.find((item) => item.status === "doing")
    ?? input.pathTasks.find((item) => item.status === "todo");
  if (currentTask) {
    return {
      kind: "continue_path",
      label: `继续任务：${currentTask.title}`,
      reason: currentTask.reason || "继续当前学习路径，完成后再用练习更新掌握度。",
      knowledgePointId: currentTask.knowledge_point_id
    };
  }

  const activeWeakness = input.weaknesses.find((item) => item.status === "reviewing")
    ?? input.weaknesses.find((item) => item.status === "confirmed");
  if (activeWeakness) {
    return {
      kind: "practice_weakness",
      label: `针对练习：${activeWeakness.title}`,
      reason: "通过自适应练习验证薄弱点是否已经掌握。",
      knowledgePointId: activeWeakness.knowledge_point_id
    };
  }

  const lowestPoint = [...input.masteryPoints]
    .filter((item): item is CourseMasteryPoint & { score: number } => item.score !== null && item.score < 75)
    .sort((left, right) => left.score - right.score || left.order_index - right.order_index)[0];
  if (lowestPoint) {
    return {
      kind: "study_point",
      label: `学习知识点：${lowestPoint.title}`,
      reason: `当前掌握度 ${lowestPoint.score}%，先阅读真实课程内容再进入练习。`,
      knowledgePointId: lowestPoint.id
    };
  }

  const citationPointId = findBestCitationKnowledgePoint(input.latestCitations);
  if (input.latestCitations.length > 0) {
    return {
      kind: "generate_resource",
      label: "基于本次回答生成学习资源",
      reason: "已有课程引用，可以生成讲解、思维导图或练习巩固。",
      knowledgePointId: citationPointId
    };
  }

  const practiceTime = parseTimestamp(input.latestPractice?.updated_at);
  const reportTime = parseTimestamp(input.latestReport?.created_at);
  if (input.latestPractice?.status === "completed" && practiceTime > reportTime) {
    return {
      kind: "report",
      label: "生成最新学习报告",
      reason: "最近练习结果尚未进入报告，可以生成阶段总结。",
      knowledgePointId: null
    };
  }

  const firstPoint = [...input.masteryPoints].sort((left, right) => left.order_index - right.order_index)[0];
  return {
    kind: "study_point",
    label: firstPoint ? `从 ${firstPoint.title} 开始学习` : "从课程内容开始学习",
    reason: "先建立课程知识基础，再通过问答和练习形成学习闭环。",
    knowledgePointId: firstPoint?.id ?? null
  };
}

export function findBestCitationKnowledgePoint(citations: RagSearchResultItem[]) {
  return [...citations]
    .filter((item) => Number.isFinite(item.knowledge_point_id) && Number(item.knowledge_point_id) > 0)
    .sort((left, right) => right.score - left.score)[0]
    ?.knowledge_point_id?.toString() ?? null;
}

export function resourceDifficultyForPoint(point: CourseMasteryPoint | undefined): ResourceDifficulty {
  if (!point || point.score === null) return "medium";
  if (point.score < 45) return "easy";
  if (point.score < 75) return "medium";
  return "hard";
}

function parseTimestamp(value: string | null | undefined) {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
