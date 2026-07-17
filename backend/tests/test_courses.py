from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.agents.course_builder import CourseBuilderGraphRunner
from backend.app.api.v1.deps import get_auth_service
from backend.app.api.v1.courses import get_course_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    Course,
    CourseEnrollment,
    CourseMaterial,
    CourseMaterialLink,
    GeneratedResource,
    KnowledgeChunk,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    Material,
    MaterialChunk,
    ProfileEvent,
    PracticeAnswer,
    StudentProfile,
    User,
    WeaknessReviewItem,
)
from backend.app.services.auth import AuthService
from backend.app.services.courses import CourseNotFoundError, CourseService
from backend.app.services.material_retrieval import MaterialChunkingService


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeCourseRepository:
    materials: list[Material] = field(default_factory=list)
    courses: list[Course] = field(default_factory=list)
    enrollments: list[CourseEnrollment] = field(default_factory=list)
    course_materials: list[CourseMaterial] = field(default_factory=list)
    material_links: list[CourseMaterialLink] = field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)
    knowledge_chunks: list[KnowledgeChunk] = field(default_factory=list)
    profiles: dict[int, StudentProfile] = field(default_factory=dict)
    profile_events: list[ProfileEvent] = field(default_factory=list)
    weakness_items: list[WeaknessReviewItem] = field(default_factory=list)
    generated_resources: list[GeneratedResource] = field(default_factory=list)
    learning_paths: list[LearningPath] = field(default_factory=list)
    learning_tasks: list[LearningTask] = field(default_factory=list)
    practice_answers: list[PracticeAnswer] = field(default_factory=list)
    next_course_id: int = 101
    next_enrollment_id: int = 201
    next_course_material_id: int = 301
    next_link_id: int = 401
    next_knowledge_point_id: int = 501
    next_chunk_id: int = 601
    next_weakness_item_id: int = 701

    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        material_id_set = set(material_ids)
        return [material for material in self.materials if material.user_id == user_id and material.id in material_id_set]

    def list_material_chunks(self, material_ids: list[int]) -> list[MaterialChunk]:
        chunks: list[MaterialChunk] = []
        for material in self.materials:
            if material.id not in material_ids or not material.extracted_text:
                continue
            paths: dict[str, list[str]] = {}
            stack: list[str] = []
            if material.filename.endswith((".md", ".markdown")):
                for line in material.extracted_text.splitlines():
                    match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
                    if not match:
                        continue
                    level = len(match.group(1))
                    title = match.group(2).strip()
                    stack = stack[: level - 1]
                    stack.append(title)
                    paths[title] = list(stack)
            built = MaterialChunkingService().build_chunks(material)
            for chunk in built:
                chunk.section_path_json = paths.get(chunk.section_title or "", [chunk.section_title or "正文"])
                chunk.quality_json = {"included": True}
            chunks.extend(built)
        return chunks

    def add_course_graph(
        self,
        course: Course,
        enrollment: CourseEnrollment,
        course_materials: list[CourseMaterial],
        material_links: list[CourseMaterialLink],
        knowledge_points: list[KnowledgePoint],
        knowledge_chunks: list[KnowledgeChunk],
    ) -> Course:
        course.id = self.next_course_id
        self.next_course_id += 1
        self.courses.append(course)

        enrollment.id = self.next_enrollment_id
        enrollment.course_id = course.id
        self.next_enrollment_id += 1
        self.enrollments.append(enrollment)

        for course_material in course_materials:
            course_material.id = self.next_course_material_id
            course_material.course_id = course.id
            self.next_course_material_id += 1
            self.course_materials.append(course_material)

        for link in material_links:
            link.id = self.next_link_id
            link.course_id = course.id
            self.next_link_id += 1
            self.material_links.append(link)

        for knowledge_point in knowledge_points:
            knowledge_point.id = self.next_knowledge_point_id
            knowledge_point.course_id = course.id
            self.next_knowledge_point_id += 1
            self.knowledge_points.append(knowledge_point)

        point_by_key = {
            str(getattr(point, "builder_key", f"kp-{index + 1}")): point
            for index, point in enumerate(knowledge_points)
        }
        for knowledge_point in knowledge_points:
            knowledge_point.prerequisites_json = [
                point_by_key[key].id
                for key in list(knowledge_point.prerequisites_json or [])
                if key in point_by_key and point_by_key[key].id != knowledge_point.id
            ]

        for index, chunk in enumerate(knowledge_chunks):
            chunk.id = self.next_chunk_id
            chunk.course_id = course.id
            point_key = str((chunk.metadata_json or {}).get("knowledge_point_key") or "")
            if point_key in point_by_key:
                chunk.knowledge_point_id = point_by_key[point_key].id
            if chunk.material_id is None:
                chunk.material_id = self.course_materials[min(index, len(self.course_materials) - 1)].id
            self.next_chunk_id += 1
            self.knowledge_chunks.append(chunk)

        return course

    def list_courses_for_user(self, user_id: int, source_type: str | None = None) -> list[Course]:
        result = [course for course in self.courses if course.owner_id == user_id]
        if source_type:
            result = [course for course in result if course.source_type == source_type]
        return result

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.owner_id == user_id and course.id == course_id), None)

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]:
        return [material for material in self.course_materials if material.course_id == course_id]

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return [point for point in self.knowledge_points if point.course_id == course_id]

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        return [chunk for chunk in self.knowledge_chunks if chunk.course_id == course_id]

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.profiles.get(user_id)

    def list_weakness_candidate_events(self, user_id: int, course_id: int) -> list[ProfileEvent]:
        result: list[ProfileEvent] = []
        for event in self.profile_events:
            evidence = event.evidence_json or {}
            if (
                event.user_id == user_id
                and event.dimension == "weak_points"
                and evidence.get("source_type") == "course_question"
                and evidence.get("course_id") == course_id
            ):
                result.append(event)
        return sorted(result, key=lambda event: (event.created_at, event.id), reverse=True)

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        result = [item for item in self.weakness_items if item.user_id == user_id and item.course_id == course_id]
        return sorted(result, key=lambda item: (item.created_at, item.id), reverse=True)

    def list_weakness_review_items_for_update(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return self.list_weakness_review_items(user_id, course_id)

    def get_weakness_review_item(self, user_id: int, course_id: int, item_id: int) -> WeaknessReviewItem | None:
        return next(
            (
                item
                for item in self.weakness_items
                if item.user_id == user_id and item.course_id == course_id and item.id == item_id
            ),
            None,
        )

    def add_weakness_review_item(self, item: WeaknessReviewItem) -> None:
        item.id = self.next_weakness_item_id
        self.next_weakness_item_id += 1
        item.created_at = item.created_at or datetime(2026, 7, 5, 8, 0, tzinfo=UTC)
        item.updated_at = item.updated_at or item.created_at
        self.weakness_items.append(item)

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return [
            resource
            for resource in self.generated_resources
            if resource.user_id == user_id and resource.course_id == course_id
        ]

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None:
        active_paths = [
            path
            for path in self.learning_paths
            if path.user_id == user_id and path.course_id == course_id and path.status == "active"
        ]
        return active_paths[0] if active_paths else None

    def list_learning_tasks(self, user_id: int, course_id: int) -> list[LearningTask]:
        return [
            task
            for task in self.learning_tasks
            if task.user_id == user_id and task.course_id == course_id
        ]

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]:
        return [task for task in self.learning_tasks if task.path_id == path_id]

    def list_practice_answers(self, user_id: int, course_id: int) -> list[PracticeAnswer]:
        return [
            answer
            for answer in self.practice_answers
            if answer.user_id == user_id and (answer.question_json or {}).get("course_id") == course_id
        ]

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def refresh(self, _instance: object) -> None:
        return None


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        account=f"user{user_id}",
        hashed_password="not-used",
        display_name=f"用户 {user_id}",
        role="student",
        starter_mode="blank",
    )


