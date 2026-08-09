import {
  PATHS,
  buildCoursePathWorkspacePath,
  buildCoursePracticeWorkspacePath,
  buildCourseReportsWorkspacePath
} from "../../app/routePaths";
import { type ApiCourseKnowledgePoint } from "../../api/courses";
import { type LearningNextAction } from "../../api/learning";
import { type RagSearchResultItem } from "../../api/rag";
import {
  type TutorCitation,
  type TutorImageAttachment,
  type TutorMessage,
  type TutorSessionSummary
} from "../../api/tutor";

const inlineSourceBlockPattern =
  /(?:\*\*\s*依据\s*[:：]\s*\*\*|依据\s*[:：])\s*(?:\d+[.、]\s*)?(?:来源|章节|匹配度|片段)\s*[:：][\s\S]*?(?=(?:\s*\*\*[^*]{1,32}[:：]\s*\*\*)|(?:\s*(?:易错点|下一步|练习|建议)\s*[:：])|$)/g;
const inlineSourcePrefixPattern =
  /[（(]\s*匹配度\s*[:：]\s*[^）)]*[）)]\s*[-—–]\s*来源\s*[:：]\s*\[[^\]]+\]\s*[-—–]\s*片段\s*[:：]\s*/g;
const plainSourcePrefixPattern = /\s*[-—–]\s*来源\s*[:：]\s*\[[^\]]+\]\s*[-—–]\s*片段\s*[:：]\s*/g;
const matchScorePattern = /[（(]\s*匹配度\s*[:：]\s*[^）)]*[）)]/g;
const sourceMetadataLinePattern = /(^|\n)\s*(?:\d+[.、]\s*)?(?:来源|章节|匹配度|片段)\s*[:：][^\n]*(?=\n|$)/g;
const answerStartMarkers = ["根据上述引用", "基于上述引用", "依据上述引用", "从上述引用", "从这些引用"];

export type CourseMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: RagSearchResultItem[];
  supplementalSources?: TutorCitation[];
  traceId?: string | null;
  attachments?: TutorImageAttachment[];
  resourceJobs?: TutorMessage["resource_jobs"];
  resourceProposal?: TutorMessage["resource_proposal"];
};

export function sanitizeCourseAnswerContent(content: string) {
  const sanitized = content
    .trim()
    .replace(inlineSourceBlockPattern, "")
    .replace(inlineSourcePrefixPattern, "：")
    .replace(plainSourcePrefixPattern, "：")
    .replace(matchScorePattern, "")
    .replace(sourceMetadataLinePattern, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (!sanitized.includes("学生问题：") || !sanitized.includes("课程引用：")) {
    return sanitized || content;
  }

  const answerStarts = answerStartMarkers
    .map((marker) => sanitized.indexOf(marker))
    .filter((position) => position >= 0);

  if (answerStarts.length > 0) {
    return sanitized.slice(Math.min(...answerStarts)).trim();
  }

  return "这条回答包含过多内部引用上下文。请打开来源面板查看证据，或换一种问法继续提问。";
}

export function courseQuestionTitle(question: string) {
  const normalized = question.trim();
  return normalized.length > 30 ? `${normalized.slice(0, 30)}...` : normalized;
}

function isRagCitation(citation: TutorCitation): citation is RagSearchResultItem {
  return (
    typeof citation.chunk_id === "number" &&
    typeof citation.course_id === "number" &&
    typeof citation.material_id === "number" &&
    typeof citation.content === "string" &&
    typeof citation.source_title === "string"
  );
}

export function mapTutorMessagesToCourseMessages(messages: TutorMessage[]): CourseMessage[] {
  return messages.map((message) => {
    const assistantCitations = message.role === "assistant" ? message.citation_json : [];

    return {
      id: message.id,
      role: message.role,
      content: message.content,
      citations: message.role === "assistant" ? assistantCitations.filter(isRagCitation) : undefined,
      supplementalSources: message.role === "assistant"
        ? assistantCitations.filter((citation) => !isRagCitation(citation))
        : undefined,
      traceId: message.role === "assistant" ? message.trace_id : null,
      attachments: message.attachments ?? [],
      resourceJobs: message.resource_jobs ?? [],
      resourceProposal: message.resource_proposal ?? null
    };
  });
}

export function mapCourseSessionsToConversations(sessions: TutorSessionSummary[]) {
  return sessions.map((session) => ({
    id: session.id,
    title: session.title,
    meta: "课程内"
  }));
}

export function findQuestionForAssistant(messages: CourseMessage[], assistantIndex: number) {
  for (let index = assistantIndex - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user") {
      return messages[index]?.content ?? null;
    }
  }
  return null;
}

export function buildCourseStarterQuestions(
  recommendation: LearningNextAction,
  points: ApiCourseKnowledgePoint[]
) {
  const recommendedPoint = points.find((point) => point.id === recommendation.knowledge_point_id) ?? points[0];
  const pointTitle = recommendedPoint?.title ?? "这门课的核心知识";
  return [
    `请结合课程资料解释${pointTitle}，并给一个具体例子`,
    `学习${pointTitle}前，我需要先掌握什么？`,
    `围绕${pointTitle}出一道检查理解的问题`
  ];
}

function resolveCourseWorkspacePath(destination: string, courseId: number) {
  if (destination === PATHS.path) return buildCoursePathWorkspacePath(courseId);
  if (destination === PATHS.practice) return buildCoursePracticeWorkspacePath(courseId);
  if (destination === PATHS.reports) return buildCourseReportsWorkspacePath(courseId);
  return destination;
}

export function buildCourseClosureHref(
  destination: string,
  courseId: number,
  sessionId: string | null,
  messageId: string,
  knowledgePointId?: string | null
) {
  const params = new URLSearchParams({
    return_to: "course",
    course_message_id: messageId
  });
  if (sessionId) params.set("course_session_id", sessionId);
  if (knowledgePointId) params.set("knowledge_point_id", knowledgePointId);
  return `${resolveCourseWorkspacePath(destination, courseId)}?${params.toString()}`;
}
