import { describe, expect, it } from "vitest";

import { PATHS } from "../../app/routePaths";
import { type TutorMessage, type TutorSessionSummary } from "../../api/tutor";
import {
  buildCourseClosureHref,
  buildCourseStarterQuestions,
  courseQuestionTitle,
  findQuestionForAssistant,
  mapCourseSessionsToConversations,
  mapTutorMessagesToCourseMessages,
  sanitizeCourseAnswerContent,
  type CourseMessage
} from "./courseConversation";

const assistantMessage: TutorMessage = {
  id: "message-2",
  session_id: "session-1",
  role: "assistant",
  content: "根据课程内容回答。",
  citation_json: [
    {
      chunk_id: 12,
      course_id: 3,
      material_id: 7,
      content: "课程证据",
      source_title: "数据结构讲义",
      section_title: "线性表",
      page_number: 8,
      score: 0.92
    },
    {
      source_type: "web",
      title: "外部补充",
      url: "https://example.com/reference"
    }
  ],
  trace_id: "trace-1",
  created_at: "2026-08-09T00:00:00Z",
  attachments: []
};

describe("course conversation view model", () => {
  it("separates course evidence from supplemental sources", () => {
    const [message] = mapTutorMessagesToCourseMessages([assistantMessage]);

    expect(message.citations).toHaveLength(1);
    expect(message.citations?.[0]?.source_title).toBe("数据结构讲义");
    expect(message.supplementalSources).toHaveLength(1);
    expect(message.traceId).toBe("trace-1");
  });

  it("keeps user messages free of assistant-only evidence", () => {
    const [message] = mapTutorMessagesToCourseMessages([
      {
        ...assistantMessage,
        id: "message-1",
        role: "user",
        content: "什么是线性表？"
      }
    ]);

    expect(message.citations).toBeUndefined();
    expect(message.supplementalSources).toBeUndefined();
    expect(message.traceId).toBeNull();
  });

  it("removes persisted source metadata without hiding the answer", () => {
    const content = "线性表用于组织有序数据。\n来源：[数据结构讲义] - 片段：数组是一种线性表。";
    expect(sanitizeCourseAnswerContent(content)).toBe("线性表用于组织有序数据。");
  });

  it("drops legacy prompt context before the actual answer", () => {
    const content = "学生问题：什么是栈？\n课程引用：后进先出\n根据上述引用，栈是一种后进先出的结构。";
    expect(sanitizeCourseAnswerContent(content)).toBe("根据上述引用，栈是一种后进先出的结构。");
  });

  it("finds the user question that belongs to an assistant turn", () => {
    const messages: CourseMessage[] = [
      { id: "1", role: "user", content: "第一个问题" },
      { id: "2", role: "assistant", content: "第一个回答" },
      { id: "3", role: "user", content: "追问" },
      { id: "4", role: "assistant", content: "追问回答" }
    ];

    expect(findQuestionForAssistant(messages, 3)).toBe("追问");
    expect(findQuestionForAssistant(messages, 0)).toBeNull();
  });

  it("builds stable sidebar and closed-loop navigation values", () => {
    const sessions: TutorSessionSummary[] = [{
      id: "session-1",
      scope: "course",
      course_id: "3",
      title: "线性表复习",
      mode: "chat",
      archived_from_home: false,
      selected_material_ids: [7],
      created_at: "2026-08-09T00:00:00Z",
      updated_at: "2026-08-09T00:00:00Z"
    }];

    expect(mapCourseSessionsToConversations(sessions)).toEqual([
      { id: "session-1", title: "线性表复习", meta: "课程内" }
    ]);
    expect(buildCourseClosureHref(PATHS.practice, 3, "session-1", "message-2", "12")).toBe(
      "/app/courses/3/practice?return_to=course&course_message_id=message-2&course_session_id=session-1&knowledge_point_id=12"
    );
  });

  it("builds concise titles and course-specific starter questions", () => {
    expect(courseQuestionTitle("  什么是栈？  ")).toBe("什么是栈？");
    expect(courseQuestionTitle("一".repeat(31))).toBe(`${"一".repeat(30)}...`);
    expect(buildCourseStarterQuestions(
      {
        kind: "continue_course",
        status: "ready",
        label: "继续学习",
        description: "完成当前知识点",
        course_id: "3",
        material_id: null,
        knowledge_point_id: "12",
        path_task_id: null,
        resource_id: null
      },
      [{ id: "12", title: "线性表", summary: null, chapter: "第一章", order_index: 0, difficulty: null, prerequisite_ids: [] }]
    )).toEqual([
      "请结合课程资料解释线性表，并给一个具体例子",
      "学习线性表前，我需要先掌握什么？",
      "围绕线性表出一道检查理解的问题"
    ]);
  });
});
