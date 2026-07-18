from types import SimpleNamespace

from backend.app.services.semantic_decision import SemanticDecisionService


class FakeModel:
    def __init__(self, response: str | Exception | list[str | Exception]) -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def chat_completion(self, user, messages):
        self.calls.append(messages)
        response = self.response.pop(0) if isinstance(self.response, list) else self.response
        if isinstance(response, Exception):
            raise response
        return response


def user():
    return SimpleNamespace(id=1)


def test_resource_recommendation_is_decided_by_model_semantics() -> None:
    model = FakeModel(
        '{"intent":"external_resource_recommendation","search_required":true,'
        '"search_query":"Java 初学者 官方视频教程","reasoning_mode":"auto",'
        '"course_related":false,"confidence":0.94,"reason_codes":["external_resource"],'
        '"reason_summary":"需要检索真实可访问的外部学习资源。","profile_signals":[]}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="可以推荐一些 Java 学习视频吗？", scope="home"
    )

    assert decision.search_required is True
    assert decision.search_query == "Java 初学者 官方视频教程"
    assert decision.intent == "external_resource_recommendation"
    assert decision.decision_mode == "model"
    assert decision.source_scope == "mainland_preferred"


def test_semantic_decision_normalizes_known_resource_difficulty_alias() -> None:
    model = FakeModel(
        '{"intent":"material_question","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.9,'
        '"reason_codes":["course_question"],"reason_summary":"课程内概念问题。",'
        '"profile_signals":[],"resource_difficulty":"中等"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="二叉树前序遍历是什么？", scope="course", course_title="数据结构"
    )

    assert decision.decision_mode == "model"
    assert decision.resource_difficulty == "medium"


def test_semantic_decision_normalizes_difficulty_wrapper() -> None:
    model = FakeModel(
        '{"intent":"material_question","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.9,'
        '"reason_codes":["course_question"],"reason_summary":"课程内概念问题。",'
        '"profile_signals":[],"resource_difficulty":"中等难度"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="二叉树前序遍历是什么？", scope="course", course_title="数据结构"
    )

    assert decision.decision_mode == "model"
    assert decision.resource_difficulty == "medium"


def test_semantic_decision_normalizes_non_resource_difficulty_placeholder() -> None:
    model = FakeModel(
        '{"intent":"material_question","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.9,'
        '"reason_codes":["course_question"],"reason_summary":"课程内概念问题。",'
        '"profile_signals":[],"resource_difficulty":"N/A"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="二叉树前序遍历是什么？", scope="course", course_title="数据结构"
    )

    assert decision.decision_mode == "model"
    assert decision.resource_difficulty == "medium"


def test_semantic_decision_keeps_unknown_difficulty_strict_for_resource_action() -> None:
    model = FakeModel(
        '{"intent":"learning_resource_generation","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.9,'
        '"reason_codes":["resource_generation"],"reason_summary":"生成课程资源。",'
        '"profile_signals":[],"resource_action":"generate","resource_types":["mindmap"],'
        '"resource_difficulty":"unrecognized"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="生成一份二叉树思维导图", scope="course", course_title="数据结构"
    )

    assert decision.decision_mode == "degraded"


def test_model_can_request_global_original_sources_without_keyword_fallback() -> None:
    model = FakeModel(
        '{"intent":"verification","search_required":true,"search_query":"RFC 9110 original",'
        '"reasoning_mode":"deep","source_scope":"global_required","course_related":false,'
        '"confidence":0.96,"reason_codes":["international_primary_source"],'
        '"reason_summary":"需要核对国际原始规范。","profile_signals":[]}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="请按 RFC 9110 原文核实这个 HTTP 结论", scope="home"
    )

    assert decision.source_scope == "global_required"


def test_complex_question_uses_deep_without_forcing_search() -> None:
    model = FakeModel(
        '{"intent":"comparison","search_required":false,"search_query":"",'
        '"reasoning_mode":"deep","course_related":true,"confidence":0.9,'
        '"reason_codes":["multi_step_reasoning"],"reason_summary":"需要多步比较。",'
        '"profile_signals":[]}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="比较 AVL 树和红黑树的工程权衡", scope="course", course_title="数据结构"
    )

    assert decision.search_required is False
    assert decision.reasoning_mode == "deep"
    assert decision.course_related is True


