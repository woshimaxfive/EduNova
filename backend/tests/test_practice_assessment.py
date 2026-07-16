from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
import json
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
    KnowledgeChunk,
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


class DefaultPracticeGenerationModel:
    def chat_completion(self, _user: User, messages: list[dict[str, str]]) -> str:
        prompt = "\n".join(message["content"] for message in messages)
        if "题目蓝图=" not in prompt:
            raise RuntimeError("该测试模型只承担题面生成")
        encoded = prompt.split("题目蓝图=", 1)[1].split("。近期同知识点题目摘要=", 1)[0]
        blueprints = json.loads(encoded)
        questions = []
        scenarios = [
            "课堂概念辨析：先定位定义中的必要条件，再判断结论。",
            "期末综合应用：结合两个概念之间的关系分析给定现象。",
            "常见错误诊断：找出推理链中被忽略的课程依据。",
            "迁移任务设计：把课程结论用于一个新的问题情境。",
            "反例检验：判断边界条件变化后原结论是否仍成立。",
        ]
        for index, item in enumerate(blueprints, start=1):
            options = list(item.get("options") or [])
            questions.append(
                {
                    "id": item["id"],
                    "prompt": f"{scenarios[(index - 1) % len(scenarios)]}{item['prompt']}请结合课程证据作答。",
                    "options": options,
                    "explanation": "依据课程短摘录判断，并说明关键概念关系。",
                    "cognitive_level": ["understand", "apply", "analyze", "create"][(index - 1) % 4],
                    "scenario_type": f"课程情境-{index}",
                    "target_misconception": f"避免混淆知识关系-{index}",
                    "reasoning_pattern": f"证据到结论-{index}",
                }
            )
        return json.dumps(
            {
                "questions": questions,
                "quality_review": {
                    "review_status": "passed",
                    "confidence": 0.9,
                    "risk_flags": [],
                    "safety_summary": "题目合同审核通过。",
                },
            },
            ensure_ascii=False,
        )


class DefaultReportModel:
    def chat_completion(self, _user: User, _messages: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "summary": "结合近期学习证据，当前应继续巩固薄弱概念并完成迁移练习。",
                "next_step_suggestions": ["复习课程引用中的关键关系", "完成一组针对性练习"],
                "quality_review": {
                    "review_status": "passed",
                    "confidence": 0.9,
                    "risk_flags": [],
                    "safety_summary": "叙事未改写确定性统计。",
                },
            },
            ensure_ascii=False,
        )


def make_practice_service(repo: FakePracticeRepository, **kwargs: Any):
    from backend.app.services.practice import PracticeService

    return PracticeService(repo, model_service=DefaultPracticeGenerationModel(), **kwargs)


def make_report_service(repo: FakePracticeRepository, **kwargs: Any):
    from backend.app.services.reports import ReportService

    return ReportService(repo, model_service=DefaultReportModel(), **kwargs)


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
    chunks: list[KnowledgeChunk] = field(default_factory=list)
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

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        return [chunk for chunk in self.chunks if chunk.course_id == course_id]

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
        account=f"user{user_id}",
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
        chunks=[
            KnowledgeChunk(id=301, course_id=101, material_id=201, knowledge_point_id=401, content="人工智能研究感知、推理与行动。机器学习从数据中学习规律。智能体依据环境状态选择动作。", section_title="人工智能概述", metadata_json={}),
            KnowledgeChunk(id=302, course_id=101, material_id=201, knowledge_point_id=402, content="A* 使用 f(n)=g(n)+h(n) 评价节点。g(n) 是已走代价。h(n) 是剩余代价的启发估计。", section_title="启发式搜索", metadata_json={}),
        ],
    )


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def make_trace_recorder(logs: list[Any]) -> AgentTraceRecorder:
    def add_log(log):
        logs.append(log)
        return log

    return AgentTraceRecorder(repository_add_log=add_log)


