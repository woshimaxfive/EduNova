import { expect, it } from "vitest";

import type { CourseMasteryPoint } from "../../api/courses";
import { parseCourseWorkspaceUrl, selectCourseWorkspacePoint } from "./courseWorkspaceState";

const points: CourseMasteryPoint[] = [
  { id: "1", title: "基础", chapter: "第一章", order_index: 0, status: "mastered", score: 80, prerequisite_ids: [], weakness_item_ids: [], recommended_resource_ids: [] },
  { id: "2", title: "重点", chapter: "第二章", order_index: 1, status: "weak", score: 35, prerequisite_ids: ["1"], weakness_item_ids: [], recommended_resource_ids: [] }
];

it("defaults a bare course URL to the graph workspace", () => {
  expect(parseCourseWorkspaceUrl(new URLSearchParams())).toMatchObject({ mode: "study", view: "graph", graphScope: "focus" });
});

it("restores an explicit conversation panel", () => {
  expect(parseCourseWorkspaceUrl(new URLSearchParams("course_session_id=s1&course_message_id=m1&panel=trace"))).toMatchObject({
    mode: "chat",
    view: "overview",
    courseMessageId: "m1",
    panel: "thinking"
  });
  expect(parseCourseWorkspaceUrl(new URLSearchParams("course_message_id=m1&panel=why"))).toMatchObject({ panel: "why" });
});

it("keeps the floating mentor in study mode while restoring its course session", () => {
  expect(parseCourseWorkspaceUrl(new URLSearchParams("mentor=open&course_session_id=s1&knowledge_point_id=2"))).toMatchObject({
    mode: "study",
    view: "overview",
    mentorOpen: true,
    courseSessionId: "s1",
    knowledgePointId: "2"
  });
});

it("chooses a safe point when a URL point is invalid", () => {
  expect(selectCourseWorkspacePoint(points, "missing", null, [])).toBe("2");
});
