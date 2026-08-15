import { describe, expect, it } from "vitest";

import type { ProfileEventResponse, StudentProfileResponse } from "../../api/profiles";
import {
  buildProfileDimensions,
  buildProfileEventView,
  buildProfileUpdateReceipt,
  calculateProfileCompleteness,
  PROFILE_DIMENSIONS,
  profileEventsForDimension,
  profileQuestionGuidance
} from "./profileViewModel";

const profile = (overrides: Partial<StudentProfileResponse> = {}): StudentProfileResponse => ({
  id: "7",
  version: 2,
  has_profile: true,
  profile_json: {
    major_background: "计算机专业",
    knowledge_foundation: "具备 Python 基础",
    learning_goal: "掌握机器学习",
    cognitive_style: "偏好先看结构",
    learning_preference: "图解与实操",
    weak_points: ["链式法则"],
    learning_pace: "每天两个任务",
    motivation_interest: "完成 AI 项目"
  },
  confidence_score: 72,
  dimension_confidence: { learning_goal: 82, weak_points: 64 },
  evidence_summary: { applied_count: 1, candidate_count: 1 },
  updated_reason: "更新学习画像：学习目标",
  updated_at: "2026-07-13T09:00:00Z",
  next_question: "最近哪里最卡住？",
  ...overrides
});

const event = (overrides: Partial<ProfileEventResponse> = {}): ProfileEventResponse => ({
  id: "91",
  dimension: "profile_chat",
  change_summary: "更新学习画像：学习目标",
  evidence_json: {
    updated_dimensions: ["learning_goal"],
    candidate_dimensions: ["weak_points"],
    generation_mode: "model_enhanced",
    parse_status: "repaired",
    repair_count: 1,
    review_mode: "model_and_rules"
  },
  source_type: "profile_chat",
  status: "applied",
  confidence_score: 0.82,
  created_at: "2026-07-13T09:01:00Z",
  ...overrides
});

describe("profileViewModel", () => {
  it("separates eight-dimension completeness from evidence confidence and supports legacy responses", () => {
    const partial = profile({
      profile_json: {
        ...profile().profile_json,
        major_background: "计算机专业",
        learning_goal: "掌握机器学习",
        knowledge_foundation: "",
        cognitive_style: "",
        learning_preference: "",
        weak_points: [],
        learning_pace: "",
        motivation_interest: ""
      },
      completeness_score: undefined,
      evidence_confidence_score: 88
    });

    expect(calculateProfileCompleteness(partial)).toBe(25);
    expect(calculateProfileCompleteness(profile({ completeness_score: 62.5 }))).toBe(62.5);
  });

  it("provides friendly labels, guidance and plain-text examples for every profile dimension", () => {
    expect(PROFILE_DIMENSIONS.map((item) => item.label)).toEqual([
      "学习背景",
      "已有基础",
      "学习目标",
      "理解习惯",
      "学习方式",
      "学习难点",
      "学习节奏",
      "学习动力"
    ]);
    expect(PROFILE_DIMENSIONS.map((item) => item.shortLabel)).toEqual([
      "背景",
      "基础",
      "目标",
      "理解",
      "方式",
      "难点",
      "节奏",
      "动力"
    ]);
    for (const dimension of PROFILE_DIMENSIONS) {
      expect(profileQuestionGuidance(dimension.key)).toMatchObject({
        key: dimension.key,
        label: dimension.label,
        guidance: expect.stringMatching(/。$/),
        examples: expect.stringMatching(/。$/)
      });
    }
    expect(profileQuestionGuidance(undefined)).toBeNull();
  });

  it("keeps the eight-dimension profile order and counts applied and candidate evidence", () => {
    const dimensions = buildProfileDimensions(profile(), [event()]);
    expect(dimensions.map((item) => item.key)).toEqual(PROFILE_DIMENSIONS.map((item) => item.key));
    expect(dimensions.find((item) => item.key === "learning_goal")).toMatchObject({ confidence: 82, appliedCount: 1 });
    expect(dimensions.find((item) => item.key === "weak_points")).toMatchObject({ confidence: 64, candidateCount: 1 });
  });

  it("separates candidate dimensions from applied dimensions", () => {
    const view = buildProfileEventView(event());
    expect(view.appliedDimensions).toEqual(["learning_goal"]);
    expect(view.candidateDimensions).toEqual(["weak_points"]);
    expect(view.status).toBe("mixed");
    expect(view.sourceLabel).toBe("主动回答");
    expect(view.generationModeLabel).toBe("模型增强");
    expect(view.parseStatus).toBe("repaired");
    expect(view.repairCount).toBe(1);
  });

  it("supports legacy events without inventing evidence fields", () => {
    const legacy = event({
      dimension: "profile_chat",
      change_summary: "更新学习画像：知识基础、学习目标",
      evidence_json: { source_type: "course_question" },
      source_type: undefined,
      status: "applied"
    });
    expect(buildProfileEventView(legacy).appliedDimensions).toEqual(["knowledge_foundation", "learning_goal"]);
    expect(buildProfileEventView(legacy).sourceLabel).toBe("课程问答");
    expect(profileEventsForDimension([legacy], "knowledge_foundation")).toHaveLength(1);

    const legacyCognitiveStyle = event({
      dimension: "profile_chat",
      change_summary: "更新学习画像：认知风格、学习动机",
      evidence_json: {},
      status: "applied"
    });
    expect(buildProfileEventView(legacyCognitiveStyle).appliedDimensions).toEqual([
      "cognitive_style",
      "motivation_interest"
    ]);
  });

  it("only marks real response differences as changed", () => {
    const previous = profile({
      profile_json: { ...profile().profile_json, learning_goal: "" },
      dimension_confidence: { learning_goal: 0, weak_points: 64 }
    });
    const receipt = buildProfileUpdateReceipt(previous, profile(), event());
    expect(receipt.changedDimensions).toEqual(["learning_goal"]);
    expect(receipt.appliedDimensions).toEqual(["learning_goal"]);
    expect(receipt.candidateDimensions).toEqual(["weak_points"]);
  });
});