def test_create_practice_session_generates_deterministic_questions_and_validates_scope() -> None:
    from backend.app.services.practice import PracticeNotFoundError, PracticeValidationError

    repo = make_repo()
    service = make_practice_service(repo)

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
    assert detail["questions"][0]["citation_refs"]
    assert detail["questions"][0]["generation_mode"] == "model_generated"
    assert detail["questions"][0]["prompt_version"] == "assessment-v3.2"
    assert detail["questions"][0]["quality"]["evidence_bound"] is True
    assert detail["answers"] == []
    stored = [row.question_json for row in repo.list_answers_for_session(int(detail["id"]))]
    assert len({question["prompt"] for question in stored}) == 3
    assert all(question["source_excerpt"] for question in stored)
    assert all(question["citation_refs"] for question in stored)
    assert not any(
        option in {"无关概念", "跳过资料依据", "只背结论", "无关提示"}
        for question in stored
        for option in question.get("options", [])
    )
    assert not any(
        marker in option
        for question in stored
        for option in question.get("options", [])
        for marker in ("计算机部件", "软件界面", "硬件关系")
    )
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


def test_practice_generation_embeds_model_review_in_single_call() -> None:
    from backend.app.services.practice import PracticeService

    baseline = as_dict(make_practice_service(make_repo()).create_session(make_user(), 101, [401], 1, "easy"))
    source = baseline["questions"][0]
    model = FakeModelService(
        responses=[
            json.dumps(
                {
                    "questions": [
                        {
                            "id": source["id"],
                            "prompt": source["prompt"] + "请结合课程证据选择最准确的表述。",
                            "options": source["options"],
                            "explanation": source["explanation"] + "该结论与课程片段直接对应。",
                            "cognitive_level": "understand",
                            "scenario_type": "课程证据辨析",
                            "target_misconception": "忽略课程依据",
                            "reasoning_pattern": "证据到结论",
                        }
                    ],
                    "quality_review": {
                        "review_status": "passed",
                        "confidence": 0.91,
                        "risk_flags": [],
                        "safety_summary": "题目结构、答案、引用和隐私检查通过。",
                    },
                },
                ensure_ascii=False,
            )
        ]
    )

    detail = as_dict(PracticeService(make_repo(), model_service=model).create_session(make_user(), 101, [401], 1, "easy"))

    assert detail["questions"][0]["generation_mode"] == "model_generated"
    assert detail["questions"][0]["quality"]["review_mode"] == "embedded_model_and_rules"
    assert detail["questions"][0]["quality"]["review_status"] == "passed"
    assert len(model.calls) == 1


