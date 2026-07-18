from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import ChatMessage, ChatSession, CourseEnrollment, ProfileEvent, StudentProfile, User
from backend.app.services.auth import AuthService


NOW = datetime(2026, 7, 5, 9, 0, tzinfo=UTC)


def load_profile_module():
    try:
        return importlib.import_module("backend.app.services.profiles")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 profiles 服务模块: {exc.name}")


def load_profile_api_module():
    try:
        return importlib.import_module("backend.app.api.v1.profiles")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 profiles API 模块: {exc.name}")


@dataclass
class FakeProfileRepository:
    profiles: dict[int, StudentProfile] = field(default_factory=dict)
    events: list[ProfileEvent] = field(default_factory=list)
    next_profile_id: int = 1
    next_event_id: int = 1
    pending_profiles: list[StudentProfile] = field(default_factory=list)
    pending_events: list[ProfileEvent] = field(default_factory=list)
    enrollments: dict[tuple[int, int], CourseEnrollment] = field(default_factory=dict)
    committed: bool = False
    rolled_back: bool = False

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.profiles.get(user_id)

    def get_course_enrollment(self, user_id: int, course_id: int) -> CourseEnrollment | None:
        return self.enrollments.get((user_id, course_id))

    def add_profile(self, profile: StudentProfile) -> None:
        self.pending_profiles.append(profile)
        self.profiles[profile.user_id] = profile

    def add_event(self, event: ProfileEvent) -> None:
        self.pending_events.append(event)
        self.events.append(event)

    def list_events(self, user_id: int, limit: int) -> list[ProfileEvent]:
        return sorted(
            [event for event in self.events if event.user_id == user_id],
            key=lambda event: event.created_at,
            reverse=True,
        )[:limit]

    def count_events_for_profile(self, profile_id: int | None) -> int:
        if profile_id is None:
            return 0
        return len([event for event in self.events if event.profile_id == profile_id])

    def flush(self) -> None:
        for profile in self.pending_profiles:
            if profile.id is None:
                profile.id = self.next_profile_id
                self.next_profile_id += 1
            profile.created_at = NOW
            profile.updated_at = NOW
        self.pending_profiles.clear()
        for event in self.pending_events:
            if event.id is None:
                event.id = self.next_event_id
                self.next_event_id += 1
            event.created_at = NOW + timedelta(minutes=event.id)
        self.pending_events.clear()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeProfileModelService:
    responses: list[str]
    messages: list[list[dict[str, str]]] = field(default_factory=list)

    def chat_completion(self, _user: User, messages: list[dict[str, str]]) -> str:
        self.messages.append(messages)
        if not self.responses:
            raise RuntimeError("模型响应已用完")
        return self.responses.pop(0)


def make_user(user_id: int, display_name: str = "画像学生") -> User:
    return User(
        id=user_id,
        account=f"profile{user_id}",
        hashed_password="not-used",
        display_name=display_name,
        role="student",
        starter_mode="blank",
    )


def as_dict(value: Any) -> dict[str, Any]:
    return value.model_dump() if hasattr(value, "model_dump") else value


def make_token(user: User, settings: Settings) -> str:
    return create_access_token(str(user.id), settings=settings)


def make_trace_recorder(logs: list[Any]) -> AgentTraceRecorder:
    def add_log(log):
        logs.append(log)
        return log

    return AgentTraceRecorder(repository_add_log=add_log)


def test_profile_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/profiles/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_empty_profile_returns_stable_eight_dimension_shape() -> None:
    module = load_profile_module()
    user = make_user(1, "空白学生")
    service = module.ProfileService(FakeProfileRepository(), now=NOW)

    profile = as_dict(service.get_my_profile(user))

    assert profile["id"] is None
    assert profile["version"] == 0
    assert profile["has_profile"] is False
    assert profile["profile_json"] == {
        "major_background": "",
        "knowledge_foundation": "",
        "learning_goal": "",
        "cognitive_style": "",
        "learning_preference": "",
        "weak_points": [],
        "learning_pace": "",
        "motivation_interest": "",
    }
    assert profile["confidence_score"] == 0
    assert profile["completeness_score"] == 0
    assert profile["evidence_confidence_score"] == 0
    assert profile["next_question"] == "你更喜欢通过什么形式学习和练习？"
    assert profile["next_question_dimension"] == "learning_preference"


