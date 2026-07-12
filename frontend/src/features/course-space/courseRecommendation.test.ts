import { describe, expect, it } from "vitest";

import { buildCourseLearningRecommendation, findBestCitationKnowledgePoint, resourceDifficultyForPoint } from "./courseRecommendation";

const baseInput = {
  weaknesses: [],
  pathTasks: [],
  masteryPoints: [],
  latestCitations: [],
  latestPractice: null,
  latestReport: null
};

describe("course learning recommendation", () => {
  it("uses the fixed learning priority", () => {
    const recommendation = buildCourseLearningRecommendation({
      ...baseInput,
      weaknesses: [{ id: "1", title: "反向传播", status: "pending", source_type: "practice", course_id: "8", knowledge_point_id: "42", recommended_resource_ids: [], recommended_resources: [], next_review_at: null, created_at: "", updated_at: "" }],
      pathTasks: [{ id: "2", path_id: "1", course_id: "8", knowledge_point_id: "43", title: "路径任务", task_type: "learn", reason: "路径依据", recommended_resource_ids: [], recommended_resources: [], status: "doing", created_at: "", updated_at: "" }]
    });

    expect(recommendation.kind).toBe("confirm_weakness");
    expect(recommendation.knowledgePointId).toBe("42");
  });

  it("selects the highest scoring valid citation knowledge point", () => {
    expect(findBestCitationKnowledgePoint([
      { chunk_id: 1, course_id: 8, material_id: 2, knowledge_point_id: null, content: "a", source_title: "a", section_title: null, page_number: null, score: 10 },
      { chunk_id: 2, course_id: 8, material_id: 2, knowledge_point_id: 42, content: "b", source_title: "b", section_title: null, page_number: null, score: 5 },
      { chunk_id: 3, course_id: 8, material_id: 2, knowledge_point_id: 43, content: "c", source_title: "c", section_title: null, page_number: null, score: 8 }
    ])).toBe("43");
  });

  it("derives resource difficulty from deterministic mastery", () => {
    const point = (score: number) => ({ id: "1", title: "知识点", chapter: null, order_index: 0, status: "learning" as const, score, prerequisite_ids: [], weakness_item_ids: [], recommended_resource_ids: [] });
    expect(resourceDifficultyForPoint(undefined)).toBe("easy");
    expect(resourceDifficultyForPoint(point(44))).toBe("easy");
    expect(resourceDifficultyForPoint(point(45))).toBe("medium");
    expect(resourceDifficultyForPoint(point(75))).toBe("hard");
  });
});
