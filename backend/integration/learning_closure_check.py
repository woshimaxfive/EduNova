"""Controlled-provider fixture and DB assertions for the isolated Docker E2E only.

Not a production provider: fixed, synthetic course answers exercise the real graphs
and quality rules. Never registered in application settings or runtime factories.
"""

import json
import sys

from sqlalchemy import func, select

from backend.app.core.security import hash_password
from backend.app.core.config import get_settings
from backend.app.core.errors import NotFoundDomainError
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.db.session import SessionLocal
from backend.app.models import (
    AiJob,
    Course,
    CourseEnrollment,
    CourseMaterial,
    GeneratedResource,
    KnowledgeChunk,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    PracticeAnswer,
    PracticeSession,
    ResourceInteraction,
    StudentProfile,
    User,
)
from backend.app.services.courses import CourseService, SqlAlchemyCourseRepository
from backend.app.services.paths import PathService, SqlAlchemyPathRepository
from backend.app.services.resources import (
    ResourceGenerationService,
    SqlAlchemyResourceRepository,
)
from backend.app.services.task_progress import TaskProgressService
from backend.app.services.task_resource_binding import binding_status
from backend.app.services.ai_jobs import AiJobService, SqlAlchemyAiJobRepository
from backend.app.services.ai_capabilities import AI_CAPABILITIES

ACCOUNT = "e2e_evidence_loop"
PASSWORD = "SyntheticLoop2026"


class ControlledModel:
    def __init__(self, refs):
        self.refs = refs
        self.calls = 0

    def chat_completion_for_task(self, user, messages, profile):
        self.calls += 1
        prompt = "\n".join(message["content"] for message in messages)
        if "candidate_tasks" in messages[-1]["content"]:
            payload = json.loads(messages[-1]["content"])
            return json.dumps(
                {
                    "priority_tasks": [
                        {
                            "task_key": item["task_key"],
                            "rationale": "结合课程证据完成概念学习与测验",
                            "bundle_types": ["doc", "quiz"],
                            "resource_ids": list(item.get("resource_ids") or []),
                            "teaching_strategy": "证据讲解后进行迁移练习",
                            "learning_problem": "理解 A* 的代价与估计",
                            "example_direction": "比较课程中的候选节点",
                            "difficulty": "medium",
                            "used_profile_factor_codes": [],
                        }
                        for item in payload["candidate_tasks"]
                    ]
                },
                ensure_ascii=False,
            )
        if "资源教学策略规划器" in prompt:
            return "{}"
        if "ReviewAgent" in prompt:
            return json.dumps(
                {
                    "resources": {
                        kind: {"status": "passed", "confidence": 0.9, "risk_flags": []}
                        for kind in ("doc", "quiz")
                    }
                }
            )
        if "资源类型：quiz" in prompt:
            specs = [
                (
                    "q1",
                    "A* 中 f(n) 的含义是什么？",
                    ["g(n)+h(n)", "仅 h(n)", "仅 g(n)", "节点深度"],
                ),
                (
                    "q2",
                    "h(n) 不高估真实剩余代价支持什么性质？",
                    ["相应条件下的最优性", "随机扩展", "忽略路径代价", "固定深度"],
                ),
                (
                    "q3",
                    "开放列表优先选择什么节点？",
                    ["较小的 f(n)", "最大编号", "最晚加入", "随机节点"],
                ),
            ]
            artifact = {
                "kind": "quiz",
                "citation_refs": self.refs,
                "questions": [
                    {
                        "id": qid,
                        "type": "single_choice",
                        "prompt": question,
                        "options": [
                            {"key": chr(65 + i), "text": text}
                            for i, text in enumerate(options)
                        ],
                        "answer": "A",
                        "explanation": "课程原文说明 A* 结合已走代价与启发估计，并在启发函数满足条件时讨论最优性。",
                        "citation_refs": self.refs,
                    }
                    for qid, question, options in specs
                ],
            }
        else:
            artifact = {
                "kind": "document",
                "citation_refs": self.refs,
                "sections": [
                    {
                        "heading": "概念",
                        "body": "A* 是启发式搜索算法，使用 f(n)=g(n)+h(n) 选择候选状态。",
                    },
                    {
                        "heading": "代价关系",
                        "body": "g(n) 表示已走代价，h(n) 表示从当前状态到目标的估计代价。",
                    },
                    {
                        "heading": "最优条件",
                        "body": "当启发函数不高估真实剩余代价时，可在相应条件下保持最优性。",
                    },
                    {
                        "heading": "复习动作",
                        "body": "手算一个开放列表的更新过程，并比较不同 h(n) 对节点顺序的影响。",
                    },
                ],
            }
        return json.dumps(
            {
                "artifact": artifact,
                "summary": "围绕 A* 的证据型学习资源",
                "learning_objectives": ["解释 f(n)=g(n)+h(n)", "判断启发函数条件"],
            },
            ensure_ascii=False,
        )


