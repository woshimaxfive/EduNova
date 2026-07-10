from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    AssessmentReport,
    Course,
    GeneratedResource,
    KnowledgePoint,
    PracticeAnswer,
    PracticeSession,
    StudentProfile,
    User,
    WeaknessReviewItem,
)
from backend.app.services.auth import AuthService


NOW = datetime(2026, 7, 5, 10, 0, tzinfo=UTC)


@dataclass
class FakeModelService:
    responses: list[str]
    calls: list[list[dict[str, str]]] = field(default_factory=list)

    def chat_completion(self, _user: User, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.responses.pop(0)


class FailingPathService:
    def replan_after_assessment(self, _user: User, _course_id: int, _assessment_session_id: int):
        raise RuntimeError("path failed")


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakePracticeRepository:
    courses: list[Course] = field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)
    resources: list[GeneratedResource] = field(default_factory=list)
    sessions: list[PracticeSession] = field(default_factory=list)
    answers: list[PracticeAnswer] = field(default_factory=list)
    weakness_items: list[WeaknessReviewItem] = field(default_factory=list)
    reports: list[AssessmentReport] = field(default_factory=list)
    profiles: dict[int, StudentProfile] = field(default_factory=dict)
    next_session_id: int = 501
    next_answer_id: int = 601
    next_weakness_id: int = 701
    next_report_id: int = 801
    committed: bool = False

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.id == course_id and course.owner_id == user_id), None)

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return sorted(
            [point for point in self.knowledge_points if point.course_id == course_id],
            key=lambda point: (point.order_index, point.id),
        )

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return [resource for resource in self.resources if resource.user_id == user_id and resource.course_id == course_id]

    def add_practice_session(self, session: PracticeSession) -> PracticeSession:
        session.id = self.next_session_id
        self.next_session_id += 1
        session.created_at = NOW
        session.updated_at = NOW
        self.sessions.append(session)
        return session

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None:
        return next((session for session in self.sessions if session.id == session_id and session.user_id == user_id), None)

    def get_latest_completed_practice_session(self, user_id: int, course_id: int) -> PracticeSession | None:
        sessions = [
            session
            for session in self.sessions
            if session.user_id == user_id and session.course_id == course_id and session.status == "completed"
        ]
        return sorted(sessions, key=lambda session: (session.updated_at, session.id), reverse=True)[0] if sessions else None

    def get_latest_practice_session_for_user(self, user_id: int, course_id: int) -> PracticeSession | None:
        sessions = [
            session
            for session in self.sessions
            if session.user_id == user_id and session.course_id == course_id
        ]
        return sorted(
            sessions,
            key=lambda session: (session.status == "in_progress", session.updated_at, session.id),
            reverse=True,
        )[0] if sessions else None

    def list_recent_completed_practice_sessions(self, user_id: int, course_id: int, limit: int = 5) -> list[PracticeSession]:
        sessions = [
            session
            for session in self.sessions
            if session.user_id == user_id and session.course_id == course_id and session.status == "completed"
        ]
        return sorted(sessions, key=lambda session: (session.updated_at, session.id), reverse=True)[:limit]

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]:
        return sorted([answer for answer in self.answers if answer.session_id == session_id], key=lambda answer: answer.id)

    def list_answers_for_course(self, user_id: int, course_id: int) -> list[PracticeAnswer]:
        session_ids = {
            session.id
            for session in self.sessions
            if session.user_id == user_id and session.course_id == course_id
        }
        return [answer for answer in self.answers if answer.session_id in session_ids]

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.profiles.get(user_id)

    def replace_answers_for_session(self, session_id: int, answers: list[PracticeAnswer]) -> list[PracticeAnswer]:
        self.answers = [answer for answer in self.answers if answer.session_id != session_id]
        for answer in answers:
            answer.id = self.next_answer_id
            self.next_answer_id += 1
            answer.created_at = NOW
            self.answers.append(answer)
        return answers

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return [item for item in self.weakness_items if item.user_id == user_id and item.course_id == course_id]

    def add_weakness_review_item(self, item: WeaknessReviewItem) -> WeaknessReviewItem:
        item.id = self.next_weakness_id
        self.next_weakness_id += 1
        item.created_at = NOW
        item.updated_at = NOW
        self.weakness_items.append(item)
        return item

    def add_assessment_report(self, report: AssessmentReport) -> AssessmentReport:
        report.id = self.next_report_id
        self.next_report_id += 1
        report.created_at = NOW
        self.reports.append(report)
        return report

    def get_latest_report(self, user_id: int, course_id: int) -> AssessmentReport | None:
        reports = [report for report in self.reports if report.user_id == user_id and report.course_id == course_id]
        return sorted(reports, key=lambda report: (report.created_at, report.id), reverse=True)[0] if reports else None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        return None

    def refresh(self, _instance: object) -> None:
        return None


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@edunova.local",
        hashed_password="not-used",
        display_name=f"学生 {user_id}",
        role="student",
        starter_mode="blank",
    )