def make_material(
    material_id: int,
    user_id: int,
    filename: str,
    extracted_text: str | None,
    parse_status: str = "completed",
) -> Material:
    return Material(
        id=material_id,
        user_id=user_id,
        filename=filename,
        content_type="text/markdown" if filename.endswith(".md") else "text/plain",
        storage_path=f"user_{user_id}/{filename}",
        parse_status=parse_status,
        ingestion_status="confirmed" if parse_status == "completed" and extracted_text else "failed",
        extracted_text=extracted_text,
        outline_json={"confirmed": bool(parse_status == "completed" and extracted_text)},
        quality_json={"passed": bool(parse_status == "completed" and extracted_text)},
        metadata_json={"size_label": "1 KB", "extension": filename.rsplit(".", 1)[-1].upper()},
    )


def make_service(repo: FakeCourseRepository) -> CourseService:
    return CourseService(repository=repo)


def make_trace_recorder(logs: list[Any]) -> AgentTraceRecorder:
    def add_log(log):
        logs.append(log)
        return log

    return AgentTraceRecorder(repository_add_log=add_log)


@dataclass
class FakeEmbeddingBatch:
    vectors: list[list[float]]
    source: str = "local"
    model: str = "local-hash-1536"
    dimension: int = 1536
    status: str = "local_fallback"


@dataclass
class FakeEmbeddingService:
    calls: list[list[str]] = field(default_factory=list)

    def embed_texts(self, _user: User, texts: list[str]) -> FakeEmbeddingBatch:
        self.calls.append(texts)
        vectors = []
        for index, _text in enumerate(texts):
            vector = [0.0] * 1536
            vector[index % 1536] = 1.0
            vectors.append(vector)
        return FakeEmbeddingBatch(vectors=vectors)


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def make_course(course_id: int = 101, owner_id: int = 1, title: str = "AI 搜索复习") -> Course:
    return Course(
        id=course_id,
        owner_id=owner_id,
        title=title,
        description="由资料生成",
        subject="人工智能",
        source_type="uploaded",
        visibility="private",
        status="ready",
    )


def make_candidate_event(
    event_id: int,
    user_id: int,
    course_id: int,
    *,
    knowledge_point_id: int | None = 401,
    section_title: str | None = "启发式搜索",
    source_title: str | None = "人工智能导论讲义.md",
    trace_id: str = "trace_candidate",
    created_at: datetime | None = None,
) -> ProfileEvent:
    event = ProfileEvent(
        id=event_id,
        user_id=user_id,
        profile_id=None,
        dimension="weak_points",
        change_summary="课程问答提示可能存在薄弱点",
        evidence_json={
            "source_type": "course_question",
            "course_id": course_id,
            "session_id": 3,
            "user_message_id": 11,
            "assistant_message_id": 12,
            "trace_id": trace_id,
            "citations": [
                {
                    "chunk_id": 501,
                    "knowledge_point_id": knowledge_point_id,
                    "source_title": source_title,
                    "section_title": section_title,
                }
            ],
        },
    )
    event.created_at = created_at or datetime(2026, 7, 5, 8, 0, tzinfo=UTC)
    return event


def make_weakness_item(
    item_id: int,
    user_id: int,
    course_id: int,
    *,
    title: str = "启发式搜索",
    knowledge_point_id: int | None = 401,
    status: str = "pending",
) -> WeaknessReviewItem:
    item = WeaknessReviewItem(
        id=item_id,
        user_id=user_id,
        course_id=course_id,
        knowledge_point_id=knowledge_point_id,
        title=title,
        source_type="course_question",
        status=status,
        recommended_resource_ids=[],
        next_review_at=None,
    )
    item.created_at = datetime(2026, 7, 5, 8, 10, tzinfo=UTC)
    item.updated_at = datetime(2026, 7, 5, 8, 12, tzinfo=UTC)
    return item