def test_course_profile_signal_requires_explicit_high_confidence_expression() -> None:
    model = FakeModel(
        '{"intent":"material_question","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.91,'
        '"reason_codes":["course_question"],"reason_summary":"课程内概念问题。",'
        '"profile_signals":['
        '{"dimension":"weak_points","value":"红黑树旋转","confidence":0.88,"explicit":true},'
        '{"dimension":"learning_goal","value":"掌握树结构","confidence":0.5,"explicit":true},'
        '{"dimension":"learning_preference","value":"视频","confidence":0.9,"explicit":false}]}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="我一直不会红黑树旋转", scope="course", course_title="数据结构"
    )

    assert decision.profile_updates == {"weak_points": ["红黑树旋转"]}
    assert decision.profile_confidence == {"weak_points": 0.88}


def test_invalid_model_output_uses_visible_conservative_degradation() -> None:
    decision = SemanticDecisionService(FakeModel("not-json")).decide(
        user=user(), question="推荐一些教程", scope="home"
    )

    assert decision.search_required is False
    assert decision.reasoning_mode == "auto"
    assert decision.decision_mode == "degraded"
    assert decision.warning


def test_legacy_force_overrides_model_false() -> None:
    model = FakeModel(
        '{"intent":"general_learning","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":false,"confidence":0.8,'
        '"reason_codes":[],"reason_summary":"普通解释。","profile_signals":[]}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="解释栈", scope="home", force_search=True, force_deep=True
    )

    assert decision.search_required is True
    assert decision.reasoning_mode == "deep"
    assert decision.decision_mode == "model_forced"


def test_provider_specific_intent_and_empty_object_profile_signals_remain_usable() -> None:
    model = FakeModel(
        '{"intent":"video_recommendation","search_required":true,'
        '"search_query":"Java learning video tutorials","reasoning_mode":"auto",'
        '"course_related":false,"confidence":0.92,"reason_codes":["SEARCH_REQUIRED"],'
        '"reason_summary":"需要外部视频资源。","profile_signals":{}}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="可以给我一些 Java 学习的视频吗？", scope="home"
    )

    assert decision.decision_mode == "model"
    assert decision.intent == "video_recommendation"
    assert decision.search_required is True


def test_model_rewrites_follow_up_using_real_turn_ids() -> None:
    model = FakeModel(
        '{"intent":"follow_up","search_required":false,"search_query":"","reasoning_mode":"auto",'
        '"course_related":false,"confidence":0.95,"reason_codes":["history_reference"],'
        '"reason_summary":"用户要求回顾上一轮。","profile_signals":[],'
        '"standalone_query":"回顾上一轮对机器学习的定义","uses_history":true,'
        '"referenced_turn_ids":["message-8"]}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(),
        question="还记得上面说过什么吗？",
        scope="home",
        conversation_messages=[{"role": "assistant", "content": "机器学习是从数据中学习规律。", "turn_id": "message-8"}],
    )

    assert decision.uses_history is True
    assert decision.standalone_query == "回顾上一轮对机器学习的定义"
    assert decision.referenced_turn_ids == ("message-8",)


def test_course_evidence_assessment_rejects_unreturned_citation_ids() -> None:
    model = FakeModel(
        '{"relation_type":"adjacent","relevant_citation_ids":["12","forged"],'
        '"course_evidence_sufficient":false,"external_search_helpful":true,'
        '"confidence":0.89,"reason_summary":"主题相邻但教材依据不足。"}'
    )

    result = SemanticDecisionService(model).assess_course_evidence(
        user=user(),
        question="B 树为什么适合数据库索引？",
        course_title="数据结构",
        citations=[{"chunk_id": 12, "source_title": "树", "content": "B 树保持较低树高。"}],
    )

    assert result is not None
    assert result["relation_type"] == "adjacent"
    assert result["relevant_citation_ids"] == ["12"]
    assert result["external_search_helpful"] is True