def seed():
    with SessionLocal() as db:
        assert db.scalar(select(User.id).where(User.account == ACCOUNT)) is None, (
            "Fixture already exists; reset isolated E2E project"
        )
        user = User(
            account=ACCOUNT,
            hashed_password=hash_password(PASSWORD),
            display_name="受控闭环账号",
            role="student",
            starter_mode="blank",
        )
        db.add(user)
        db.flush()
        course = Course(owner_id=user.id, title="受控 A* 学习闭环", status="ready")
        db.add(course)
        db.flush()
        db.add(
            CourseEnrollment(
                user_id=user.id,
                course_id=course.id,
                learning_status="active",
                learning_context_json={
                    "learning_goal": "理解 A* 并完成练习",
                    "knowledge_foundation": "已学习图遍历",
                },
                learning_context_confidence_json={
                    "learning_goal": 100,
                    "knowledge_foundation": 100,
                },
            )
        )
        db.add(
            StudentProfile(
                user_id=user.id,
                profile_json={"learning_preference": "先阅读再练习"},
                dimension_confidence_json={"learning_preference": 100},
                confidence_score=100,
            )
        )
        point = KnowledgePoint(
            course_id=course.id,
            title="A* 搜索",
            summary="f(n)=g(n)+h(n) 与启发函数",
            order_index=1,
        )
        material = CourseMaterial(
            user_id=user.id,
            course_id=course.id,
            filename="synthetic-astar.txt",
            content_type="text/plain",
            storage_path="synthetic-only",
            parse_status="completed",
        )
        db.add_all([point, material])
        db.flush()
        chunk = KnowledgeChunk(
            course_id=course.id,
            material_id=material.id,
            knowledge_point_id=point.id,
            section_title="A* 搜索",
            content="A* 使用 f(n)=g(n)+h(n) 选择候选节点。g(n) 是已走路径代价，h(n) 是到目标的估计代价。开放列表优先扩展较小 f(n) 的节点。启发函数不高估真实剩余代价时，在相应条件下保持最优性。",
        )
        db.add(chunk)
        db.commit()
        model = ControlledModel([chunk.id])
        generated = ResourceGenerationService(
            SqlAlchemyResourceRepository(db), model_settings_service=model, trace_recorder=AgentTraceRecorder()
        ).generate_resources(
            user,
            course_id=course.id,
            knowledge_point_id=point.id,
            resource_types=["doc", "quiz"],
            learning_goal="理解 A* 搜索",
            difficulty="medium",
        )
        assert len(generated.resources) == 2, generated
        detail = PathService(
            SqlAlchemyPathRepository(db), model_service=model
        ).generate_path(user, course_id=course.id, draft=True)
        assert detail.path.approval_status == "draft" and len(detail.tasks) == 1
        task = db.scalar(
            select(LearningTask).where(LearningTask.path_id == int(detail.path.id))
        )
        for item in task.learning_bundle_json["items"]:
            assert (
                binding_status(
                    task, item, db.get(GeneratedResource, int(item["resource_id"]))
                )
                == "verified"
            )
        assert model.calls >= 4
        print(
            "Controlled provider generated reviewed resources and a draft through real LangGraph workflows"
        )