def make_course(course_id: int = 101, owner_id: int = 1) -> Course:
    return Course(
        id=course_id,
        owner_id=owner_id,
        title="人工智能导论",
        description="课程资料",
        subject="人工智能",
        source_type="uploaded",
        visibility="private",
        status="ready",
    )


def make_point(point_id: int, title: str, order_index: int, course_id: int = 101) -> KnowledgePoint:
    return KnowledgePoint(
        id=point_id,
        course_id=course_id,
        title=title,
        summary=f"{title} 的课程摘要，包含关键概念、常见误区和复习线索。",
        chapter="第一章",
        order_index=order_index,
        difficulty=None,
        prerequisites_json=[],
    )


def make_resource(resource_id: int, point_id: int, title: str) -> GeneratedResource:
    return GeneratedResource(
        id=resource_id,
        user_id=1,
        course_id=101,
        knowledge_point_id=point_id,
        resource_type="doc",
        title=title,
        content_json={"markdown": "安全资源摘要", "metadata": {"agent_trace_id": "trace_resource"}},
        citation_json=[],
        status="completed",
        review_status="passed",
        confidence_score=Decimal("0.88"),
        created_at=NOW,
        updated_at=NOW,
    )


def make_repo() -> FakePracticeRepository:
    return FakePracticeRepository(
        courses=[make_course(), make_course(202, owner_id=2)],
        knowledge_points=[
            make_point(401, "人工智能概述", 0),
            make_point(402, "启发式搜索", 1),
            make_point(499, "其他课程知识点", 0, course_id=202),
        ],
        resources=[make_resource(901, 401, "人工智能概述讲解"), make_resource(902, 402, "启发式搜索练习")],
    )


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def make_trace_recorder(logs: list[Any]) -> AgentTraceRecorder:
    def add_log(log):
        logs.append(log)
        return log

    return AgentTraceRecorder(repository_add_log=add_log)


def test_create_practice_session_generates_deterministic_questions_and_validates_scope() -> None:
    from backend.app.services.practice import PracticeNotFoundError, PracticeService, PracticeValidationError

    repo = make_repo()
    service = PracticeService(repo)

    detail = as_dict(
        service.create_session(
            make_user(),
            course_id=101,
            knowledge_point_ids=[401, 402],
            question_count=3,
            difficulty="medium",
        )
    )

    assert detail["id"] == "501"
    assert detail["course_id"] == "101"
    assert detail["status"] == "in_progress"
    assert [question["question_type"] for question in detail["questions"]] == ["single_choice", "multiple_choice", "short_answer"]
    assert detail["questions"][0]["knowledge_point_id"] == "401"
    assert detail["questions"][0]["options"]
    assert detail["questions"][0]["correct_answer"] is None
    assert detail["answers"] == []
    assert repo.sessions[0].status == "in_progress"
    assert repo.sessions[0].score is None
    assert "系统提示词" not in str(detail)
    assert "API Key" not in str(detail)

    with pytest.raises(PracticeNotFoundError):
        service.create_session(make_user(), course_id=202, knowledge_point_ids=[401], question_count=3, difficulty="medium")

    with pytest.raises(PracticeNotFoundError):
        service.create_session(make_user(), course_id=101, knowledge_point_ids=[499], question_count=3, difficulty="medium")

    with pytest.raises(PracticeValidationError):
        service.create_session(make_user(), course_id=101, knowledge_point_ids=[401], question_count=0, difficulty="medium")


