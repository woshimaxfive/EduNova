from __future__ import annotations

from backend.app.services.resource_intent import (
    build_artifact_intents,
    duplicate_sentence_ratio,
    evaluate_diversity,
    intent_difference_count,
    personalization_summary,
)


def test_keyword_preferences_do_not_decide_teaching_strategy_without_model_planning() -> None:
    derivation = build_artifact_intents(
        resource_types=["doc"],
        topic="反向传播",
        learning_goal="理解梯度计算",
        difficulty="medium",
        profile_summary={"cognitive_style": "喜欢逐步推导", "mastery_average": 68},
        evidence_refs=[701, 702],
        generation_action="new",
    )["doc"]
    example = build_artifact_intents(
        resource_types=["doc"],
        topic="反向传播",
        learning_goal="理解梯度计算",
        difficulty="medium",
        profile_summary={"learning_preference": "喜欢案例和例题", "mastery_average": 68},
        evidence_refs=[701, 702],
        generation_action="new",
    )["doc"]

    assert derivation["evidence_refs"] == example["evidence_refs"] == [701, 702]
    assert derivation["teaching_strategy"] == "evidence_to_concept"
    assert example["teaching_strategy"] == "evidence_to_concept"
    assert derivation["personalization_status"] == example["personalization_status"] == "personalized"
    summary = personalization_summary(example)
    assert "偏好的学习方式" in summary["teaching_reason"]
    assert "从资料证据建立概念" in summary["teaching_reason"]
    assert "worked_example_first" not in summary["teaching_reason"]


def test_alternative_changes_at_least_two_intent_dimensions_and_refine_keeps_them() -> None:
    source = build_artifact_intents(
        resource_types=["doc"],
        topic="A* 搜索",
        learning_goal="掌握启发式搜索",
        difficulty="medium",
        profile_summary={"learning_preference": "案例"},
        evidence_refs=[701],
        generation_action="new",
    )["doc"]
    alternative = build_artifact_intents(
        resource_types=["doc"],
        topic="A* 搜索",
        learning_goal="掌握启发式搜索",
        difficulty="medium",
        profile_summary={"learning_preference": "案例"},
        evidence_refs=[701],
        generation_action="alternative",
        source_intent=source,
    )["doc"]
    refined = build_artifact_intents(
        resource_types=["doc"],
        topic="A* 搜索",
        learning_goal="掌握启发式搜索",
        difficulty="medium",
        profile_summary={"learning_preference": "案例"},
        evidence_refs=[701],
        generation_action="refine",
        source_intent=source,
    )["doc"]

    assert intent_difference_count(alternative, source) >= 2
    assert intent_difference_count(refined, source) == 0


def test_diversity_gate_rejects_near_duplicate_alternative() -> None:
    source_intent = {
        "teaching_strategy": "evidence_to_concept",
        "cognitive_level": "understand",
        "example_direction": "课程真实情境",
        "interaction_structure": "概念-证据-推导-自检",
    }
    alternative_intent = {
        **source_intent,
        "teaching_strategy": "worked_example_first",
        "cognitive_level": "apply",
    }
    artifact = {
        "kind": "document",
        "sections": [
            {"title": "核心", "body": "A星搜索使用评价函数选择当前代价与预计代价之和最小的节点。"},
            {"title": "结论", "body": "启发函数不会高估剩余代价时可以保持最优性。"},
        ],
    }
    diversity, risks = evaluate_diversity(
        content={"artifact": artifact},
        intent=alternative_intent,
        comparison_contents=[],
        source_content={"artifact": artifact},
        source_intent=source_intent,
        generation_action="alternative",
    )

    assert diversity["source_similarity"] > 0.85
    assert "low_novelty" in risks
    assert diversity["status"] == "failed"


def test_sentence_overlap_ignores_short_labels_but_detects_reused_explanations() -> None:
    candidate = {
        "title": "A*",
        "sections": [
            {"body": "评价函数由已经付出的路径代价和预计剩余代价共同组成。"},
            {"body": "学习后需要能够解释启发函数为何影响搜索效率。"},
        ],
    }
    comparison = {
        "title": "导图",
        "nodes": [
            {"label": "评价函数由已经付出的路径代价和预计剩余代价共同组成。"},
            {"label": "开放列表"},
        ],
    }

    assert duplicate_sentence_ratio(candidate, [comparison]) == 0.5


def test_semantic_similarity_rejects_alternative_that_only_changes_wording() -> None:
    source_intent = {
        "teaching_strategy": "evidence_first",
        "cognitive_level": "understand",
        "example_direction": "课程真实情境",
        "interaction_structure": "概念-证据-推导-自检",
    }
    alternative_intent = {
        **source_intent,
        "teaching_strategy": "worked_example_first",
        "cognitive_level": "apply",
    }

    diversity, risks = evaluate_diversity(
        content={"artifact": {"kind": "document", "sections": [{"body": "改写后的全新表达。"}]}},
        intent=alternative_intent,
        comparison_contents=[],
        source_content={"artifact": {"kind": "document", "sections": [{"body": "来源版本原文。"}]}},
        source_intent=source_intent,
        generation_action="alternative",
        semantic_similarity=0.91,
        semantic_status="completed",
    )

    assert diversity["source_similarity"] < 0.85
    assert diversity["semantic_similarity"] == 0.91
    assert diversity["semantic_status"] == "completed"
    assert "low_novelty" in risks


def test_resource_feedback_changes_difficulty_without_becoming_profile_evidence() -> None:
    intents = build_artifact_intents(
        resource_types=["doc", "quiz", "video"],
        topic="二叉树遍历",
        learning_goal="完成考试复习",
        difficulty="medium",
        profile_summary={
            "resource_feedback": {
                "doc": {"too_hard": 1},
                "quiz": {"too_easy": 1},
                "video": {"not_helpful": 2},
            }
        },
        evidence_refs=[701],
        generation_action="new",
    )

    assert intents["doc"]["teaching_strategy"] == "scaffolded_foundation"
    assert intents["doc"]["cognitive_level"] == "understand"
    assert intents["quiz"]["cognitive_level"] == "analyze"
    assert intents["video"]["teaching_strategy"] == "concept_walkthrough"
    assert "课程级资源反馈" in intents["doc"]["learner_factors"]