def make_practice_answer(
    answer_id: int,
    point_id: int,
    score: int,
    is_correct: bool,
    *,
    session_id: int = 900,
    created_at: datetime | None = None,
) -> PracticeAnswer:
    return PracticeAnswer(
        id=answer_id,
        session_id=session_id,
        user_id=1,
        question_json={
            "id": f"q-{answer_id}",
            "course_id": 101,
            "knowledge_point_id": str(point_id),
            "knowledge_point_title": "练习知识点",
            "question_type": "single_choice",
        },
        answer_text="学生作答",
        feedback_json={"score": score, "message": "规则批改"},
        is_correct=is_correct,
        created_at=created_at or datetime(2026, 7, 5, 9, 0, tzinfo=UTC),
    )


def make_resource(
    resource_id: int,
    user_id: int,
    course_id: int,
    *,
    title: str = "启发式搜索讲解",
    knowledge_point_id: int | None = 401,
) -> GeneratedResource:
    return GeneratedResource(
        id=resource_id,
        user_id=user_id,
        course_id=course_id,
        knowledge_point_id=knowledge_point_id,
        resource_type="doc",
        title=title,
        content_json={"markdown": "安全摘要", "metadata": {"agent_trace_id": "trace_resource"}},
        citation_json=[],
        status="completed",
        review_status="passed",
        confidence_score=Decimal("0.86"),
        created_at=datetime(2026, 7, 5, 8, 20, tzinfo=UTC),
        updated_at=datetime(2026, 7, 5, 8, 21, tzinfo=UTC),
    )


def make_learning_path(path_id: int, user_id: int = 1, course_id: int = 101) -> LearningPath:
    path = LearningPath(
        id=path_id,
        user_id=user_id,
        course_id=course_id,
        title="AI 搜索复习路径",
        goal="期末前掌握搜索算法",
        status="active",
        plan_json={"duration_days": 7, "reason": "基于已确认弱点生成"},
    )
    path.created_at = datetime(2026, 7, 5, 8, 30, tzinfo=UTC)
    path.updated_at = datetime(2026, 7, 5, 8, 30, tzinfo=UTC)
    return path


def make_learning_task(
    task_id: int,
    path_id: int,
    *,
    user_id: int = 1,
    course_id: int = 101,
    knowledge_point_id: int | None = 401,
    title: str = "复习启发式搜索",
    task_type: str = "review",
    status: str = "doing",
) -> LearningTask:
    task = LearningTask(
        id=task_id,
        path_id=path_id,
        user_id=user_id,
        course_id=course_id,
        knowledge_point_id=knowledge_point_id,
        title=title,
        task_type=task_type,
        reason="来自已确认薄弱点",
        recommended_resource_ids=[801],
        status=status,
        due_at=datetime(2026, 7, 6, 8, 0, tzinfo=UTC),
        next_review_at=None,
    )
    task.created_at = datetime(2026, 7, 5, 8, 31, tzinfo=UTC)
    task.updated_at = datetime(2026, 7, 5, 8, 31, tzinfo=UTC)
    return task


def test_course_routes_require_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/courses")
    mastery_map_response = client.get("/api/v1/courses/101/mastery-map")
    learning_state_response = client.get("/api/v1/courses/101/learning-state")
    weakness_action_response = client.post("/api/v1/courses/101/weakness-review-items/701/confirm")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert mastery_map_response.status_code == 401
    assert mastery_map_response.json()["error"]["code"] == "UNAUTHORIZED"
    assert learning_state_response.status_code == 401
    assert learning_state_response.json()["error"]["code"] == "UNAUTHORIZED"
    assert weakness_action_response.status_code == 401
    assert weakness_action_response.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_course_from_txt_material_builds_course_graph() -> None:
    repo = FakeCourseRepository(
        materials=[
            make_material(
                1,
                1,
                "exam-notes.txt",
                "神经网络基础\n\n反向传播使用链式法则计算梯度。\n\n过拟合需要用正则化缓解。",
            )
        ]
    )
    user = make_user()

    result = make_service(repo).create_course_from_materials(
        user,
        material_ids=[1],
        course_title="神经网络期末复习",
    )

    data = as_dict(result)

    assert data["course"]["title"] == "神经网络期末复习"
    assert data["course"]["source_type"] == "uploaded"
    assert data["course"]["status"] == "ready"
    assert data["course"]["material_count"] == 1
    assert data["course"]["knowledge_point_count"] >= 2
    assert data["course"]["chunk_count"] >= 2
    assert repo.courses[0].owner_id == user.id
    assert repo.enrollments[0].progress_percent == Decimal("0")
    assert repo.course_materials[0].filename == "exam-notes.txt"
    assert repo.material_links[0].material_id == 1
    assert repo.material_links[0].usage_type == "course_source"
    assert all(chunk.embedding is None for chunk in repo.knowledge_chunks)


def test_course_builder_graph_records_nodes_structure_and_prerequisites() -> None:
    repo = FakeCourseRepository(
        materials=[
            make_material(
                1,
                1,
                "ai.md",
                "# 搜索问题\n状态空间是搜索的基础。\n## 启发式搜索\nA* 使用启发函数。",
            )
        ]
    )
    logs: list[Any] = []
    service = CourseService(repository=repo, trace_recorder=make_trace_recorder(logs))

    result = as_dict(service.create_course_from_materials(make_user(), [1], "AI 搜索复习"))

    assert [log.agent_name for log in logs] == [
        "validate_confirmed_materials",
        "coherence_gate",
        "load_outlines",
        "chapter_plan",
        "concept_workers",
        "aggregate",
        "prerequisite_graph",
        "evidence_bind",
        "review",
        "persist",
    ]
    assert result["course"]["agent_trace_id"] == logs[0].trace_id
    assert repo.courses[0].structure_json["schema_version"] == 3
    assert repo.courses[0].structure_json["source_coverage"] == {
        "source_chunk_count": 2,
        "mapped_source_count": 2,
    }
    assert result["knowledge_points"][1]["prerequisite_ids"] == [result["knowledge_points"][0]["id"]]
    assert all(chunk.knowledge_point_id is not None for chunk in repo.knowledge_chunks)


