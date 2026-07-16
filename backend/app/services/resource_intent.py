from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal

from backend.app.services.resource_quality import normalized_text, text_similarity
from backend.app.services.resource_feedback import feedback_adjustment


GenerationAction = Literal["new", "alternative", "refine"]

RESOURCE_ROLES = {
    "doc": "解释核心概念、依据与推导过程",
    "mindmap": "组织概念关系、先修结构与复习线索",
    "quiz": "检验理解、应用与迁移，暴露具体误区",
    "code": "通过可运行实验验证知识过程与结果",
    "slide": "组织一段完整、可讲授的学习过程",
    "animation": "呈现状态、流程或关系随步骤发生的变化",
    "video": "补充可信平台上的外部教学讲解",
}

BASE_STRATEGIES = {
    "doc": "evidence_to_concept",
    "mindmap": "relationship_mapping",
    "quiz": "misconception_transfer",
    "code": "executable_experiment",
    "slide": "guided_lesson",
    "animation": "process_visualization",
    "video": "curated_external_explanation",
}

ALTERNATIVE_STRATEGIES = {
    "doc": ("worked_example_first", "contrastive_explanation", "derivation_first"),
    "mindmap": ("problem_solution_mapping", "prerequisite_mapping", "comparison_mapping"),
    "quiz": ("scenario_transfer", "error_diagnosis", "progressive_challenge"),
    "code": ("boundary_experiment", "step_trace", "comparison_experiment"),
    "slide": ("case_led_lesson", "question_led_lesson", "review_workshop"),
    "animation": ("state_transition", "cause_effect_sequence", "error_correction_sequence"),
    "video": ("concept_walkthrough", "worked_example_video", "review_video"),
}

ALLOWED_TEACHING_STRATEGIES = frozenset(BASE_STRATEGIES.values()) | frozenset(
    strategy for strategies in ALTERNATIVE_STRATEGIES.values() for strategy in strategies
) | {"scaffolded_foundation"}

COGNITIVE_LEVELS = {
    "doc": ("understand", "analyze"),
    "mindmap": ("understand", "analyze"),
    "quiz": ("apply", "analyze"),
    "code": ("apply", "create"),
    "slide": ("understand", "apply"),
    "animation": ("understand", "analyze"),
    "video": ("understand", "apply"),
}

INTERACTION_STRUCTURES = {
    "doc": ("概念-证据-推导-自检", "问题-示例-反例-复盘"),
    "mindmap": ("中心概念-关系分支-复习动作", "问题链-条件-结论-迁移"),
    "quiz": ("理解-应用-迁移递进", "误区辨析-情境判断-解释反馈"),
    "code": ("观察输出-修改参数-验证结论", "逐步跟踪-边界测试-结果解释"),
    "slide": ("目标-讲解-示例-练习-总结", "问题-证据-推导-讨论-行动"),
    "animation": ("状态变化-原因-结果-回看", "输入-步骤-关键转折-输出"),
    "video": ("观看目标-关键片段-自检问题", "问题-讲解-例子-迁移"),
}

CASE_DIRECTIONS = (
    "课程真实情境",
    "常见误区辨析",
    "数值或步骤演算",
    "边界条件与反例",
    "跨场景迁移应用",
)

STRATEGY_LABELS = {
    "evidence_to_concept": "从资料证据建立概念",
    "relationship_mapping": "梳理概念关系",
    "misconception_transfer": "通过误区辨析完成迁移",
    "executable_experiment": "用可运行实验验证结论",
    "guided_lesson": "按完整教学过程逐步推进",
    "process_visualization": "把知识过程可视化",
    "scaffolded_foundation": "分步骤巩固基础",
    "derivation_first": "先推导再应用",
    "worked_example_first": "先看完整案例再归纳概念",
    "framework_first": "先建立整体框架",
    "code_first_experiment": "先动手实验再解释原理",
    "contrastive_explanation": "通过对比和反例解释概念",
    "problem_solution_mapping": "按问题与解法组织关系",
    "prerequisite_mapping": "按先修关系组织知识",
    "comparison_mapping": "通过对比组织知识结构",
    "scenario_transfer": "用新情境检验迁移",
    "error_diagnosis": "从错误诊断反推理解缺口",
    "progressive_challenge": "按难度递进完成挑战",
    "boundary_experiment": "通过边界实验验证规律",
    "step_trace": "逐步跟踪过程与状态",
    "comparison_experiment": "用对照实验解释差异",
    "case_led_lesson": "用案例串联教学过程",
    "question_led_lesson": "用问题链引导学习",
    "review_workshop": "用复习任务组织教学",
    "state_transition": "按状态变化解释过程",
    "cause_effect_sequence": "按因果顺序解释变化",
    "error_correction_sequence": "通过纠错过程展示变化",
    "curated_external_explanation": "精选外部教学讲解",
    "concept_walkthrough": "跟随讲解理解概念",
    "worked_example_video": "通过视频案例完成迁移",
    "review_video": "通过视频复习关键结论",
}