def test_profile_chat_without_model_does_not_guess_profile_updates() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    service = module.ProfileService(repo, now=NOW)

    result = as_dict(
        service.update_by_chat(
            user,
            "我是计算机专业大二学生，机器学习刚入门，数学基础一般，想期末前掌握神经网络。我喜欢案例和图解，每天 45 分钟学习。",
        )
    )

    profile_json = result["profile"]["profile_json"]
    assert all(not value for value in profile_json.values())
    assert result["event"]["dimension"] == "profile_chat"
    assert result["event"]["evidence_json"]["source_type"] == "profile_chat"
    assert "计算机专业大二学生" not in str(result["event"]["evidence_json"])
    assert result["event"]["status"] == "candidate"
    assert result["event"]["evidence_json"]["updated_dimensions"] == []
    assert result["profile"]["version"] == 1
    assert repo.events[0].profile_id == repo.profiles[user.id].id
    assert repo.committed is True


def test_profile_model_extracts_natural_chinese_profile_signals() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"major_background":"计算机专业学生","learning_goal":"系统掌握神经网络",'
            '"learning_preference":"图解、代码","weak_points":["反向传播推导"],'
            '"learning_pace":"每天可以学习四十五分钟"},'
            '"confidence":{"major_background":0.88,"learning_goal":0.86,"learning_preference":0.84,'
            '"weak_points":0.87,"learning_pace":0.82},"uncertain_dimensions":[]}',
            '{"review_status":"passed","confidence":0.88,"risk_flags":[],"safety_summary":"字段来自学生明确表达。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model)

    result = as_dict(
        service.update_by_chat(
            user,
            "我是计算机专业学生，正在学习机器学习，希望系统掌握神经网络；我喜欢图解和代码例子，反向传播推导比较薄弱，每天可以学习四十五分钟。",
        )
    )

    profile = result["profile"]["profile_json"]
    assert profile["major_background"] == "计算机专业学生"
    assert profile["learning_goal"] == ""
    assert profile["learning_preference"] == "图解、代码"
    assert profile["weak_points"] == []
    assert profile["learning_pace"] == "每天可以学习四十五分钟"
    assert result["event"]["evidence_json"]["generation_mode"] == "model_generated"
    assert result["event"]["evidence_json"]["parse_status"] == "valid"


def test_profile_does_not_infer_aspiration_when_model_is_unavailable() -> None:
    module = load_profile_module()
    user = make_user(1)
    service = module.ProfileService(FakeProfileRepository(), now=NOW)

    result = as_dict(service.update_by_chat(user, "想成为AI领域大神，为人类发展做贡献"))

    profile = result["profile"]["profile_json"]
    assert profile["learning_goal"] == ""
    assert profile["motivation_interest"] == ""
    assert result["event"]["status"] == "candidate"
    assert result["event"]["evidence_json"]["generation_mode"] == "rules_only"