def test_create_course_from_parsed_pdf_material_builds_course_graph() -> None:
    repo = FakeCourseRepository(
        materials=[
            make_material(
                1,
                1,
                "search-notes.pdf",
                "Heuristic search review\n\nA star search uses a heuristic function.\n\nLocal search explores nearby states.",
            )
        ]
    )

    result = make_service(repo).create_course_from_materials(make_user(), [1], "AI 搜索 PDF 课程")

    data = as_dict(result)

    assert data["course"]["title"] == "AI 搜索 PDF 课程"
    assert data["course"]["material_count"] == 1
    assert data["course"]["knowledge_point_count"] >= 2
    assert repo.course_materials[0].filename == "search-notes.pdf"
    assert repo.knowledge_chunks[0].metadata_json["source_filename"] == "search-notes.pdf"


def test_markdown_headings_generate_chapters_and_knowledge_points() -> None:
    repo = FakeCourseRepository(
        materials=[
            make_material(
                1,
                1,
                "ai.md",
                "# 搜索问题\n状态空间是搜索的基础。\n## 启发式搜索\nA* 使用启发函数。\n## 对抗搜索\nMinimax 用于博弈。",
            )
        ]
    )

    result = make_service(repo).create_course_from_materials(make_user(), [1], "AI 搜索复习")
    points = as_dict(result)["knowledge_points"]

    assert [point["title"] for point in points] == ["搜索问题", "启发式搜索", "对抗搜索"]
    assert points[1]["chapter"] == "搜索问题"
    assert "A*" in repo.knowledge_chunks[1].content


def test_long_markdown_section_keeps_all_chunks_across_adaptive_knowledge_points() -> None:
    repo = FakeCourseRepository(
        materials=[make_material(1, 1, "long.md", "# 长章节\n" + "神经网络训练需要理解梯度与优化。" * 160)]
    )

    result = as_dict(make_service(repo).create_course_from_materials(make_user(), [1], "长章节课程"))

    assert len(result["knowledge_points"]) > 1
    assert result["knowledge_points"][0]["title"] == "长章节"
    assert all("核心概念" not in point["title"] for point in result["knowledge_points"])
    assert len(repo.knowledge_chunks) > 1
    assert len({chunk.knowledge_point_id for chunk in repo.knowledge_chunks}) == len(result["knowledge_points"])


def test_course_builder_rejects_sentence_like_ocr_titles_and_repairs_common_noise() -> None:
    runner = CourseBuilderGraphRunner.__new__(CourseBuilderGraphRunner)
    chunks = [
        MaterialChunk(
            material_id=1,
            chunk_index=index,
            content=content,
            page_number=index,
            end_page_number=index,
            section_title=title,
            section_path_json=["第8章 排序", title],
            quality_json={"included": True},
        )
        for index, (title, content) in enumerate(
            [
                ("8.1 插人排序", "直接插入排序逐步扩大有序区间。"),
                ("8.15 (f)和图 8.15 (g) 所示。至此排序完毕。", "排序过程说明。"),
                ("8.6 归井排序", "归并排序合并相邻有序序列。"),
            ],
            start=1,
        )
    ]

    points = runner._deterministic_chapter_points(
        {"title": "第8章 排序", "target_count": 3},
        chunks,
    )

    titles = [point["title"] for point in points]
    assert "8.1 插入排序" in titles
    assert "8.6 归并排序" in titles
    assert all("所示" not in title and "至此" not in title for title in titles)
    assert all(runner._is_knowledge_title(title) for title in titles)


def test_course_builder_disambiguates_chapter_local_duplicate_titles() -> None:
    runner = CourseBuilderGraphRunner.__new__(CourseBuilderGraphRunner)
    points = [
        {"title": "概述", "chapter": "第4章"},
        {"title": "概述", "chapter": "第5章"},
        {"title": "概述", "chapter": "第5章"},
    ]

    runner._ensure_unique_point_titles(points)

    titles = [point["title"] for point in points]
    assert titles == ["概述", "第5章：概述", "第5章：概述（2）"]
    assert len({runner._normalize(title) for title in titles}) == len(titles)
    assert all(runner._is_knowledge_title(title) for title in titles)


def test_create_course_best_effort_generates_chunk_embeddings() -> None:
    repo = FakeCourseRepository(
        materials=[
            make_material(
                1,
                1,
                "ai.md",
                "# 搜索问题\n状态空间是搜索的基础。\n## 启发式搜索\nA* 使用启发函数。",
            )
        ]
    )
    embedding_service = FakeEmbeddingService()
    service = CourseService(repository=repo, embedding_service=embedding_service)

    service.create_course_from_materials(make_user(), [1], "AI 搜索复习")

    assert embedding_service.calls == [[chunk.content for chunk in repo.knowledge_chunks]]
    assert all(chunk.embedding is not None for chunk in repo.knowledge_chunks)
    assert repo.knowledge_chunks[0].metadata_json["embedding_source"] == "local"
    assert repo.knowledge_chunks[0].metadata_json["embedding_model"] == "local-hash-1536"
    assert repo.knowledge_chunks[0].metadata_json["embedding_dimension"] == 1536


def test_unheaded_txt_generates_numbered_sections() -> None:
    repo = FakeCourseRepository(
        materials=[make_material(1, 1, "plain.txt", "第一段介绍监督学习。\n\n第二段介绍泛化能力。")]
    )

    result = make_service(repo).create_course_from_materials(make_user(), [1], "")
    points = as_dict(result)["knowledge_points"]

    assert as_dict(result)["course"]["title"] == "plain"
    assert [point["title"] for point in points] == ["第 1 部分", "第 2 部分"]


def test_rejects_other_user_or_unparsed_materials() -> None:
    from backend.app.services.courses import CourseGenerationError

    repo = FakeCourseRepository(
        materials=[
            make_material(1, 2, "other.md", "# Other"),
            make_material(2, 1, "slide.pdf", None, parse_status="uploaded"),
            make_material(3, 1, "empty.md", None, parse_status="completed"),
        ]
    )
    service = make_service(repo)
    user = make_user()

    with pytest.raises(CourseGenerationError, match="资料不存在或无权访问"):
        service.create_course_from_materials(user, [1], "非法资料")

    with pytest.raises(CourseGenerationError, match="精细解析并确认目录"):
        service.create_course_from_materials(user, [2], "PDF 课程")

    with pytest.raises(CourseGenerationError, match="精细解析并确认目录"):
        service.create_course_from_materials(user, [3], "空资料")

    with pytest.raises(CourseGenerationError, match="至少选择一份资料"):
        service.create_course_from_materials(user, [], "空选择")