def test_adaptive_practice_uses_profile_and_restores_saved_draft() -> None:
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    repo.profiles[1] = StudentProfile(
        id=41,
        user_id=1,
        profile_json={"knowledge_foundation": "机器学习刚入门"},
        confidence_score=Decimal("72"),
    )
    service = PracticeService(repo)

    created = as_dict(service.create_session(make_user(), 101, [401], 1, "adaptive"))
    question_id = created["questions"][0]["id"]
    saved = as_dict(
        service.save_draft(
            make_user(),
            int(created["id"]),
            [{"question_id": question_id, "answer_text": "先写下启发函数的作用"}],
        )
    )
    latest = as_dict(service.get_latest_session(make_user(), 101))

    assert created["requested_difficulty"] == "adaptive"
    assert created["effective_difficulty"] == "easy"
    assert created["questions"][0]["difficulty"] == "easy"
    assert saved["draft_saved_at"] is not None
    assert latest["id"] == created["id"]
    assert latest["answers"][0]["answer_text"] == "先写下启发函数的作用"


def test_submit_practice_answers_scores_and_writes_confirmed_weakness_items() -> None:
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    service = PracticeService(repo)
    created = as_dict(service.create_session(make_user(), 101, [401, 402], 3, "medium"))
    session_id = int(created["id"])
    answers = [
        {"question_id": created["questions"][0]["id"], "answer_text": "错误选项"},
        {"question_id": created["questions"][1]["id"], "answer_text": "关键概念, 课程引用"},
        {"question_id": created["questions"][2]["id"], "answer_text": "我会用概念和误区解释复习线索。"},
    ]

    evaluated = as_dict(service.submit_answers(make_user(), session_id, answers))

    assert evaluated["status"] == "completed"
    assert evaluated["score"] == 67
    assert len(evaluated["answers"]) == 3
    assert evaluated["answers"][0]["is_correct"] is False
    assert evaluated["answers"][0]["feedback"]["score"] == 0
    assert evaluated["answers"][2]["feedback"]["score"] > 0
    assert repo.sessions[0].score == Decimal("67")
    assert repo.sessions[0].status == "completed"
    assert len(repo.weakness_items) == 1
    assert repo.weakness_items[0].source_type == "practice_assessment"
    assert repo.weakness_items[0].status == "confirmed"
    assert repo.weakness_items[0].knowledge_point_id == 401

    service.submit_answers(make_user(), session_id, answers)

    assert len(repo.weakness_items) == 1


def test_submit_answers_validates_empty_answers_and_user_scope() -> None:
    from backend.app.services.practice import PracticeNotFoundError, PracticeService, PracticeValidationError

    repo = make_repo()
    service = PracticeService(repo)
    created = as_dict(service.create_session(make_user(), 101, [401], 1, "easy"))
    session_id = int(created["id"])

    with pytest.raises(PracticeValidationError):
        service.submit_answers(make_user(), session_id, [{"question_id": created["questions"][0]["id"], "answer_text": " "}])

    with pytest.raises(PracticeValidationError):
        service.submit_answers(make_user(), session_id, [{"question_id": "unknown", "answer_text": "A"}])

    with pytest.raises(PracticeNotFoundError):
        service.submit_answers(make_user(2), session_id, [{"question_id": created["questions"][0]["id"], "answer_text": "A"}])


