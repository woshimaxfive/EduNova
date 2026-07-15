from types import SimpleNamespace

from backend.app.services.semantic_decision import SemanticDecisionService


class FakeModel:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def chat_completion(self, user, messages):
        self.calls.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


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