def test_course_read_apis_are_scoped_to_current_user() -> None:
    repo = FakeCourseRepository(courses=[Course(id=101, owner_id=1, title="我的课", source_type="uploaded")])
    repo.knowledge_points.append(KnowledgePoint(id=501, course_id=101, title="知识点", summary="摘要", chapter="第一章", order_index=0))
    repo.knowledge_chunks.append(KnowledgeChunk(id=601, course_id=101, material_id=301, content="知识切片", metadata_json={}))
    service = make_service(repo)

    assert [item.title for item in service.list_courses(make_user(1)).data] == ["我的课"]
    assert service.list_courses(make_user(2)).data == []
    assert service.get_course(make_user(1), 101).title == "我的课"
    assert service.get_overview(make_user(1), 101).chunk_count == 1
    assert service.get_knowledge_points(make_user(1), 101)[0].title == "知识点"

    with pytest.raises(CourseNotFoundError):
        service.get_course(make_user(2), 101)


def test_knowledge_point_content_returns_safe_ordered_course_evidence() -> None:
    repo = FakeCourseRepository(
        courses=[make_course()],
        course_materials=[
            CourseMaterial(
                id=301,
                user_id=1,
                course_id=101,
                filename="机器学习讲义.md",
                content_type="text/markdown",
                storage_path="private/never-return-this-path.md",
                parse_status="completed",
                metadata_json={"secret": "never-return-this"},
            )
        ],
        knowledge_points=[
            KnowledgePoint(id=401, course_id=101, title="机器学习", summary="学习目标", chapter="第四章", order_index=0),
            KnowledgePoint(id=402, course_id=101, title="监督学习", summary="后续目标", chapter="第四章", order_index=1),
        ],
        knowledge_chunks=[
            KnowledgeChunk(
                id=601,
                course_id=101,
                material_id=301,
                knowledge_point_id=401,
                content="  机器学习从数据中学习规律。  ",
                page_number=8,
                section_title="从规则到数据",
                metadata_json={"api_key": "never-return-this"},
            )
        ],
        generated_resources=[make_resource(801, 1, 101, knowledge_point_id=401)],
    )

    result = as_dict(make_service(repo).get_knowledge_point_content(make_user(), 101, 401))

    assert result["knowledge_point"]["title"] == "机器学习"
    assert result["sections"] == [
        {
            "chunk_id": "601",
            "title": "从规则到数据",
            "content": "机器学习从数据中学习规律。",
            "source_title": "机器学习讲义.md",
            "page_number": 8,
        }
    ]
    assert result["related_resources"][0]["id"] == "801"
    assert result["previous_knowledge_point_id"] is None
    assert result["next_knowledge_point_id"] == "402"
    assert "storage_path" not in str(result)
    assert "never-return-this" not in str(result)

    with pytest.raises(CourseNotFoundError):
        make_service(repo).get_knowledge_point_content(make_user(2), 101, 401)


def test_learning_state_returns_empty_course_state_without_candidates() -> None:
    repo = FakeCourseRepository(courses=[make_course()])
    user = make_user()

    state = as_dict(make_service(repo).get_learning_state(user, 101))

    assert state["course_id"] == "101"
    assert state["profile_overlay"] == {
        "learning_goal": "",
        "knowledge_foundation": "",
        "weak_points": [],
    }
    assert state["weakness_summary"]["candidate_event_count"] == 0
    assert state["weakness_summary"]["pending_count"] == 0
    assert state["weakness_review_queue"] == []
    assert state["path_summary"]["status"] == "not_started"
    assert state["path_summary"]["path_id"] is None
    assert state["mastery_summary"]["total_count"] == 0


def test_learning_state_promotes_course_question_candidate_to_pending_review_item() -> None:
    event_time = datetime(2026, 7, 5, 8, 30, tzinfo=UTC)
    repo = FakeCourseRepository(
        courses=[make_course()],
        profiles={
            1: StudentProfile(
                id=9,
                user_id=1,
                profile_json={
                    "learning_goal": "期末前掌握搜索算法",
                    "knowledge_foundation": "机器学习刚入门",
                    "weak_points": ["链式法则"],
                },
                confidence_score=Decimal("0.64"),
            )
        },
        profile_events=[make_candidate_event(1, 1, 101, created_at=event_time)],
    )

    state = as_dict(make_service(repo).get_learning_state(make_user(), 101))

    assert len(repo.weakness_items) == 1
    created_item = repo.weakness_items[0]
    assert created_item.user_id == 1
    assert created_item.course_id == 101
    assert created_item.knowledge_point_id == 401
    assert created_item.title == "启发式搜索"
    assert created_item.source_type == "course_question"
    assert created_item.status == "pending"
    assert created_item.recommended_resource_ids == []
    assert created_item.next_review_at is None
    assert state["profile_overlay"]["learning_goal"] == "期末前掌握搜索算法"
    assert state["profile_overlay"]["weak_points"] == []
    assert state["learner_context"]["active_weaknesses"] == []
    assert state["weakness_summary"]["candidate_event_count"] == 1
    assert state["weakness_summary"]["pending_count"] == 1
    assert state["weakness_summary"]["latest_evidence_at"] == "2026-07-05T08:30:00Z"
    assert state["weakness_review_queue"][0]["title"] == "启发式搜索"
    assert state["weakness_review_queue"][0]["status"] == "pending"
    assert state["evidence_summary"]["latest_trace_id"] == "trace_candidate"