def test_explicit_resource_generation_is_model_decided_without_keyword_rules() -> None:
    model = FakeModel(
        '{"intent":"learning_resource_generation","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.95,'
        '"reason_codes":["explicit_resource_generation"],"reason_summary":"用户明确要求生成配套资源。",'
        '"profile_signals":[],"resource_action":"generate",'
        '"resource_types":["mindmap","quiz"],"resource_difficulty":"medium",'
        '"resource_learning_goal":"用图解和练习掌握二叉树遍历",'
        '"resource_reason_summary":"图解建立结构，练习检验理解。"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="给我换两种方式把这节内容做成可以学习的材料", scope="course"
    )

    assert decision.resource_action == "generate"
    assert decision.response_mode == "action"
    assert decision.resource_types == ("mindmap", "quiz")
    assert decision.resource_learning_goal == "用图解和练习掌握二叉树遍历"


def test_explanation_plus_resource_generation_keeps_answer_and_action() -> None:
    model = FakeModel(
        '{"intent":"learning_resource_generation","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.94,'
        '"reason_codes":["explain_then_generate"],"reason_summary":"先讲解再生成图解。",'
        '"profile_signals":[],"resource_action":"generate","answer_requested":true,'
        '"response_mode":"answer_and_action",'
        '"resource_types":["mindmap"],"resource_difficulty":"medium",'
        '"resource_learning_goal":"理解二叉树遍历后生成图解",'
        '"resource_reason_summary":"讲解与图解都由用户明确要求。"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="先解释二叉树遍历，再给我生成一张思维导图", scope="course"
    )

    assert decision.resource_action == "generate"
    assert decision.response_mode == "answer_and_action"


def test_resource_generation_cannot_claim_combined_answer_without_explicit_answer_request() -> None:
    model = FakeModel(
        '{"intent":"learning_resource_generation","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.95,'
        '"reason_codes":["explicit_resource_generation"],"reason_summary":"用户只要求生成图解。",'
        '"profile_signals":[],"resource_action":"generate","answer_requested":false,'
        '"response_mode":"answer_and_action","resource_types":["mindmap"],'
        '"resource_difficulty":"medium","resource_learning_goal":"梳理二叉树遍历",'
        '"resource_reason_summary":"生成一份图解资源。"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="请给二叉树遍历生成一张思维导图", scope="home"
    )

    assert decision.resource_action == "generate"
    assert decision.response_mode == "action"


def test_empty_collection_history_flag_does_not_discard_valid_resource_decision() -> None:
    model = FakeModel(
        '{"intent":"learning_resource_generation","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.95,'
        '"reason_codes":["explicit_resource_generation"],"reason_summary":"用户明确要求生成配套资源。",'
        '"profile_signals":[],"uses_history":[],"resource_action":"generate",'
        '"resource_types":["mindmap","quiz"],"resource_difficulty":"medium",'
        '"resource_learning_goal":"掌握二叉树遍历",'
        '"resource_reason_summary":"图解建立结构，练习检验理解。"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="请生成思维导图和练习题", scope="home"
    )

    assert decision.decision_mode == "model"
    assert decision.uses_history is False
    assert decision.resource_action == "generate"


def test_scalar_reason_code_does_not_discard_valid_resource_decision() -> None:
    model = FakeModel(
        '{"intent":"material_question","search_required":false,"search_query":"二叉树知识导图",'
        '"reasoning_mode":"auto","source_scope":"mainland_preferred","course_related":true,'
        '"confidence":0.95,"reason_codes":"none","reason_summary":"稳定学科知识。",'
        '"profile_signals":[],"standalone_query":"生成二叉树的知识导图","uses_history":[],'
        '"referenced_turn_ids":[],"resource_action":"generate","resource_types":["mindmap"],'
        '"resource_difficulty":"medium","resource_learning_goal":"系统梳理二叉树核心概念",'
        '"resource_reason_summary":"使用思维导图整理定义和遍历方法。",'
        '"answer_requested":false,"response_mode":"action"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="生成二叉树的知识导图", scope="home"
    )

    assert decision.decision_mode == "model"
    assert decision.resource_action == "generate"
    assert decision.resource_types == ("mindmap",)
    assert decision.response_mode == "action"