def test_profile_model_accepts_explanatory_text_and_partial_valid_fields() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    model = FakeProfileModelService(
        responses=[
            "画像提取结果如下：\n```json\n"
            '{"updates":{"knowledge_foundation":"具备 Python 基础","weak_points":["反向传播推导"],"unknown":"忽略"},'
            '"confidence":{"knowledge_foundation":0.83,"weak_points":0.79},"uncertain_dimensions":[]}\n```',
            '{"review_status":"passed","confidence":0.86,"risk_flags":[],"safety_summary":"画像字段与证据一致。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model)

    result = as_dict(service.update_by_chat(user, "我学过 Python，但反向传播推导比较薄弱。"))

    assert result["profile"]["profile_json"]["knowledge_foundation"] == ""
    assert "knowledge_foundation" not in result["profile"]["dimension_confidence"]
    assert result["profile"]["profile_json"]["weak_points"] == []
    evidence = result["event"]["evidence_json"]
    assert evidence["generation_mode"] == "model_generated"
    assert evidence["parse_status"] == "valid"
    assert evidence["repair_count"] == 0
    assert evidence["review_mode"] == "model_and_rules"
    assert len(model.messages) == 2
    assert "八个字段" in model.messages[0][0]["content"]
    assert "当前画像安全摘要" in model.messages[0][1]["content"]


def test_profile_model_is_authoritative_and_rules_do_not_fill_omitted_dimensions() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"weak_points":["反向传播"],"motivation_interest":"希望进入人工智能领域"},'
            '"confidence":{"weak_points":0.86,"motivation_interest":0.9},"uncertain_dimensions":[]}',
            '{"review_status":"passed","confidence":0.84,"risk_flags":[],"safety_summary":"画像字段与证据一致。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model)

    result = as_dict(
        service.update_by_chat(
            user,
            "希望系统掌握神经网络，反向传播推导比较薄弱。",
        )
    )

    profile = result["profile"]["profile_json"]
    assert profile["learning_goal"] == ""
    assert profile["weak_points"] == []
    assert profile["motivation_interest"] == "希望进入人工智能领域"
    assert "weak_points" not in result["profile"]["dimension_confidence"]
    assert result["event"]["evidence_json"]["updated_dimensions"] == ["motivation_interest"]


def test_profile_model_accepts_semantic_dimension_without_rule_hint() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"motivation_interest":"长期深耕可信人工智能，让技术产生长远价值"},'
            '"confidence":{"motivation_interest":0.88},"uncertain_dimensions":[]}',
            '{"review_status":"passed","confidence":0.87,"risk_flags":[],"safety_summary":"画像字段与证据一致。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model)
    message = "长期深耕可信人工智能，也让技术产生更长远的价值。"

    result = as_dict(service.update_by_chat(user, message))

    assert result["profile"]["profile_json"]["motivation_interest"] == "长期深耕可信人工智能，让技术产生长远价值"
    assert result["event"]["evidence_json"]["generation_mode"] == "model_generated"
    assert result["event"]["evidence_json"]["parse_status"] == "valid"


def test_profile_aspiration_and_contribution_update_goal_and_motivation() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"learning_goal":"成为 AI 领域专业人才",'
            '"motivation_interest":"对 AI 感兴趣，希望为人类发展作贡献"},'
            '"confidence":{"learning_goal":0.9,"motivation_interest":0.92},"uncertain_dimensions":[]}',
            '{"review_status":"passed","confidence":0.9,"risk_flags":[],"safety_summary":"职业愿景和学习动力均来自学生明确表达。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model)

    result = as_dict(service.update_by_chat(user, "想成为AI领域大神，为人类发展做贡献"))

    profile = result["profile"]["profile_json"]
    assert profile["learning_goal"] == ""
    assert profile["motivation_interest"] == "对 AI 感兴趣，希望为人类发展作贡献"
    assert result["event"]["status"] == "applied"
    assert result["event"]["evidence_json"]["updated_dimensions"] == ["motivation_interest"]


def test_profile_review_rejection_discards_unverified_model_dimensions() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"learning_pace":"每天学习两小时"},'
            '"confidence":{"learning_pace":0.91},"uncertain_dimensions":[]}',
            '{"review_status":"revise","confidence":0.35,"risk_flags":["unsupported_dimension"],'
            '"safety_summary":"回答没有提供学习时间。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model)

    result = as_dict(service.update_by_chat(user, "我暂时只想补充一下。"))

    assert result["profile"]["profile_json"]["learning_pace"] == ""
    assert result["event"]["status"] == "candidate"
    assert result["event"]["evidence_json"]["generation_mode"] == "rules_only"
    assert result["event"]["evidence_json"]["parse_status"] == "review_fallback"