def test_learning_state_deduplicates_by_knowledge_point_and_title() -> None:
    repo = FakeCourseRepository(
        courses=[make_course()],
        profile_events=[
            make_candidate_event(1, 1, 101, knowledge_point_id=401, section_title="启发式搜索"),
            make_candidate_event(2, 1, 101, knowledge_point_id=401, section_title="A* 搜索"),
            make_candidate_event(3, 1, 101, knowledge_point_id=None, section_title="反向传播"),
            make_candidate_event(4, 1, 101, knowledge_point_id=None, section_title="反向传播"),
        ],
    )

    state = as_dict(make_service(repo).get_learning_state(make_user(), 101))

    assert [item.title for item in repo.weakness_items] == ["启发式搜索", "反向传播"]
    assert state["weakness_summary"]["candidate_event_count"] == 4
    assert state["weakness_summary"]["pending_count"] == 2


def test_learning_state_isolates_users_courses_and_existing_items() -> None:
    existing = make_weakness_item(55, 1, 101, title="启发式搜索", knowledge_point_id=401, status="completed")
    repo = FakeCourseRepository(
        courses=[make_course(101, owner_id=1), make_course(202, owner_id=1, title="其他课程"), make_course(303, owner_id=2)],
        weakness_items=[existing, make_weakness_item(56, 2, 303, title="别人弱点", knowledge_point_id=999)],
        profile_events=[
            make_candidate_event(1, 1, 101, knowledge_point_id=401, section_title="启发式搜索"),
            make_candidate_event(2, 1, 202, knowledge_point_id=402, section_title="其他课程弱点"),
            make_candidate_event(3, 2, 101, knowledge_point_id=403, section_title="别人事件"),
        ],
    )

    state = as_dict(make_service(repo).get_learning_state(make_user(1), 101))

    assert len(repo.weakness_items) == 2
    assert state["weakness_summary"]["candidate_event_count"] == 1
    assert state["weakness_summary"]["pending_count"] == 0
    assert state["weakness_summary"]["completed_count"] == 1
    assert [item["title"] for item in state["weakness_review_queue"]] == ["启发式搜索"]

    from backend.app.services.courses import CourseNotFoundError

    with pytest.raises(CourseNotFoundError):
        make_service(repo).get_learning_state(make_user(1), 303)


def test_learning_state_hides_dismissed_items_and_prevents_requeue() -> None:
    dismissed = make_weakness_item(55, 1, 101, title="启发式搜索", knowledge_point_id=401, status="dismissed")
    repo = FakeCourseRepository(
        courses=[make_course()],
        weakness_items=[dismissed],
        profile_events=[make_candidate_event(1, 1, 101, knowledge_point_id=401, section_title="启发式搜索")],
    )

    state = as_dict(make_service(repo).get_learning_state(make_user(), 101))

    assert len(repo.weakness_items) == 1
    assert state["weakness_review_queue"] == []
    assert state["weakness_summary"]["pending_count"] == 0
    assert state["weakness_summary"]["dismissed_count"] == 1


def test_update_weakness_review_item_allows_expected_status_transitions() -> None:
    transitions = [
        ("pending", "confirm", "confirmed"),
        ("pending", "start", "reviewing"),
        ("pending", "complete", "completed"),
        ("pending", "dismiss", "dismissed"),
        ("confirmed", "start", "reviewing"),
        ("confirmed", "complete", "completed"),
        ("confirmed", "dismiss", "dismissed"),
        ("reviewing", "complete", "completed"),
        ("reviewing", "dismiss", "dismissed"),
        ("completed", "dismiss", "dismissed"),
        ("dismissed", "dismiss", "dismissed"),
    ]

    for initial_status, action, expected_status in transitions:
        item = make_weakness_item(55, 1, 101, status=initial_status)
        repo = FakeCourseRepository(courses=[make_course()], weakness_items=[item])

        updated = as_dict(make_service(repo).update_weakness_review_item(make_user(), 101, 55, action))

        assert updated["status"] == expected_status
        assert item.status == expected_status
        if action == "complete":
            assert item.next_review_at is not None


def test_update_weakness_review_item_rejects_invalid_transitions() -> None:
    from backend.app.services.courses import CourseWeaknessStateTransitionError

    item = make_weakness_item(55, 1, 101, status="dismissed")
    repo = FakeCourseRepository(courses=[make_course()], weakness_items=[item])

    with pytest.raises(CourseWeaknessStateTransitionError):
        make_service(repo).update_weakness_review_item(make_user(), 101, 55, "start")

    assert item.status == "dismissed"


def test_update_weakness_review_item_scopes_user_course_and_item() -> None:
    from backend.app.services.courses import CourseNotFoundError

    repo = FakeCourseRepository(
        courses=[make_course(101, owner_id=1), make_course(202, owner_id=1), make_course(303, owner_id=2)],
        weakness_items=[
            make_weakness_item(55, 1, 202, title="其他课程弱点"),
            make_weakness_item(56, 2, 303, title="其他用户弱点"),
        ],
    )

    with pytest.raises(CourseNotFoundError):
        make_service(repo).update_weakness_review_item(make_user(1), 101, 55, "confirm")

    with pytest.raises(CourseNotFoundError):
        make_service(repo).update_weakness_review_item(make_user(1), 303, 56, "confirm")


def test_learning_state_response_does_not_expose_private_prompt_or_source_text() -> None:
    event = make_candidate_event(1, 1, 101, section_title=None, source_title="神经网络讲义.md")
    event.evidence_json["raw_question"] = "为什么反向传播这么难？这是完整用户问题"
    event.evidence_json["system_prompt"] = "系统提示词"
    event.evidence_json["model_input"] = "模型输入"
    event.evidence_json["citations"][0]["content"] = "资料原文里很长的一段内容"
    repo = FakeCourseRepository(courses=[make_course()], profile_events=[event])

    state = as_dict(make_service(repo).get_learning_state(make_user(), 101))
    serialized = str(state)

    assert state["weakness_review_queue"][0]["title"] == "神经网络讲义.md"
    assert "完整用户问题" not in serialized
    assert "系统提示词" not in serialized
    assert "模型输入" not in serialized
    assert "资料原文" not in serialized