def test_non_boolean_history_container_does_not_discard_valid_resource_decision() -> None:
    model = FakeModel(
        '{"intent":"material_question","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","source_scope":"mainland_preferred","course_related":true,'
        '"confidence":0.95,"reason_codes":["resource_generation"],'
        '"reason_summary":"生成课程资源。","profile_signals":[],'
        '"standalone_query":"生成广义表的思维导图",'
        '"uses_history":[{"turn_id":"121","content":"生成广义表的思维导图"}],'
        '"referenced_turn_ids":["121"],"resource_action":"generate",'
        '"resource_types":["mindmap"],"resource_difficulty":"medium",'
        '"resource_topic":"广义表",'
        '"resource_learning_goal":"梳理广义表知识",'
        '"resource_reason_summary":"使用思维导图整理。",'
        '"answer_requested":false,"response_mode":"action"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="生成广义表的思维导图", scope="course"
    )

    assert len(model.calls) == 1
    assert decision.decision_mode == "model"
    assert decision.uses_history is True
    assert decision.resource_action == "generate"
    assert decision.resource_types == ("mindmap",)
    assert decision.resource_topic == "广义表"
    assert decision.response_mode == "action"


def test_invalid_structured_decision_gets_one_model_repair_before_degrading() -> None:
    valid = (
        '{"intent":"material_question","search_required":false,"search_query":"二叉树知识导图",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.95,'
        '"reason_codes":["resource_generation"],"reason_summary":"生成课程资源。",'
        '"profile_signals":[],"standalone_query":"生成二叉树的知识导图","uses_history":false,'
        '"referenced_turn_ids":[],"resource_action":"generate","resource_types":["mindmap"],'
        '"resource_difficulty":"medium","resource_learning_goal":"梳理二叉树知识",'
        '"resource_reason_summary":"使用思维导图整理。","answer_requested":false,"response_mode":"action"}'
    )
    model = FakeModel(['{"intent":"material_question","profile_signals":"invalid"}', valid])

    decision = SemanticDecisionService(model).decide(
        user=user(), question="生成二叉树的知识导图", scope="home"
    )

    assert len(model.calls) == 2
    assert decision.decision_mode == "model"
    assert decision.reason_codes[0] == "structured_repair"
    assert decision.resource_action == "generate"
    assert decision.response_mode == "action"


def test_valid_resource_subdecision_survives_unrelated_semantic_schema_failures() -> None:
    invalid_full_but_valid_resource = (
        '{"intent":"material_question","search_required":false,"reasoning_mode":"auto",'
        '"confidence":0.95,"reason_codes":"none","reason_summary":"生成课程资源。",'
        '"profile_signals":"invalid","uses_history":"invalid","resource_action":"generate",'
        '"resource_types":["mindmap"],"resource_difficulty":"medium",'
        '"resource_learning_goal":"梳理二叉树知识",'
        '"resource_reason_summary":"使用思维导图整理。","answer_requested":false,"response_mode":"action"}'
    )
    model = FakeModel([invalid_full_but_valid_resource, invalid_full_but_valid_resource])

    decision = SemanticDecisionService(model).decide(
        user=user(), question="生成二叉树的知识导图", scope="home"
    )

    assert len(model.calls) == 2
    assert decision.decision_mode == "model"
    assert decision.reason_codes == ("resource_decision_salvaged",)
    assert decision.resource_action == "generate"
    assert decision.resource_types == ("mindmap",)
    assert decision.response_mode == "action"
    assert decision.search_required is False
    assert decision.profile_updates == {}


def test_ambiguous_learning_need_only_returns_confirmable_suggestion() -> None:
    model = FakeModel(
        '{"intent":"learning_support","search_required":false,"search_query":"",'
        '"reasoning_mode":"auto","course_related":true,"confidence":0.83,'
        '"reason_codes":["visual_support_helpful"],"reason_summary":"图解可能帮助理解。",'
        '"profile_signals":[],"resource_action":"suggest","resource_types":["mindmap"],'
        '"resource_difficulty":"easy","resource_learning_goal":"梳理状态变化",'
        '"resource_reason_summary":"建议先用图解确认状态关系。"}'
    )

    decision = SemanticDecisionService(model).decide(
        user=user(), question="我还是有点绕，有没有更直观的办法？", scope="course"
    )

    assert decision.resource_action == "suggest"
    assert decision.resource_types == ("mindmap",)