def test_profile_model_repairs_invalid_json_once() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    logs: list[Any] = []
    model = FakeProfileModelService(
        responses=[
            "我认为学生更喜欢图解，但这里没有按 JSON 输出。",
            '{"updates":{"learning_preference":"图解、代码"},"confidence":{"learning_preference":0.81},"uncertain_dimensions":[]}',
            '{"review_status":"passed","confidence":0.82,"risk_flags":[],"safety_summary":"画像字段与证据一致。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model, trace_recorder=make_trace_recorder(logs))

    result = as_dict(service.update_by_chat(user, "我更喜欢图解和代码。"))

    evidence = result["event"]["evidence_json"]
    assert evidence["generation_mode"] == "model_generated"
    assert evidence["parse_status"] == "repaired"
    assert evidence["repair_count"] == 1
    extract_log = next(log for log in logs if log.agent_name == "extract")
    assert extract_log.metadata_json["extraction_mode"] == "model_generated"
    assert extract_log.metadata_json["parse_status"] == "repaired"
    assert extract_log.metadata_json["extracted_dimension_count"] == 1
    assert "我更喜欢图解和代码" not in str(extract_log.metadata_json)


def test_profile_model_invalid_twice_falls_back_without_fake_model_review() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    model = FakeProfileModelService(responses=["不是 JSON", "仍然不是 JSON"])
    service = module.ProfileService(repo, now=NOW, model_service=model)

    result = as_dict(service.update_by_chat(user, "反向传播推导比较薄弱，每天学习四十五分钟。"))

    assert result["profile"]["profile_json"]["weak_points"] == []
    evidence = result["event"]["evidence_json"]
    assert evidence["generation_mode"] == "rules_only"
    assert evidence["parse_status"] == "fallback"
    assert evidence["repair_count"] == 1
    assert evidence["review_mode"] == "rules_only"
    assert len(model.messages) == 2


def test_uncertain_explicit_statement_stays_candidate() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"learning_preference":"视频学习"},'
            '"confidence":{"learning_preference":0.72},"uncertain_dimensions":["learning_preference"]}',
            '{"review_status":"passed","confidence":0.75,"risk_flags":[],"safety_summary":"表达含有不确定性。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model)

    result = as_dict(service.update_by_chat(user, "我好像更喜欢视频学习，但还不确定。"))

    assert result["profile"]["profile_json"]["learning_preference"] == ""
    assert result["event"]["status"] == "candidate"
    assert result["event"]["evidence_json"]["candidate_dimensions"] == ["learning_preference"]


def test_profile_rules_do_not_invent_updates_from_negated_preferences_or_weaknesses() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    service = module.ProfileService(repo, now=NOW)

    result = as_dict(service.update_by_chat(user, "我不喜欢视频，反向传播并不薄弱，也没有卡住。"))

    assert result["profile"]["profile_json"]["learning_preference"] == ""
    assert result["profile"]["profile_json"]["weak_points"] == []
    assert result["event"]["status"] == "candidate"
    assert result["event"]["evidence_json"]["updated_dimensions"] == []
    assert result["event"]["evidence_json"]["candidate_dimensions"] == []


def test_explicit_profile_statement_updates_existing_dimension() -> None:
    module = load_profile_module()
    user = make_user(1)
    profile = StudentProfile(
        id=7,
        user_id=1,
        profile_json={"learning_goal": "掌握机器学习"},
        confidence_score=Decimal("72"),
        dimension_confidence_json={"learning_goal": 72},
    )
    repo = FakeProfileRepository(profiles={1: profile})
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"learning_goal":"完成深度学习项目"},'
            '"confidence":{"learning_goal":0.91},"uncertain_dimensions":[]}',
            '{"review_status":"passed","confidence":0.9,"risk_flags":[],"safety_summary":"目标来自学生明确表达。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model)

    result = as_dict(service.update_by_chat(user, "我的目标是完成深度学习项目。"))

    assert result["profile"]["profile_json"]["learning_goal"] == "掌握机器学习"
    assert result["event"]["status"] == "candidate"


def test_profile_next_question_targets_missing_or_low_confidence_dimension() -> None:
    module = load_profile_module()
    user = make_user(1)
    profile = StudentProfile(
        id=7,
        user_id=1,
        profile_json={
            "major_background": "计算机专业",
            "knowledge_foundation": "具备 Python 基础",
            "learning_goal": "掌握机器学习",
            "cognitive_style": "结构化理解",
            "learning_preference": "图解、代码",
            "weak_points": ["反向传播"],
            "learning_pace": "每天四十五分钟",
            "motivation_interest": "完成 AI 项目",
        },
        confidence_score=Decimal("70"),
        dimension_confidence_json={
            "major_background": 82,
            "knowledge_foundation": 78,
            "learning_goal": 90,
            "cognitive_style": 76,
            "learning_preference": 84,
            "weak_points": 42,
            "learning_pace": 75,
            "motivation_interest": 80,
        },
    )
    service = module.ProfileService(FakeProfileRepository(profiles={1: profile}), now=NOW)

    result = as_dict(service.get_my_profile(user))

    assert result["next_question"] == "目前哪些内容最容易让你卡住或出错？"
    assert result["next_question_dimension"] == "weak_points"