def test_generate_and_read_latest_report_uses_practice_and_learning_state_evidence() -> None:
    from backend.app.services.practice import PracticeService
    from backend.app.services.reports import ReportService

    repo = make_repo()
    practice_service = PracticeService(repo)
    report_service = ReportService(repo)
    created = as_dict(practice_service.create_session(make_user(), 101, [401, 402], 3, "medium"))
    practice_service.submit_answers(
        make_user(),
        int(created["id"]),
        [
            {"question_id": created["questions"][0]["id"], "answer_text": "错误选项"},
            {"question_id": created["questions"][1]["id"], "answer_text": "关键概念, 课程引用"},
            {"question_id": created["questions"][2]["id"], "answer_text": "概念 误区 复习线索"},
        ],
    )

    report = as_dict(report_service.generate_report(make_user(), course_id=101))
    latest = as_dict(report_service.get_latest_report(make_user(), course_id=101))

    assert report["course_id"] == "101"
    assert report["practice_session_id"] == created["id"]
    assert report["score"] == 67
    assert report["report"]["mastery_update"]["weak_count"] == 1
    assert report["report"]["weakness_list"][0]["knowledge_point_id"] == "401"
    assert report["report"]["next_step_suggestions"]
    assert latest["id"] == report["id"]
    assert "系统提示词" not in str(report)
    assert "模型输入" not in str(report)
    assert "API Key" not in str(report)


def test_latest_report_returns_empty_state_and_routes_require_login() -> None:
    from backend.app.api.v1.practice import get_practice_service
    from backend.app.api.v1.reports import get_report_service
    from backend.app.services.practice import PracticeService
    from backend.app.services.reports import ReportService

    repo = make_repo()
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="practice-test-secret-with-32-bytes-long", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(repository=TokenAuthRepository(user), settings=settings)
    app.dependency_overrides[get_practice_service] = lambda: PracticeService(repo)
    app.dependency_overrides[get_report_service] = lambda: ReportService(repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)
    headers = {"Authorization": f"Bearer {token}"}

    unauthorized = client.post("/api/v1/practice/sessions", json={"course_id": 101, "knowledge_point_ids": [401]})
    latest_empty = client.get("/api/v1/reports/latest?course_id=101", headers=headers)
    created = client.post(
        "/api/v1/practice/sessions",
        headers=headers,
        json={"course_id": 101, "knowledge_point_ids": [401], "question_count": 1, "difficulty": "easy"},
    )
    question_id = created.json()["data"]["questions"][0]["id"]
    submitted = client.post(
        f"/api/v1/practice/sessions/{created.json()['data']['id']}/answers",
        headers=headers,
        json={"answers": [{"question_id": question_id, "answer_text": "错误选项"}]},
    )
    generated_report = client.post(
        "/api/v1/reports/generate",
        headers=headers,
        json={"course_id": 101},
    )
    latest = client.get("/api/v1/reports/latest?course_id=101", headers=headers)
    missing = client.get("/api/v1/reports/latest?course_id=202", headers=headers)

    assert unauthorized.status_code == 401
    assert latest_empty.status_code == 200
    assert latest_empty.json()["data"]["status"] == "empty"
    assert created.status_code == 200
    assert submitted.status_code == 200
    assert submitted.json()["data"]["status"] == "completed"
    assert generated_report.status_code == 200
    assert generated_report.json()["data"]["practice_session_id"] == created.json()["data"]["id"]
    assert latest.status_code == 200
    assert latest.json()["data"]["status"] == "ready"
    assert missing.status_code == 404