def test_learning_state_returns_real_path_mastery_and_resource_recommendations() -> None:
    path = make_learning_path(901)
    reviewing = make_weakness_item(55, 1, 101, knowledge_point_id=401, status="reviewing")
    reviewing.diagnosis_json = {
        "misconception": "把启发函数当成真实剩余代价",
        "missing_concepts": ["估计值", "可采纳性"],
        "recommended_action": "对照课程证据完成一次针对性再测",
        "confidence": 0.88,
        "evidence_count": 2,
        "baseline_score": 35,
        "latest_score": 70,
        "attempt_count": 1,
        "last_practice_session_id": "501",
        "raw_answer": "不得返回的学生原始答案",
    }
    completed = make_weakness_item(56, 1, 101, title="A* 搜索", knowledge_point_id=402, status="completed")
    completed.next_review_at = datetime(2026, 7, 4, 8, 0, tzinfo=UTC)
    repo = FakeCourseRepository(
        courses=[make_course()],
        knowledge_points=[
            KnowledgePoint(id=401, course_id=101, title="启发式搜索", summary="摘要", chapter="第一章", order_index=0),
            KnowledgePoint(id=402, course_id=101, title="A* 搜索", summary="摘要", chapter="第一章", order_index=1),
            KnowledgePoint(id=403, course_id=101, title="局部搜索", summary="摘要", chapter="第一章", order_index=2),
        ],
        weakness_items=[reviewing, completed],
        generated_resources=[
            make_resource(801, 1, 101, knowledge_point_id=401),
            make_resource(802, 1, 101, title="A* 搜索讲解", knowledge_point_id=402),
        ],
        learning_paths=[path],
        learning_tasks=[
            make_learning_task(1001, 901, knowledge_point_id=401, status="doing"),
            make_learning_task(1002, 901, knowledge_point_id=403, title="学习局部搜索", task_type="learn", status="todo"),
        ],
    )

    state = as_dict(make_service(repo).get_learning_state(make_user(), 101))

    assert state["path_summary"] == {
        "status": "active",
        "message": "当前学习路径进行中。",
        "path_id": "901",
        "current_task_title": "复习启发式搜索",
        "task_count": 2,
        "completed_task_count": 0,
    }
    assert state["mastery_summary"]["total_count"] == 3
    assert state["mastery_summary"]["weak_count"] == 1
    assert state["mastery_summary"]["learning_count"] == 0
    assert state["mastery_summary"]["recommended_review_count"] == 1
    assert state["mastery_summary"]["assessed_count"] == 2
    assert state["mastery_summary"]["unassessed_count"] == 1
    by_title = {item["title"]: item for item in state["weakness_review_queue"]}
    assert by_title["启发式搜索"]["recommended_resource_ids"] == ["801"]
    assert by_title["启发式搜索"]["recommended_resources"][0]["title"] == "启发式搜索讲解"
    assert by_title["启发式搜索"]["next_review_at"] is not None
    assert by_title["启发式搜索"]["diagnosis"] == {
        "misconception": "把启发函数当成真实剩余代价",
        "missing_concepts": ["估计值", "可采纳性"],
        "recommended_action": "对照课程证据完成一次针对性再测",
        "confidence": 0.88,
        "evidence_count": 2,
        "baseline_score": 35,
        "latest_score": 70,
        "improvement": 35,
        "attempt_count": 1,
        "last_practice_session_id": "501",
    }
    assert "不得返回的学生原始答案" not in str(state)


def test_mastery_map_maps_weaknesses_tasks_resources_and_scopes_course() -> None:
    path = make_learning_path(901)
    repo = FakeCourseRepository(
        courses=[make_course(), make_course(202, owner_id=2)],
        knowledge_points=[
            KnowledgePoint(id=401, course_id=101, title="启发式搜索", summary="摘要", chapter="第一章", order_index=0),
            KnowledgePoint(id=402, course_id=101, title="A* 搜索", summary="摘要", chapter="第一章", order_index=1),
            KnowledgePoint(id=403, course_id=101, title="局部搜索", summary="摘要", chapter="第一章", order_index=2),
        ],
        weakness_items=[
            make_weakness_item(55, 1, 101, knowledge_point_id=401, status="confirmed"),
            make_weakness_item(56, 1, 101, title="A* 搜索", knowledge_point_id=402, status="completed"),
        ],
        generated_resources=[make_resource(801, 1, 101, knowledge_point_id=401)],
        learning_paths=[path],
        learning_tasks=[
            make_learning_task(1001, 901, knowledge_point_id=401, status="todo"),
            make_learning_task(1002, 901, knowledge_point_id=403, title="完成局部搜索", status="completed"),
        ],
    )

    mastery = as_dict(make_service(repo).get_mastery_map(make_user(), 101))

    by_title = {point["title"]: point for point in mastery["points"]}
    assert by_title["启发式搜索"]["status"] == "weak"
    assert by_title["启发式搜索"]["score"] == 35
    assert by_title["启发式搜索"]["weakness_item_ids"] == ["55"]
    assert by_title["启发式搜索"]["recommended_resource_ids"] == ["801"]
    assert by_title["局部搜索"]["status"] == "not_started"
    assert by_title["局部搜索"]["score"] is None
    assert mastery["summary"]["weak_count"] == 1
    assert mastery["summary"]["mastered_count"] == 0
    assert mastery["summary"]["learning_count"] == 1
    assert mastery["summary"]["unassessed_count"] == 1

    serialized = str(mastery)
    assert "系统提示词" not in serialized
    assert "模型输入" not in serialized
    assert "资料原文" not in serialized

    from backend.app.services.courses import CourseNotFoundError

    with pytest.raises(CourseNotFoundError):
        make_service(repo).get_mastery_map(make_user(1), 202)