def test_practice_revision_receives_previous_candidate_and_preserves_valid_fields() -> None:
    from backend.app.services.practice import PracticeService

    baseline = as_dict(make_practice_service(make_repo()).create_session(make_user(), 101, [401], 1, "easy"))
    source = baseline["questions"][0]
    candidate_prompt = source["prompt"] + "请从课程证据判断这项表述。"
    candidate = {
        "id": source["id"],
        "prompt": candidate_prompt,
        "options": source["options"],
        "explanation": "根据课程短摘录中的定义关系可以判断。",
        "cognitive_level": "",
        "scenario_type": "课程证据辨析",
        "target_misconception": "忽略定义中的必要条件",
        "reasoning_pattern": "证据到结论",
    }
    repaired = {**candidate, "cognitive_level": "understand"}
    model = FakeModelService(
        responses=[
            json.dumps(
                {
                    "questions": [candidate],
                    "quality_review": {
                        "review_status": "passed",
                        "confidence": 0.9,
                        "risk_flags": [],
                        "safety_summary": "其余字段已通过。",
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "questions": [repaired],
                    "quality_review": {
                        "review_status": "passed",
                        "confidence": 0.92,
                        "risk_flags": [],
                        "safety_summary": "缺失字段已修订。",
                    },
                },
                ensure_ascii=False,
            ),
        ]
    )

    detail = as_dict(PracticeService(make_repo(), model_service=model).create_session(make_user(), 101, [401], 1, "easy"))

    assert detail["questions"][0]["prompt"] == candidate_prompt
    assert len(model.calls) == 2
    revision_prompt = "\n".join(message["content"] for message in model.calls[1])
    assert "上一版题目=" in revision_prompt
    assert candidate_prompt in revision_prompt
    assert "missing_pedagogical_fingerprint" in revision_prompt
    assert "补齐风险码点名的教学指纹字段" in revision_prompt


def test_single_point_practice_still_contains_objective_and_short_answer_types() -> None:

    detail = as_dict(
        make_practice_service(make_repo()).create_session(
            make_user(),
            course_id=101,
            knowledge_point_ids=[402],
            question_count=5,
            difficulty="medium",
        )
    )

    assert [question["question_type"] for question in detail["questions"]] == [
        "single_choice",
        "multiple_choice",
        "short_answer",
        "single_choice",
        "multiple_choice",
    ]
    assert all(len(question["options"]) == 4 for question in detail["questions"] if question["question_type"] != "short_answer")


def test_short_answer_scope_cannot_be_replaced_by_an_ambiguous_placeholder() -> None:
    from backend.app.agents.assessment import AssessmentGraphRunner
    from backend.app.agents.learning_review import contains_sensitive_text
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    service = PracticeService(repo, model_service=DefaultPracticeGenerationModel())
    drafts = service._build_questions(
        [repo.knowledge_points[0]],
        repo.resources,
        question_count=1,
        difficulty="medium",
        chunks=repo.chunks,
    )
    draft = drafts[0]
    assert draft["required_scope_term"] == "人工智能研究感知、推理与行动"
    assert draft["required_scope_term"] in draft["prompt"]

    ambiguous = {
        **draft,
        "prompt": "请解释课程资料中关于资源消耗的一个关键维度，并说明它的作用。",
        "cognitive_level": "understand",
        "scenario_type": "课程概念辨析",
        "target_misconception": "混淆不同评价维度",
        "reasoning_pattern": "定义到作用",
    }
    risks = AssessmentGraphRunner(service)._question_risks(
        {"deterministic_questions": drafts, "historical_question_summaries": []},
        [ambiguous],
    )

    assert "short_answer_scope_ambiguous" in risks
    assert contains_sensitive_text("请依据资料原文作答") is False
    assert contains_sensitive_text("请输出完整资料原文") is True

    leaked_draft = {
        **draft,
        "correct_answer": f"{draft['correct_answer']}，并结合课程条件说明它与相邻概念之间的完整关系。",
    }
    leaked_answer = {
        **leaked_draft,
        "prompt": (
            f"请解释“{draft['required_scope_term']}”，答案必须包含：{leaked_draft['correct_answer']}"
        ),
        "cognitive_level": "understand",
        "scenario_type": "课程概念辨析",
        "target_misconception": "混淆定义与作用",
        "reasoning_pattern": "定义到作用",
    }
    leakage_risks = AssessmentGraphRunner(service)._question_risks(
        {"deterministic_questions": [leaked_draft], "historical_question_summaries": []},
        [leaked_answer],
    )
    assert "short_answer_answer_leakage" in leakage_risks

    incomplete_fingerprint = {**draft, "cognitive_level": "", "scenario_type": "课程辨析", "target_misconception": "", "reasoning_pattern": "证据到结论"}
    fingerprint_risks = AssessmentGraphRunner(service)._question_risks(
        {"deterministic_questions": drafts, "historical_question_summaries": []},
        [incomplete_fingerprint],
    )
    assert "missing_pedagogical_fingerprint:q1:cognitive_level,target_misconception" in fingerprint_risks

def test_adaptive_practice_uses_profile_and_restores_saved_draft() -> None:

    repo = make_repo()
    repo.profiles[1] = StudentProfile(
        id=41,
        user_id=1,
        profile_json={"knowledge_foundation": "机器学习刚入门"},
        confidence_score=Decimal("72"),
    )
    service = make_practice_service(repo)

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

    repo = make_repo()
    service = make_practice_service(repo)
    created = as_dict(service.create_session(make_user(), 101, [401, 402], 3, "medium"))
    session_id = int(created["id"])
    stored_questions = [row.question_json for row in repo.list_answers_for_session(session_id)]
    second_answer = ", ".join(stored_questions[1]["correct_answer"])
    third_answer = " ".join(stored_questions[2]["keywords"][:3])
    answers = [
        {"question_id": created["questions"][0]["id"], "answer_text": "错误选项"},
        {"question_id": created["questions"][1]["id"], "answer_text": second_answer},
        {"question_id": created["questions"][2]["id"], "answer_text": third_answer},
    ]

    evaluated = as_dict(service.submit_answers(make_user(), session_id, answers))

    assert evaluated["status"] == "completed"
    assert evaluated["score"] == 50
    assert evaluated["grading_status"] == "partial"
    assert len(evaluated["answers"]) == 3
    assert evaluated["answers"][0]["is_correct"] is False
    assert evaluated["answers"][0]["feedback"]["score"] == 0
    assert evaluated["answers"][2]["feedback"]["score"] is None
    assert evaluated["answers"][2]["feedback"]["grading_status"] == "ungraded"
    assert evaluated["questions"][0]["correct_answer"] == stored_questions[0]["correct_answer"]
    assert evaluated["questions"][1]["correct_answer"] == stored_questions[1]["correct_answer"]
    assert repo.sessions[0].score == Decimal("50")
    assert repo.sessions[0].status == "completed"
    assert len(repo.weakness_items) == 1
    assert repo.weakness_items[0].source_type == "practice_assessment"
    assert repo.weakness_items[0].status == "confirmed"
    assert repo.weakness_items[0].knowledge_point_id == 401

    service.submit_answers(make_user(), session_id, answers)

    assert len(repo.weakness_items) == 1


def test_submit_answers_validates_empty_answers_and_user_scope() -> None:
    from backend.app.services.practice import PracticeNotFoundError, PracticeValidationError

    repo = make_repo()
    service = make_practice_service(repo)
    created = as_dict(service.create_session(make_user(), 101, [401], 1, "easy"))
    session_id = int(created["id"])

    with pytest.raises(PracticeValidationError):
        service.submit_answers(make_user(), session_id, [{"question_id": created["questions"][0]["id"], "answer_text": " "}])

    with pytest.raises(PracticeValidationError):
        service.submit_answers(make_user(), session_id, [{"question_id": "unknown", "answer_text": "A"}])

    with pytest.raises(PracticeNotFoundError):
        service.submit_answers(make_user(2), session_id, [{"question_id": created["questions"][0]["id"], "answer_text": "A"}])


def test_generate_and_read_latest_report_uses_practice_and_learning_state_evidence() -> None:

    repo = make_repo()
    practice_service = make_practice_service(repo)
    report_service = make_report_service(repo)
    created = as_dict(practice_service.create_session(make_user(), 101, [401, 402], 3, "medium"))
    stored_questions = [row.question_json for row in repo.list_answers_for_session(int(created["id"]))]
    practice_service.submit_answers(
        make_user(),
        int(created["id"]),
        [
            {"question_id": created["questions"][0]["id"], "answer_text": "错误选项"},
            {"question_id": created["questions"][1]["id"], "answer_text": ", ".join(stored_questions[1]["correct_answer"])},
            {"question_id": created["questions"][2]["id"], "answer_text": " ".join(stored_questions[2]["keywords"][:3])},
        ],
    )

    report = as_dict(report_service.generate_report(make_user(), course_id=101))
    latest = as_dict(report_service.get_latest_report(make_user(), course_id=101))

    assert report["course_id"] == "101"
    assert report["practice_session_id"] == created["id"]
    assert report["score"] == 50
    assert report["report"]["mastery_update"]["weak_count"] == 1
    assert report["report"]["weakness_list"][0]["knowledge_point_id"] == "401"
    assert report["report"]["next_step_suggestions"]
    assert report["report"]["deterministic_statistics"] == {
        "practice_session_count": 1,
        "answered_question_count": 3,
        "correct_answer_count": 1,
        "assessed_knowledge_point_count": 2,
        "completed_path_task_count": 0,
    }
    assert latest["id"] == report["id"]
    assert "系统提示词" not in str(report)
    assert "模型输入" not in str(report)
    assert "API Key" not in str(report)


def test_latest_report_returns_empty_state_and_routes_require_login() -> None:
    from backend.app.api.v1.practice import get_practice_service
    from backend.app.api.v1.reports import get_report_service

    repo = make_repo()
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="practice-test-secret-with-32-bytes-long", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(repository=TokenAuthRepository(user), settings=settings)
    app.dependency_overrides[get_practice_service] = lambda: make_practice_service(repo)
    app.dependency_overrides[get_report_service] = lambda: make_report_service(repo)
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
    recent = client.get("/api/v1/practice/sessions/recent?course_id=101&limit=5", headers=headers)
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
    assert recent.status_code == 200
    assert len(recent.json()["data"]) == 1
    assert recent.json()["data"][0]["id"] == created.json()["data"]["id"]
    assert recent.json()["data"][0]["course_id"] == "101"
    assert recent.json()["data"][0]["status"] == "completed"
    assert recent.json()["data"][0]["score"] is None
    assert recent.json()["data"][0]["grading_status"] == "ungraded"
    assert recent.json()["data"][0]["effective_difficulty"] == "easy"
    assert "questions" not in recent.json()["data"][0]
    assert "answers" not in recent.json()["data"][0]
    assert generated_report.status_code == 200
    assert generated_report.json()["data"]["practice_session_id"] == created.json()["data"]["id"]
    assert latest.status_code == 200
    assert latest.json()["data"]["status"] == "ready"
    assert missing.status_code == 404


def test_assessment_graph_semantically_grades_short_answer_and_persists_diagnosis_with_trace() -> None:
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    created = make_practice_service(repo).create_session(make_user(), 101, [401], 1, "medium")
    logs: list[Any] = []
    model = FakeModelService(
        responses=[
            '{"grades":[{"question_id":"q1","score":0,"is_correct":false,'
            '"matched_concepts":[],"missing_concepts":["启发函数"],'
            '"misconception":"混淆了启发式搜索与无信息搜索",'
            '"feedback":"复习课程引用并完成同类题","evidence_refs":[],"confidence":0.88}]}',
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
    assert result["grading_status"] == "complete"
    assert result["answers"][0]["feedback"]["grading_status"] == "model"
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
    assert len(model.calls) == 1


def test_ungraded_short_answer_can_be_regraded_once_and_repeated_regrade_is_idempotent() -> None:
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    created = make_practice_service(repo).create_session(make_user(), 101, [401], 1, "medium")
    ungraded = as_dict(
        PracticeService(repo).submit_answers(
            make_user(),
            int(created.id),
            [{"question_id": "q1", "answer_text": "启发函数用来估计从当前状态到目标的剩余代价。"}],
        )
    )
    assert ungraded["score"] is None
    assert ungraded["grading_status"] == "ungraded"

    model = FakeModelService(
        responses=[
            '{"grades":[{"question_id":"q1","score":88,"is_correct":true,'
            '"matched_concepts":["启发函数","剩余代价"],"missing_concepts":[],"misconception":"",'
            '"feedback":"核心含义与作用说明准确。","evidence_refs":[],"confidence":0.91}]}'
        ]
    )
    service = PracticeService(repo, model_service=model)

    regraded = as_dict(service.regrade_answers(make_user(), int(created.id)))
    repeated = as_dict(service.regrade_answers(make_user(), int(created.id)))

    assert regraded["score"] == 88
    assert regraded["grading_status"] == "complete"
    assert regraded["answers"][0]["feedback"]["matched_concepts"] == ["启发函数", "剩余代价"]
    assert repeated == regraded
    assert len(model.calls) == 1
    assert repo.weakness_items == []


def test_targeted_weakness_retest_uses_diagnosis_and_completes_only_after_passing() -> None:
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    weakness = WeaknessReviewItem(
        id=701,
        user_id=1,
        course_id=101,
        knowledge_point_id=401,
        title="人工智能概述",
        source_type="practice_assessment",
        source_ref_type="practice_answer",
        source_ref_id=600,
        diagnosis_json={
            "misconception": "混淆了智能体与普通程序",
            "missing_concepts": ["环境状态", "行动选择"],
            "recommended_action": "结合感知、推理和行动链路复习",
            "confidence": 0.9,
            "baseline_score": 40,
            "latest_score": 40,
        },
        status="confirmed",
        recommended_resource_ids=[901],
        created_at=NOW,
        updated_at=NOW,
    )
    repo.weakness_items.append(weakness)
    created = as_dict(
        make_practice_service(repo).create_session(
            make_user(),
            101,
            [401],
            1,
            "adaptive",
            weakness_item_id=701,
        )
    )

    assert created["targeted_weakness_id"] == "701"
    assert created["targeted_weakness_title"] == "人工智能概述"

    grader = FakeModelService(
        responses=[
            '{"grades":[{"question_id":"q1","score":90,"is_correct":true,'
            '"matched_concepts":["环境状态","行动选择"],"missing_concepts":[],"misconception":"",'
            '"feedback":"已能完整说明智能体链路。","evidence_refs":[],"confidence":0.92}]}'
        ]
    )
    result = as_dict(
        PracticeService(repo, model_service=grader).submit_answers(
            make_user(),
            int(created["id"]),
            [{"question_id": "q1", "answer_text": "智能体感知环境状态，推理后选择行动。"}],
        )
    )
    assert result["closure_update"]["targeted_weakness_passed"] is True
    assert result["closure_update"]["targeted_weakness_status"] == "completed"
    assert result["closure_update"]["targeted_weakness_improvement"] == 50
    assert weakness.status == "completed"
    assert weakness.diagnosis_json["attempt_count"] == 1
    assert weakness.diagnosis_json["last_practice_session_id"] == created["id"]


def test_targeted_weakness_retest_rejects_mismatched_point_and_ungraded_does_not_complete() -> None:
    from backend.app.services.practice import PracticeService, PracticeValidationError

    repo = make_repo()
    weakness = WeaknessReviewItem(
        id=701,
        user_id=1,
        course_id=101,
        knowledge_point_id=401,
        title="人工智能概述",
        source_type="practice_assessment",
        diagnosis_json={"baseline_score": 30},
        status="reviewing",
        recommended_resource_ids=[],
        created_at=NOW,
        updated_at=NOW,
    )
    repo.weakness_items.append(weakness)

    with pytest.raises(PracticeValidationError, match="知识点必须与待复习弱点一致"):
        make_practice_service(repo).create_session(make_user(), 101, [402], 1, "adaptive", weakness_item_id=701)

    created = make_practice_service(repo).create_session(make_user(), 101, [401], 1, "adaptive", weakness_item_id=701)
    result = as_dict(
        PracticeService(repo).submit_answers(
            make_user(),
            int(created.id),
            [{"question_id": "q1", "answer_text": "我尝试解释，但当前评分模型不可用。"}],
        )
    )

    assert result["grading_status"] == "ungraded"
    assert result["closure_update"]["targeted_weakness_passed"] is False
    assert weakness.status == "reviewing"


def test_assessment_path_failure_does_not_rollback_completed_practice() -> None:
    from backend.app.services.practice import PracticeService

    repo = make_repo()
    created = make_practice_service(repo).create_session(make_user(), 101, [401], 1, "easy")
    service = PracticeService(repo, path_service=FailingPathService())

    result = as_dict(
        service.submit_answers(
            make_user(),
            int(created.id),
            [{"question_id": "q1", "answer_text": "错误选项"}],
        )
    )

    assert result["status"] == "completed"
    assert result["score"] is None
    assert result["grading_status"] == "ungraded"
    assert result["closure_update"]["path_update_status"] == "not_started"
    assert len(repo.weakness_items) == 0


def test_report_graph_aggregates_recent_trend_without_allowing_model_to_change_numbers() -> None:
    from backend.app.services.reports import ReportService

    repo = make_repo()
    practice = make_practice_service(repo)
    first = practice.create_session(make_user(), 101, [401], 1, "easy")
    practice.submit_answers(make_user(), int(first.id), [{"question_id": "q1", "answer_text": "错误选项"}])
    second = practice.create_session(make_user(), 101, [401], 1, "easy")
    second_question = repo.list_answers_for_session(int(second.id))[0].question_json
    practice.submit_answers(make_user(), int(second.id), [{"question_id": "q1", "answer_text": " ".join(second_question["keywords"][:3])}])
    logs: list[Any] = []
    model = FakeModelService(
        responses=[
            '{"summary":"近期练习表现明显提升。","next_step_suggestions":["继续巩固课程引用"],'
            '"quality_review":{"review_status":"passed","confidence":0.9,"risk_flags":[],'
            '"safety_summary":"叙事与趋势证据一致。"}}',
        ]
    )
    report_service = ReportService(repo, model_service=model, trace_recorder=make_trace_recorder(logs))

    report = as_dict(report_service.generate_report(make_user(), 101))

    assert report["score"] is None
    assert report["report"]["summary"] == "近期练习表现明显提升。"
    assert report["report"]["trend"] == {
        "direction": "insufficient",
        "score_delta": 0,
        "sessions_compared": 0,
        "scores": [],
    }
    assert report["report"]["evidence_summary"]["practice_count"] == 2
    assert report["report"]["review_result"]["review_status"] == "passed"
    assert report["report"]["quality"]["review_mode"] == "embedded_model_and_rules"
    assert len(model.calls) == 1
    assert "不得出现阿拉伯数字" in model.calls[0][1]["content"]
    assert [log.agent_name for log in logs] == [
        "collect_practice",
        "collect_mastery",
        "aggregate_evidence",
        "generate_narrative",
        "review",
        "persist",
    ]


def test_report_graph_rejects_numeric_inconsistency_without_persisting_template_report() -> None:
    from backend.app.services.reports import ReportGenerationError, ReportService

    repo = make_repo()
    practice = make_practice_service(repo)
    first = practice.create_session(make_user(), 101, [401], 1, "easy")
    practice.submit_answers(make_user(), int(first.id), [{"question_id": "q1", "answer_text": "错误选项"}])
    second = practice.create_session(make_user(), 101, [401], 1, "easy")
    second_question = repo.list_answers_for_session(int(second.id))[0].question_json
    practice.submit_answers(make_user(), int(second.id), [{"question_id": "q1", "answer_text": second_question["correct_answer"]}])
    model = FakeModelService(
        responses=[
            '{"summary":"完成了 5 次练习并回答了 9 道题。","next_step_suggestions":["继续学习"],'
            '"quality_review":{"review_status":"passed","confidence":0.9,"risk_flags":[],"safety_summary":"审核通过。"}}',
        ]
    )

    with pytest.raises(ReportGenerationError):
        ReportService(repo, model_service=model).generate_report(make_user(), 101)

    assert len(model.calls) == 1
    assert repo.reports == []