def test_profile_next_question_reports_preferred_unresolved_dimension() -> None:
    module = load_profile_module()
    profile = StudentProfile(
        id=7,
        user_id=1,
        profile_json={"learning_goal": "掌握机器学习"},
        confidence_score=Decimal("72"),
        dimension_confidence_json={"learning_goal": 72},
    )
    service = module.ProfileService(FakeProfileRepository(profiles={1: profile}), now=NOW)

    dimension, question = service._next_question_target(profile, ["cognitive_style"])

    assert dimension == "cognitive_style"
    assert question == "遇到新知识时，你通常怎样更容易弄懂？"

    dimension, question = service._next_question_target(profile, ["learning_preference"])

    assert dimension == "learning_preference"
    assert question == "你更喜欢通过什么形式学习和练习？"


def test_profile_graph_records_real_nodes_and_dimension_confidence() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    logs: list[Any] = []
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"major_background":"计算机专业大二学生","knowledge_foundation":"机器学习刚入门",'
            '"learning_goal":"掌握神经网络"},'
            '"confidence":{"major_background":0.83,"knowledge_foundation":0.81,"learning_goal":0.86},'
            '"uncertain_dimensions":[]}',
            '{"review_status":"passed","confidence":0.88,"risk_flags":[],"safety_summary":"字段来自明确表达。"}',
        ]
    )
    service = module.ProfileService(repo, now=NOW, model_service=model, trace_recorder=make_trace_recorder(logs))

    result = as_dict(service.update_by_chat(user, "我是计算机专业大二学生，机器学习刚入门，想掌握神经网络。"))

    assert [log.agent_name for log in logs] == [
        "collect_context",
        "extract",
        "evidence_gate",
        "review",
        "apply",
        "persist_event",
    ]
    assert len({log.trace_id for log in logs}) == 1
    assert result["event"]["agent_trace_id"] == logs[0].trace_id
    assert result["event"]["status"] == "applied"
    assert result["profile"]["dimension_confidence"]["major_background"] == 83
    assert result["profile"]["completeness_score"] == 12.5
    assert result["profile"]["evidence_confidence_score"] == 83.0
    assert "计算机专业大二学生" not in str(logs[0].metadata_json)


def test_learning_signal_requires_two_independent_sources_before_applying() -> None:
    module = load_profile_module()
    user = make_user(1)
    enrollment = CourseEnrollment(
        user_id=user.id,
        course_id=101,
        role="learner",
        progress_percent=0,
        learning_context_json={},
        learning_context_confidence_json={},
    )
    repo = FakeProfileRepository(enrollments={(user.id, 101): enrollment})
    service = module.ProfileService(repo, now=NOW)

    first = service.ingest_learning_signal(
        user=user,
        source_type="practice_assessment",
        source_ref_type="practice_session",
        source_ref_id=501,
        suggested_updates={"weak_points": ["反向传播"]},
        course_id=101,
    )
    second = service.ingest_learning_signal(
        user=user,
        source_type="course_tutor",
        source_ref_type="chat_message",
        source_ref_id=502,
        suggested_updates={"weak_points": ["反向传播"]},
        course_id=101,
    )

    assert first is not None and first.status == "candidate"
    assert second is not None and second.status == "applied"
    assert repo.profiles[user.id].profile_json["weak_points"] == []
    assert enrollment.learning_context_json["weak_points"] == ["反向传播"]
    assert second.course_id == 101
    assert {event.source_ref_id for event in repo.events} == {501, 502}


def test_profile_events_are_current_user_only_and_descending() -> None:
    module = load_profile_module()
    user = make_user(1)
    profile = StudentProfile(
        id=7,
        user_id=1,
        profile_json={"learning_goal": "期末复习"},
        confidence_score=Decimal("0.50"),
    )
    old_event = ProfileEvent(
        id=1,
        user_id=1,
        profile_id=7,
        dimension="profile_chat",
        change_summary="旧事件",
        evidence_json={"source_type": "profile_chat"},
    )
    old_event.created_at = NOW
    new_event = ProfileEvent(
        id=2,
        user_id=1,
        profile_id=7,
        dimension="weak_points",
        change_summary="新事件",
        evidence_json={"source_type": "course_question"},
    )
    new_event.created_at = NOW + timedelta(minutes=3)
    other_event = ProfileEvent(
        id=3,
        user_id=2,
        profile_id=None,
        dimension="profile_chat",
        change_summary="别人事件",
        evidence_json={},
    )
    other_event.created_at = NOW + timedelta(minutes=5)
    service = module.ProfileService(
        FakeProfileRepository(profiles={1: profile}, events=[old_event, new_event, other_event]),
        now=NOW,
    )

    events = [as_dict(event) for event in service.list_events(user)]
    profile_data = as_dict(service.get_my_profile(user))

    assert [event["change_summary"] for event in events] == ["新事件", "旧事件"]
    assert profile_data["version"] == 2