def test_mastery_map_uses_practice_answers_to_mark_weak_and_mastered_points() -> None:
    repo = FakeCourseRepository(
        courses=[make_course()],
        knowledge_points=[
            KnowledgePoint(id=401, course_id=101, title="启发式搜索", summary="摘要", chapter="第一章", order_index=0),
            KnowledgePoint(id=402, course_id=101, title="A* 搜索", summary="摘要", chapter="第一章", order_index=1),
        ],
        practice_answers=[
            make_practice_answer(901, 401, score=0, is_correct=False),
            make_practice_answer(902, 402, score=100, is_correct=True),
        ],
    )

    mastery = as_dict(make_service(repo).get_mastery_map(make_user(), 101))

    by_title = {point["title"]: point for point in mastery["points"]}
    assert by_title["启发式搜索"]["status"] == "weak"
    assert by_title["启发式搜索"]["score"] == 0
    assert by_title["A* 搜索"]["status"] == "mastered"
    assert by_title["A* 搜索"]["score"] == 100
    assert mastery["summary"]["average_score"] == 50
    assert mastery["summary"]["weak_count"] == 1
    assert mastery["summary"]["mastered_count"] == 1


def test_mastery_map_uses_latest_attempt_instead_of_lifetime_average() -> None:
    completed = make_weakness_item(55, 1, 101, knowledge_point_id=401, status="completed")
    completed.next_review_at = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    repo = FakeCourseRepository(
        courses=[make_course()],
        knowledge_points=[KnowledgePoint(id=401, course_id=101, title="启发式搜索", summary="摘要", chapter="第一章", order_index=0)],
        weakness_items=[completed],
        practice_answers=[
            make_practice_answer(901, 401, score=3, is_correct=False, session_id=900, created_at=datetime(2026, 7, 5, 9, 0, tzinfo=UTC)),
            make_practice_answer(902, 401, score=98, is_correct=True, session_id=901, created_at=datetime(2026, 7, 6, 9, 0, tzinfo=UTC)),
        ],
    )

    mastery = as_dict(make_service(repo).get_mastery_map(make_user(), 101))

    assert mastery["points"][0]["status"] == "mastered"
    assert mastery["points"][0]["score"] == 98
    assert mastery["summary"]["average_score"] == 98


def test_create_course_route_returns_envelope() -> None:
    repo = FakeCourseRepository(materials=[make_material(1, 1, "route.md", "# 路由测试\n正文")])
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="courses-test-secret-with-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_course_service] = lambda: CourseService(repository=repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    response = client.post(
        "/api/v1/courses/from-materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"material_ids": [1], "course_title": "路由课程"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["course"]["title"] == "路由课程"


def test_learning_state_route_returns_envelope_and_scopes_course() -> None:
    repo = FakeCourseRepository(
        courses=[make_course()],
        profile_events=[make_candidate_event(1, 1, 101)],
    )
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="courses-test-secret-with-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_course_service] = lambda: CourseService(repository=repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    response = client.get(
        "/api/v1/courses/101/learning-state",
        headers={"Authorization": f"Bearer {token}"},
    )
    missing_response = client.get(
        "/api/v1/courses/202/learning-state",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["course_id"] == "101"
    assert response.json()["data"]["weakness_summary"]["pending_count"] == 1
    assert missing_response.status_code == 404


def test_mastery_map_route_returns_envelope_and_scopes_course() -> None:
    repo = FakeCourseRepository(
        courses=[make_course()],
        knowledge_points=[KnowledgePoint(id=401, course_id=101, title="启发式搜索", summary="摘要", chapter="第一章", order_index=0)],
        weakness_items=[make_weakness_item(55, 1, 101, knowledge_point_id=401, status="confirmed")],
    )
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="courses-test-secret-with-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_course_service] = lambda: CourseService(repository=repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/courses/101/mastery-map", headers=headers)
    missing_response = client.get("/api/v1/courses/202/mastery-map", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["course_id"] == "101"
    assert response.json()["data"]["points"][0]["status"] == "weak"
    assert missing_response.status_code == 404


def test_knowledge_point_content_route_returns_envelope_and_scopes_point() -> None:
    repo = FakeCourseRepository(
        courses=[make_course()],
        course_materials=[
            CourseMaterial(
                id=301,
                user_id=1,
                course_id=101,
                filename="课程讲义.md",
                content_type="text/markdown",
                storage_path="private/course.md",
                parse_status="completed",
                metadata_json={},
            )
        ],
        knowledge_points=[KnowledgePoint(id=401, course_id=101, title="启发式搜索", summary="摘要", chapter="第一章", order_index=0)],
        knowledge_chunks=[KnowledgeChunk(id=601, course_id=101, material_id=301, knowledge_point_id=401, content="真实课程正文", metadata_json={})],
    )
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="courses-test-secret-with-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(repository=TokenAuthRepository(user), settings=settings)
    app.dependency_overrides[get_course_service] = lambda: CourseService(repository=repo)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id), settings=settings)}"}

    response = client.get("/api/v1/courses/101/knowledge-points/401/content", headers=headers)
    missing_response = client.get("/api/v1/courses/101/knowledge-points/999/content", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["sections"][0]["content"] == "真实课程正文"
    assert missing_response.status_code == 404


def test_weakness_review_action_route_updates_item_and_handles_errors() -> None:
    repo = FakeCourseRepository(
        courses=[make_course(101, owner_id=1), make_course(202, owner_id=1)],
        weakness_items=[
            make_weakness_item(55, 1, 101, status="pending"),
            make_weakness_item(56, 1, 202, title="其他课程弱点", status="pending"),
            make_weakness_item(57, 1, 101, title="已忽略弱点", status="dismissed"),
        ],
    )
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="courses-test-secret-with-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_course_service] = lambda: CourseService(repository=repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)
    headers = {"Authorization": f"Bearer {token}"}

    confirmed_response = client.post("/api/v1/courses/101/weakness-review-items/55/confirm", headers=headers)
    cross_course_response = client.post("/api/v1/courses/101/weakness-review-items/56/confirm", headers=headers)
    invalid_response = client.post("/api/v1/courses/101/weakness-review-items/57/start", headers=headers)

    assert confirmed_response.status_code == 200
    assert confirmed_response.json()["data"]["status"] == "confirmed"
    assert cross_course_response.status_code == 404
    assert invalid_response.status_code == 400