@dataclass(frozen=True)
class ArtifactIntent:
    resource_type: str
    topic: str
    learning_goal: str
    learning_need: str
    resource_role: str
    teaching_strategy: str
    cognitive_level: str
    example_direction: str
    interaction_structure: str
    evidence_refs: tuple[int, ...]
    success_criteria: tuple[str, ...]
    learner_factors: tuple[str, ...]
    difference_requirements: tuple[str, ...]
    personalization_status: str
    generation_action: GenerationAction

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["success_criteria"] = list(self.success_criteria)
        payload["learner_factors"] = list(self.learner_factors)
        payload["difference_requirements"] = list(self.difference_requirements)
        return payload

    def public_summary(self) -> dict[str, Any]:
        if self.personalization_status == "context_limited":
            reason = "当前可信学习信息较少，先依据课程证据组织这份资源。"
        else:
            reason = _personalized_reason(self.to_dict())
        difference = (
            "保留原教学意图，重点修正内容、结构和表达。"
            if self.generation_action == "refine"
            else "更换教学策略、案例角度或学习活动，避免重复旧版本。"
            if self.generation_action == "alternative"
            else f"与同批资源分工，本资源专注于{self.resource_role}。"
        )
        return {
            "status": self.personalization_status,
            "learning_problem": self.learning_need,
            "teaching_reason": reason,
            "difference": difference,
            "factors": list(self.learner_factors[:4]),
        }