def test_assessment_graph_keeps_rule_score_and_persists_model_diagnosis_with_trace() -> None:
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    created = PracticeService(repo).create_session(make_user(), 101, [401], 1, "medium")
    logs: list[Any] = []
    model = FakeModelService(
        responses=[
            '{"diagnoses":[{"question_id":"q1","misconception":"混淆了启发式搜索与无信息搜索",'
            '"missing_concepts":["启发函数"],"recommended_action":"复习课程引用并完成同类题",'
            '"confidence":0.88,"score":100}]}',
            '{"review_status":"passed","confidence":0.92,"risk_flags":[],'
            '"safety_summary":"诊断与规则分数一致。"}',
        ]
    )
    service = PracticeService(repo, model_service=model, trace_recorder=make_trace_recorder(logs))

    result = as_dict(
        service.submit_answers(
            make_user(),
            int(created.id),
            [{"question_id": "q1", "answer_text": "错误选项"}],
        )
    )

    assert result["score"] == 0
    diagnosis = result["answers"][0]["feedback"]["diagnosis"]
    assert diagnosis["misconception"] == "混淆了启发式搜索与无信息搜索"
    assert diagnosis["evidence_ref"]["type"] == "practice_answer"
    assert repo.weakness_items[0].source_ref_type == "practice_answer"
    assert repo.weakness_items[0].source_ref_id == int(diagnosis["evidence_ref"]["id"])
    assert repo.weakness_items[0].diagnosis_json["evidence_count"] == 1
    assert result["closure_update"]["path_update_status"] == "not_started"
    assert [log.agent_name for log in logs] == [
        "load",
        "deterministic_score",
        "diagnose_errors",
        "sync_weaknesses",
        "review",
        "persist",
        "path_replan",
    ]
    assert all("错误选项" not in str(log.metadata_json) for log in logs)


def test_assessment_path_failure_does_not_rollback_completed_practice() -> None:
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    created = PracticeService(repo).create_session(make_user(), 101, [401], 1, "easy")
    service = PracticeService(repo, path_service=FailingPathService())

    result = as_dict(
        service.submit_answers(
            make_user(),
            int(created.id),
            [{"question_id": "q1", "answer_text": "错误选项"}],
        )
    )

    assert result["status"] == "completed"
    assert result["score"] == 0
    assert result["closure_update"]["path_update_status"] == "failed"
    assert len(repo.weakness_items) == 1


def test_report_graph_aggregates_recent_trend_without_allowing_model_to_change_numbers() -> None:
    from backend.app.services.practice import PracticeService
    from backend.app.services.reports import ReportService

    repo = make_repo()
    practice = PracticeService(repo)
    first = practice.create_session(make_user(), 101, [401], 1, "easy")
    practice.submit_answers(make_user(), int(first.id), [{"question_id": "q1", "answer_text": "错误选项"}])
    second = practice.create_session(make_user(), 101, [401], 1, "easy")
    practice.submit_answers(make_user(), int(second.id), [{"question_id": "q1", "answer_text": "人工智能概述"}])
    logs: list[Any] = []
    model = FakeModelService(
        responses=[
            '{"summary":"近期练习表现明显提升。","next_step_suggestions":["继续巩固课程引用"]}',
            '{"review_status":"passed","confidence":0.9,"risk_flags":[],'
            '"safety_summary":"叙事与趋势证据一致。"}',
        ]
    )
    report_service = ReportService(repo, model_service=model, trace_recorder=make_trace_recorder(logs))

    report = as_dict(report_service.generate_report(make_user(), 101))

    assert report["score"] == 100
    assert report["report"]["summary"] == "近期练习表现明显提升。"
    assert report["report"]["trend"] == {
        "direction": "improved",
        "score_delta": 100,
        "sessions_compared": 2,
        "scores": [0, 100],
    }
    assert report["report"]["evidence_summary"]["practice_count"] == 2
    assert report["report"]["review_result"]["review_status"] == "passed"
    assert [log.agent_name for log in logs] == [
        "collect_practice",
        "collect_mastery",
        "aggregate_evidence",
        "generate_narrative",
        "review",
        "persist",
    ]