def verify():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.account == ACCOUNT))
        assert user is not None
        course = db.scalar(select(Course).where(Course.owner_id == user.id))
        assert course is not None
        path = db.scalar(
            select(LearningPath).where(
                LearningPath.user_id == user.id, LearningPath.status == "active"
            )
        )
        assert path.approval_status == "approved" and path.approved_at is not None
        task = db.scalar(select(LearningTask).where(LearningTask.path_id == path.id))
        progress = TaskProgressService(
            db, CourseService(SqlAlchemyCourseRepository(db))
        ).get(user, task.id)
        assert (
            progress.activity_completed
            and progress.assessment_passed
            and progress.mastered
        ), progress
        assert (
            progress.mastery_score == 100 and progress.next_step == "continue_learning"
        )
        try:
            TaskProgressService(db, CourseService(SqlAlchemyCourseRepository(db))).get(User(id=-1), task.id)
        except NotFoundDomainError:
            pass
        else:
            raise AssertionError("Task progress leaked across users")
        sessions = list(
            db.scalars(
                select(PracticeSession).where(PracticeSession.user_id == user.id)
            )
        )
        assert len(sessions) == 1 and sessions[0].score == 100
        answers = list(
            db.scalars(
                select(PracticeAnswer).where(
                    PracticeAnswer.session_id == sessions[0].id
                )
            )
        )
        assert len(answers) == 3
        for row in answers:
            assert row.feedback_json["grading_status"] == "deterministic"
            assert row.question_json["source_binding"]["path_id"] == path.id
            assert str(row.question_json["knowledge_point_id"]) == str(
                task.knowledge_point_id
            )
        completed_events = db.scalar(
            select(func.count())
            .select_from(ResourceInteraction)
            .where(
                ResourceInteraction.user_id == user.id,
                ResourceInteraction.event_type == "completed",
            )
        )
        assert completed_events == 1
        # A lost result receipt must not cause a second domain graph execution.
        resources = list(db.scalars(select(GeneratedResource).where(GeneratedResource.user_id == user.id)))
        for workflow, trace_id, payload in [
            ("path_planning", path.agent_trace_id, {"course_id": course.id, "draft": True}),
            ("resource_generation", resources[0].agent_trace_id, {"course_id": course.id,
             "knowledge_point_id": task.knowledge_point_id, "resource_types": ["doc", "quiz"]}),
        ]:
            request = AI_CAPABILITIES[workflow].validate_input(payload, course.id).model_dump(mode="json")
            original = AiJob(user_id=user.id, course_id=course.id, workflow=workflow, status="failed", stage="failed",
                label="合成 worker 中断", error_code="WORKER_LOST", progress_percent=90,
                agent_trace_id=trace_id, idempotency_key=f"synthetic-loss-{workflow}", request_json=request, result_json={}, progress_json={})
            db.add(original)
            db.commit()
            service = AiJobService(SqlAlchemyAiJobRepository(db))
            retry = service.retry_job(user, original.id)
            recovered = service.run_job(int(retry.job_id))
            assert recovered.status == "completed", recovered.error_message
            if workflow == "path_planning":
                assert recovered.result["path_id"] == str(path.id)
            else:
                assert set(recovered.result["resource_ids"]) == {str(resource.id) for resource in resources}
        assert db.scalar(select(func.count()).select_from(PracticeAnswer).where(PracticeAnswer.user_id == user.id)) == 3
        assert db.scalar(select(func.count()).select_from(GeneratedResource).where(GeneratedResource.user_id == user.id)) == 2
        assert db.scalar(select(func.count()).select_from(LearningPath).where(LearningPath.user_id == user.id)) == 1
        print("PostgreSQL worker-loss recovery and task ownership checks passed without new artifacts")
        print(
            "Browser closure DB verified: one assessment, three deterministic scores, exact provenance, mastery 100; replay added no evidence"
        )


if __name__ == "__main__":
    if get_settings().app_env != "test":
        raise SystemExit("Synthetic fixture requires APP_ENV=test")
    if sys.argv[1:] == ["seed"]:
        seed()
    elif sys.argv[1:] == ["verify"]:
        verify()
    else:
        raise SystemExit("Use seed or verify inside the isolated E2E environment")