def build_artifact_intents(
    *,
    resource_types: list[str],
    topic: str,
    learning_goal: str,
    difficulty: str,
    profile_summary: dict[str, Any],
    evidence_refs: Iterable[int],
    generation_action: GenerationAction,
    source_intent: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    factors = _learner_factors(profile_summary)
    weakness = _first_text(profile_summary.get("weak_points"))
    mastery = profile_summary.get("mastery_average")
    current_task = _clean(profile_summary.get("current_task_title"))
    resource_feedback = (
        profile_summary.get("resource_feedback")
        if isinstance(profile_summary.get("resource_feedback"), dict)
        else {}
    )
    if weakness:
        learning_need = f"优先解决“{weakness}”相关理解或应用困难"
    elif isinstance(mastery, (int, float)) and mastery < 60:
        learning_need = f"巩固当前约 {round(float(mastery))}% 的课程掌握基础"
    elif current_task:
        learning_need = f"支持当前任务“{current_task}”"
    else:
        learning_need = f"建立“{topic}”的可验证理解"
    status = "personalized" if factors or weakness or isinstance(mastery, (int, float)) or current_task else "context_limited"
    refs = tuple(dict.fromkeys(int(item) for item in evidence_refs if int(item) > 0))
    intents: dict[str, dict[str, Any]] = {}
    for index, resource_type in enumerate(resource_types):
        base_strategy = _strategy_for(resource_type, profile_summary, mastery)
        level = _cognitive_level(resource_type, difficulty)
        example_direction = CASE_DIRECTIONS[index % len(CASE_DIRECTIONS)]
        structure = INTERACTION_STRUCTURES[resource_type][0]
        adjustment = feedback_adjustment(resource_type, resource_feedback)
        if adjustment == "scaffold":
            base_strategy = "scaffolded_foundation"
            level = "understand"
            structure = INTERACTION_STRUCTURES[resource_type][0]
        elif adjustment == "challenge":
            level = _next_value(("understand", "apply", "analyze", "create"), level)
            example_direction = "跨场景迁移应用"
        elif adjustment == "alternative":
            base_strategy = ALTERNATIVE_STRATEGIES[resource_type][0]
            structure = INTERACTION_STRUCTURES[resource_type][1]
        difference_requirements = (
            f"只承担“{RESOURCE_ROLES[resource_type]}”这一教学职责，不复述其他资源的完整内容。",
            "引用同一事实时改用适合本资源类型的学习活动，而不是复制句子。",
        )
        if adjustment == "scaffold":
            difference_requirements += ("该模态近期反馈偏难，增加先修提示、分步示例和低门槛自检。",)
        elif adjustment == "challenge":
            difference_requirements += ("该模态近期反馈偏简单，提高到应用或分析层级并增加迁移任务。",)
        elif adjustment == "alternative":
            difference_requirements += ("至少两份同模态资源被标记为没帮助，本次必须更换教学组织方式。",)
        if generation_action == "alternative" and source_intent:
            base_strategy = _next_value(
                ALTERNATIVE_STRATEGIES[resource_type],
                str(source_intent.get("teaching_strategy") or base_strategy),
            )
            level = _next_value(("understand", "apply", "analyze", "create"), str(source_intent.get("cognitive_level") or level))
            example_direction = _next_value(CASE_DIRECTIONS, str(source_intent.get("example_direction") or example_direction))
            structure = INTERACTION_STRUCTURES[resource_type][1]
            difference_requirements = (
                "相对来源版本至少改变教学策略、案例角度、认知层级、交互结构中的两项。",
                "不得复用来源版本的完整句子或仅做同义改写。",
            )
        elif generation_action == "refine" and source_intent:
            base_strategy = _clean(source_intent.get("teaching_strategy")) or base_strategy
            level = _clean(source_intent.get("cognitive_level")) or level
            example_direction = _clean(source_intent.get("example_direction")) or example_direction
            structure = _clean(source_intent.get("interaction_structure")) or structure
            difference_requirements = (
                "保持原教学策略、案例方向、认知层级和交互结构。",
                "只修正事实、引用、结构完整性、表达和类型交互质量。",
            )
        intent = ArtifactIntent(
            resource_type=resource_type,
            topic=_clean(topic),
            learning_goal=_clean(learning_goal),
            learning_need=learning_need,
            resource_role=RESOURCE_ROLES[resource_type],
            teaching_strategy=base_strategy,
            cognitive_level=level,
            example_direction=example_direction,
            interaction_structure=structure,
            evidence_refs=refs,
            success_criteria=_success_criteria(resource_type, topic),
            learner_factors=tuple(factors[:5]),
            difference_requirements=difference_requirements,
            personalization_status=status,
            generation_action=generation_action,
        )
        intents[resource_type] = intent.to_dict()
    return intents


def personalization_summary(intent: dict[str, Any]) -> dict[str, Any]:
    status = str(intent.get("personalization_status") or "context_limited")
    need = _clean(intent.get("learning_need")) or "建立当前知识点的可验证理解"
    action = str(intent.get("generation_action") or "new")
    if status == "context_limited":
        reason = "当前可信学习信息较少，先依据课程证据组织这份资源。"
    else:
        reason = _personalized_reason(intent)
    difference = (
        "保留原教学意图，重点修正内容、结构和表达。"
        if action == "refine"
        else "更换教学策略、案例角度或学习活动，避免重复旧版本。"
        if action == "alternative"
        else f"与同批资源分工，本资源专注于{_clean(intent.get('resource_role'))}。"
    )
    factors = intent.get("learner_factors") if isinstance(intent.get("learner_factors"), list) else []
    return {
        "status": status,
        "learning_problem": need,
        "teaching_reason": reason,
        "difference": difference,
        "factors": [_clean(item) for item in factors if _clean(item)][:4],
    }


def evaluate_diversity(
    *,
    content: dict[str, Any],
    intent: dict[str, Any],
    comparison_contents: list[dict[str, Any]],
    source_content: dict[str, Any] | None,
    source_intent: dict[str, Any] | None,
    generation_action: GenerationAction,
    semantic_similarity: float | None = None,
    semantic_status: str = "not_checked",
) -> tuple[dict[str, Any], list[str]]:
    candidate_artifact = content.get("artifact")
    comparison_artifacts = [item.get("artifact") for item in comparison_contents if isinstance(item, dict)]
    duplicate_ratio = duplicate_sentence_ratio(candidate_artifact, comparison_artifacts)
    source_similarity = text_similarity(candidate_artifact, (source_content or {}).get("artifact")) if source_content else 0.0
    novelty_similarity = max(source_similarity, semantic_similarity or 0.0)
    changed_dimensions = intent_difference_count(intent, source_intent or {}) if source_intent else 0
    risks: list[str] = []
    if duplicate_ratio > 0.15:
        risks.append("excessive_sentence_overlap")
    if generation_action == "alternative":
        if novelty_similarity > 0.85:
            risks.append("low_novelty")
        if changed_dimensions < 2:
            risks.append("insufficient_strategy_change")
    if generation_action == "refine" and source_intent and changed_dimensions > 0:
        risks.append("intent_drift")
    score = max(0.0, min(1.0, 1.0 - max(duplicate_ratio, max(0.0, novelty_similarity - 0.7))))
    return {
        "status": "passed" if not risks else "failed",
        "score": round(score, 3),
        "duplicate_sentence_ratio": round(duplicate_ratio, 3),
        "source_similarity": round(source_similarity, 3),
        "semantic_similarity": round(semantic_similarity, 3) if semantic_similarity is not None else None,
        "semantic_status": semantic_status,
        "changed_intent_dimensions": changed_dimensions,
        "comparison_count": len(comparison_contents),
        "risk_flags": risks,
    }, risks


def quality_dimensions(
    *,
    existing_risks: list[str],
    intent: dict[str, Any],
    diversity: dict[str, Any],
    source_coverage: float,
) -> dict[str, dict[str, Any]]:
    type_risks = {"malformed_content", "invalid_options", "invalid_answer", "incomplete_code", "incomplete_animation"}
    authenticity_risks = {"off_topic", "off_topic_code", "citation_mismatch", "missing_citations", "sensitive_output"}
    personalization_score = 0.55 if intent.get("personalization_status") == "context_limited" else 0.86
    if not intent.get("learner_factors") and intent.get("personalization_status") != "context_limited":
        personalization_score = 0.68
    return {
        "authenticity": _dimension(1.0 if not authenticity_risks.intersection(existing_risks) else 0.0, "课程事实与引用一致"),
        "personalization": _dimension(personalization_score, "教学策略与当前学习状态匹配"),
        "diversity": _dimension(float(diversity.get("score") or 0), "与同批和历史成果保持有效差异"),
        "pedagogical_utility": _dimension(0.88 if intent.get("success_criteria") else 0.5, "包含可验证的学习结果"),
        "type_correctness": _dimension(1.0 if not type_risks.intersection(existing_risks) else 0.0, "符合资源类型结构与交互要求"),
        "source_coverage": _dimension(source_coverage, "覆盖本次检索到的课程依据"),
    }


def intent_difference_count(current: dict[str, Any], previous: dict[str, Any]) -> int:
    fields = ("teaching_strategy", "cognitive_level", "example_direction", "interaction_structure")
    return sum(1 for field in fields if _clean(current.get(field)) != _clean(previous.get(field)))


def duplicate_sentence_ratio(candidate: object, comparisons: Iterable[object]) -> float:
    sentences = _artifact_sentences(candidate)
    if not sentences:
        return 0.0
    other_sentences = {sentence for comparison in comparisons for sentence in _artifact_sentences(comparison)}
    if not other_sentences:
        return 0.0
    return len(sentences.intersection(other_sentences)) / len(sentences)


def safe_history_summary(resources: Iterable[Any], limit: int = 5) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for resource in resources:
        content = resource.content_json if isinstance(getattr(resource, "content_json", None), dict) else {}
        intent = content.get("intent") if isinstance(content.get("intent"), dict) else {}
        summaries.append(
            {
                "resource_id": int(resource.id),
                "resource_type": str(resource.resource_type),
                "title": str(resource.title)[:120],
                "summary": str(content.get("summary") or "")[:240],
                "teaching_strategy": str(intent.get("teaching_strategy") or ""),
                "cognitive_level": str(intent.get("cognitive_level") or ""),
            }
        )
        if len(summaries) >= limit:
            break
    return summaries


def _strategy_for(resource_type: str, profile_summary: dict[str, Any], mastery: object) -> str:
    if isinstance(mastery, (int, float)) and mastery < 45:
        return "scaffolded_foundation"
    return BASE_STRATEGIES[resource_type]


def _personalized_reason(intent: dict[str, Any]) -> str:
    need = _clean(intent.get("learning_need")) or "建立当前知识点的可验证理解"
    strategy = _clean(intent.get("teaching_strategy")) or "evidence_to_concept"
    strategy_label = STRATEGY_LABELS.get(strategy, "按课程证据组织学习")
    raw_factors = intent.get("learner_factors")
    factors = [_clean(item) for item in raw_factors if _clean(item)] if isinstance(raw_factors, (list, tuple)) else []
    if factors:
        factor_text = "和".join(factors[:2])
        return f"结合{factor_text}，采用“{strategy_label}”组织内容，重点{need}。"
    return f"采用“{strategy_label}”组织内容，重点{need}。"


def _cognitive_level(resource_type: str, difficulty: str) -> str:
    levels = COGNITIVE_LEVELS[resource_type]
    return levels[1] if difficulty == "hard" else levels[0]


def _success_criteria(resource_type: str, topic: str) -> tuple[str, ...]:
    common = f"能够用自己的话说明“{topic}”的核心依据"
    specific = {
        "doc": "能够沿关键步骤完成一次解释或推导",
        "mindmap": "能够指出至少两条概念关系并说明方向",
        "quiz": "能够在新情境中作答并解释错误选项",
        "code": "能够运行、修改并解释输出为何符合知识规律",
        "slide": "能够按页面顺序完成一次结构化复述",
        "animation": "能够描述每个场景的状态变化与因果关系",
        "video": "能够说明视频讲解与当前知识点的关联并完成自检",
    }
    return common, specific[resource_type]


def _learner_factors(profile_summary: dict[str, Any]) -> list[str]:
    factors: list[str] = []
    mapping = (
        ("learning_preference", "偏好的学习方式"),
        ("cognitive_style", "更容易理解知识的方式"),
        ("learning_pace", "可持续的学习节奏"),
        ("motivation_interest", "当前学习动力与兴趣"),
        ("major_background", "专业背景"),
    )
    for key, label in mapping:
        if _clean(profile_summary.get(key)):
            factors.append(label)
    if _first_text(profile_summary.get("weak_points")):
        factors.append("当前课程薄弱点")
    if isinstance(profile_summary.get("mastery_average"), (int, float)):
        factors.append("当前课程掌握度")
    if _clean(profile_summary.get("current_task_title")):
        factors.append("当前学习路径任务")
    if isinstance(profile_summary.get("resource_feedback"), dict) and profile_summary["resource_feedback"]:
        factors.append("课程级资源反馈")
    return list(dict.fromkeys(factors))


def _sentences(value: str) -> set[str]:
    parts = re.split(r"[。！？!?；;\n]+", value)
    return {
        normalized
        for part in parts
        if len(normalized := normalized_text(part)) >= 8
    }


def _artifact_sentences(value: object) -> set[str]:
    if isinstance(value, dict):
        structural_keys = {"kind", "citation_refs", "id", "type", "answer", "entry_file"}
        return {
            sentence
            for key, item in value.items()
            if key not in structural_keys
            for sentence in _artifact_sentences(item)
        }
    if isinstance(value, list):
        return {sentence for item in value for sentence in _artifact_sentences(item)}
    if isinstance(value, str):
        return _sentences(value)
    return set()


def _first_text(value: object) -> str:
    if isinstance(value, list):
        return next((_clean(item) for item in value if _clean(item)), "")
    return _clean(value)


def _clean(value: object) -> str:
    cleaned = " ".join(str(value or "").split())
    cleaned = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[已隐藏]", cleaned, flags=re.IGNORECASE)
    for marker in ("系统提示词", "system prompt", "模型输入", "model input", "api key", "资料原文", "raw prompt"):
        cleaned = re.sub(re.escape(marker), "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())[:160]


def _next_value(values: tuple[str, ...], current: str) -> str:
    if current not in values:
        return values[0]
    return values[(values.index(current) + 1) % len(values)]


def _dimension(score: float, rationale: str) -> dict[str, Any]:
    bounded = max(0.0, min(1.0, score))
    return {"status": "passed" if bounded >= 0.6 else "failed", "score": round(bounded, 3), "rationale": rationale}