def test_course_question_profile_event_requires_model_signal_and_course_evidence() -> None:
    module = load_profile_module()
    user = make_user(1)
    profile = StudentProfile(
        id=9,
        user_id=1,
        profile_json={"learning_goal": "复习 AI"},
        confidence_score=Decimal("0.60"),
    )
    repo = FakeProfileRepository(profiles={1: profile})
    service = module.ProfileService(repo, now=NOW)
    session = ChatSession(id=3, user_id=1, course_id=7, scope="course", title="课程答疑", mode="chat")
    user_message = ChatMessage(id=11, session_id=3, user_id=1, role="user", content="为什么启发式搜索这么难？")
    citations = [
        {
            "chunk_id": 501,
            "knowledge_point_id": 401,
            "source_title": "人工智能导论讲义.md",
            "section_title": "启发式搜索",
            "content": "启发式搜索利用启发函数估计路径代价。",
        }
    ]

    event = service.ingest_course_question_signal(
        user=user,
        session=session,
        user_message=user_message,
        message_text="为什么启发式搜索这么难？",
        citation_json=citations,
        trace_id="trace_model_test",
        suggested_updates={"weak_points": ["启发式搜索"]},
        suggested_confidence={"weak_points": 0.88},
    )
    ignored = service.ingest_course_question_signal(
        user=user,
        session=session,
        user_message=user_message,
        message_text="解释一下启发式搜索",
        citation_json=citations,
        trace_id="trace_model_test",
    )

    assert ignored is None
    assert event is not None
    assert event.dimension == "weak_points"
    assert event.profile_id == 9
    assert event.status == "candidate"
    assert event.proposal_json == {"weak_points": ["启发式搜索"]}
    assert event.evidence_json["source_type"] == "course_question"
    assert event.evidence_json["dimension_extraction_confidence"] == {"weak_points": 0.88}
    assert "为什么启发式搜索这么难" not in str(event.evidence_json)
    assert "启发式搜索利用启发函数" not in str(event.evidence_json)


def test_profile_routes_read_update_and_list_current_user_profile() -> None:
    module = load_profile_module()
    api_module = load_profile_api_module()
    user = make_user(1, "接口学生")
    settings = Settings(
        _env_file=None,
        jwt_secret="profile-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
    )
    repo = FakeProfileRepository()
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    model = FakeProfileModelService(
        responses=[
            '{"updates":{"major_background":"计算机专业大二学生","knowledge_foundation":"机器学习刚入门",'
            '"learning_goal":"期末前掌握神经网络"},'
            '"confidence":{"major_background":0.86,"knowledge_foundation":0.82,"learning_goal":0.9},'
            '"uncertain_dimensions":[]}',
            '{"review_status":"passed","confidence":0.88,"risk_flags":[],"safety_summary":"字段来自明确表达。"}',
        ]
    )
    app.dependency_overrides[api_module.get_profile_service] = lambda: module.ProfileService(
        repo,
        now=NOW,
        model_service=model,
    )
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {make_token(user, settings)}"}

    empty_response = client.get("/api/v1/profiles/me", headers=headers)
    chat_response = client.post(
        "/api/v1/profiles/chat",
        headers=headers,
        json={"message": "我是计算机专业大二学生，机器学习刚入门，想期末前掌握神经网络。"},
    )
    events_response = client.get("/api/v1/profiles/events", headers=headers)
    invalid_response = client.post("/api/v1/profiles/chat", headers=headers, json={"message": ""})
    whitespace_response = client.post("/api/v1/profiles/chat", headers=headers, json={"message": "   "})

    assert empty_response.status_code == 200
    assert empty_response.json()["data"]["has_profile"] is False
    assert chat_response.status_code == 200
    assert chat_response.json()["data"]["profile"]["has_profile"] is True
    assert chat_response.json()["data"]["profile"]["profile_json"]["major_background"] == "计算机专业大二学生"
    assert events_response.status_code == 200
    assert [event["dimension"] for event in events_response.json()["data"]] == ["profile_chat"]
    assert invalid_response.status_code == 422
    assert whitespace_response.status_code == 422
