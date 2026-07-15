from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

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
    PracticeAnswer,
    PracticeSession,
    ProfileEvent,
    StudentProfile,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.courses import (
    CourseEvidenceSummary,
    CourseKnowledgePoint,
    CourseKnowledgePointContent,
    CourseKnowledgeSection,
    CourseLearningState,
    CourseListResponse,
    CourseMasteryMap,
    CourseMasteryPoint,
    CourseMasterySummary,
    CourseOverview,
    CoursePathSummary,
    CourseProfileOverlay,
    CourseLearnerContextResponse,
    CourseSummary,
    CourseStructureSummary,
    CourseWeaknessReviewItem,
    CourseWeaknessSummary,
    CreateCourseFromMaterialsResult,
    iso_timestamp,
    weakness_item_to_api,
    resource_brief,
)
from backend.app.schemas.profiles import normalize_profile_json
from backend.app.services.material_retrieval import MaterialChunkingService
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.model_settings import ModelSettingsService
from backend.app.core.errors import NotFoundDomainError, ValidationDomainError


class CourseGenerationError(ValidationDomainError):
    pass


class CourseNotFoundError(NotFoundDomainError):
    pass


class CourseWeaknessStateTransitionError(ValidationDomainError):
    pass


@dataclass(frozen=True)
class ParsedSection:
    title: str
    chapter: str | None
    content: str
    material: Material


@dataclass(frozen=True)
class WeaknessCandidate:
    title: str
    knowledge_point_id: int | None
    trace_id: str | None
    source_title: str | None
    section_title: str | None


class CourseRepository(Protocol):
    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]: ...

    def list_material_chunks(self, material_ids: list[int]) -> list[MaterialChunk]: ...

    def add_material_chunks(self, chunks: list[MaterialChunk]) -> None: ...

    def add_course_graph(
        self,
        course: Course,
        enrollment: CourseEnrollment,
        course_materials: list[CourseMaterial],
        material_links: list[CourseMaterialLink],
        knowledge_points: list[KnowledgePoint],
        knowledge_chunks: list[KnowledgeChunk],
    ) -> Course: ...

    def list_courses_for_user(self, user_id: int, source_type: str | None = None) -> list[Course]: ...

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]: ...

    def get_profile(self, user_id: int) -> StudentProfile | None: ...

    def list_weakness_candidate_events(self, user_id: int, course_id: int) -> list[ProfileEvent]: ...

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]: ...

    def get_weakness_review_item(self, user_id: int, course_id: int, item_id: int) -> WeaknessReviewItem | None: ...

    def add_weakness_review_item(self, item: WeaknessReviewItem) -> None: ...

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]: ...

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None: ...

    def list_learning_tasks(self, user_id: int, course_id: int) -> list[LearningTask]: ...

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]: ...

    def list_practice_answers(self, user_id: int, course_id: int) -> list[PracticeAnswer]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class CourseEmbeddingService(Protocol):
    def embed_texts(self, user: User, texts: list[str]) -> Any: ...

    def apply_embeddings(self, user: User, chunks: list[KnowledgeChunk]) -> Any: ...


class SqlAlchemyCourseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        if not material_ids:
            return []
        return list(self.db.scalars(select(Material).where(Material.user_id == user_id, Material.id.in_(material_ids))))

    def list_material_chunks(self, material_ids: list[int]) -> list[MaterialChunk]:
        if not material_ids:
            return []
        return list(
            self.db.scalars(
                select(MaterialChunk)
                .where(MaterialChunk.material_id.in_(material_ids))
                .order_by(MaterialChunk.material_id, MaterialChunk.chunk_index)
            )
        )

    def add_material_chunks(self, chunks: list[MaterialChunk]) -> None:
        self.db.add_all(chunks)
        self.db.flush()

    def add_course_graph(
        self,
        course: Course,
        enrollment: CourseEnrollment,
        course_materials: list[CourseMaterial],
        material_links: list[CourseMaterialLink],
        knowledge_points: list[KnowledgePoint],
        knowledge_chunks: list[KnowledgeChunk],
    ) -> Course:
        self.db.add(course)
        self.db.flush()

        enrollment.course_id = course.id
        self.db.add(enrollment)

        source_to_course_material: dict[int, CourseMaterial] = {}
        for course_material in course_materials:
            source_material_id = int((course_material.metadata_json or {}).get("source_material_id"))
            course_material.course_id = course.id
            self.db.add(course_material)
            self.db.flush()
            source_to_course_material[source_material_id] = course_material

        for link in material_links:
            link.course_id = course.id
            self.db.add(link)

        point_by_key: dict[str, KnowledgePoint] = {}
        for index, knowledge_point in enumerate(knowledge_points):
            knowledge_point.course_id = course.id
            self.db.add(knowledge_point)
            self.db.flush()
            point_by_key[str(getattr(knowledge_point, "builder_key", f"kp-{index + 1}"))] = knowledge_point

        for knowledge_point in knowledge_points:
            local_prerequisites = list(knowledge_point.prerequisites_json or [])
            knowledge_point.prerequisites_json = [
                point_by_key[key].id
                for key in local_prerequisites
                if key in point_by_key and point_by_key[key].id != knowledge_point.id
            ]

        for chunk in knowledge_chunks:
            source_material_id = int((chunk.metadata_json or {}).get("source_material_id"))
            source_order = int((chunk.metadata_json or {}).get("knowledge_point_order", 0))
            source_key = str((chunk.metadata_json or {}).get("knowledge_point_key") or "")
            chunk.course_id = course.id
            chunk.material_id = source_to_course_material[source_material_id].id
            if source_key in point_by_key:
                chunk.knowledge_point_id = point_by_key[source_key].id
            elif 0 <= source_order < len(knowledge_points):
                chunk.knowledge_point_id = knowledge_points[source_order].id
            self.db.add(chunk)

        self.db.flush()
        return course

    def list_courses_for_user(self, user_id: int, source_type: str | None = None) -> list[Course]:
        statement = select(Course).where(Course.owner_id == user_id)
        if source_type:
            statement = statement.where(Course.source_type == source_type)
        return list(self.db.scalars(statement.order_by(Course.updated_at.desc(), Course.id.desc())))

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]:
        return list(self.db.scalars(select(CourseMaterial).where(CourseMaterial.course_id == course_id).order_by(CourseMaterial.id)))

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint).where(KnowledgePoint.course_id == course_id).order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        return list(self.db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.course_id == course_id).order_by(KnowledgeChunk.id)))

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def list_weakness_candidate_events(self, user_id: int, course_id: int) -> list[ProfileEvent]:
        events = list(
            self.db.scalars(
                select(ProfileEvent)
                .where(ProfileEvent.user_id == user_id, ProfileEvent.dimension == "weak_points")
                .order_by(ProfileEvent.created_at.desc(), ProfileEvent.id.desc())
            )
        )
        return [
            event
            for event in events
            if (event.evidence_json or {}).get("source_type") == "course_question"
            and (event.evidence_json or {}).get("course_id") == course_id
        ]

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return list(
            self.db.scalars(
                select(WeaknessReviewItem)
                .where(WeaknessReviewItem.user_id == user_id, WeaknessReviewItem.course_id == course_id)
                .order_by(WeaknessReviewItem.created_at.desc(), WeaknessReviewItem.id.desc())
            )
        )

    def get_weakness_review_item(self, user_id: int, course_id: int, item_id: int) -> WeaknessReviewItem | None:
        return self.db.scalar(
            select(WeaknessReviewItem).where(
                WeaknessReviewItem.id == item_id,
                WeaknessReviewItem.user_id == user_id,
                WeaknessReviewItem.course_id == course_id,
            )
        )

    def add_weakness_review_item(self, item: WeaknessReviewItem) -> None:
        self.db.add(item)
        self.db.flush()

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return list(
            self.db.scalars(
                select(GeneratedResource)
                .where(GeneratedResource.user_id == user_id, GeneratedResource.course_id == course_id)
                .order_by(GeneratedResource.updated_at.desc(), GeneratedResource.id.desc())
            )
        )

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None:
        return self.db.scalar(
            select(LearningPath)
            .where(LearningPath.user_id == user_id, LearningPath.course_id == course_id, LearningPath.status == "active")
            .order_by(LearningPath.updated_at.desc(), LearningPath.id.desc())
        )

    def list_learning_tasks(self, user_id: int, course_id: int) -> list[LearningTask]:
        return list(
            self.db.scalars(
                select(LearningTask)
                .where(LearningTask.user_id == user_id, LearningTask.course_id == course_id)
                .order_by(LearningTask.id.asc())
            )
        )

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]:
        return list(
            self.db.scalars(
                select(LearningTask)
                .where(LearningTask.path_id == path_id)
                .order_by(LearningTask.id.asc())
            )
        )

    def list_practice_answers(self, user_id: int, course_id: int) -> list[PracticeAnswer]:
        return list(
            self.db.scalars(
                select(PracticeAnswer)
                .join(PracticeSession, PracticeSession.id == PracticeAnswer.session_id)
                .where(PracticeAnswer.user_id == user_id, PracticeSession.course_id == course_id)
                .order_by(PracticeAnswer.created_at.desc(), PracticeAnswer.id.desc())
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)


class CourseService:
    generation_error = CourseGenerationError
    text_extensions = {".txt", ".md", ".markdown", ".pdf", ".docx", ".pptx"}
    chunk_size = 900
    weakness_action_target_status = {
        "confirm": "confirmed",
        "start": "reviewing",
        "complete": "completed",
        "dismiss": "dismissed",
    }
    weakness_allowed_actions = {
        "pending": {"confirm", "start", "complete", "dismiss"},
        "confirmed": {"start", "complete", "dismiss"},
        "reviewing": {"complete", "dismiss"},
        "completed": {"dismiss"},
        "dismissed": {"dismiss"},
    }

    def __init__(
        self,
        repository: CourseRepository,
        embedding_service: CourseEmbeddingService | None = None,
        *,
        model_service: ModelSettingsService | None = None,
        trace_recorder: Any | None = None,
        chunking_service: MaterialChunkingService | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_service = embedding_service
        self.model_service = model_service
        self.trace_recorder = trace_recorder
        self.chunking_service = chunking_service or MaterialChunkingService()

    def create_course_from_materials(
        self,
        user: User,
        material_ids: list[int],
        course_title: str = "",
    ) -> CreateCourseFromMaterialsResult:
        from backend.app.agents.course_builder import CourseBuilderGraphRunner

        return CourseBuilderGraphRunner(self).generate(user=user, material_ids=material_ids, course_title=course_title)

    def list_courses(self, user: User, source_type: str | None = None) -> CourseListResponse:
        courses = self.repository.list_courses_for_user(user.id, source_type)
        data = [self._build_summary(course) for course in courses]
        return CourseListResponse(data=data, page=1, page_size=len(data), total=len(data))

    def get_course(self, user: User, course_id: int) -> CourseSummary:
        course = self._require_course(user, course_id)
        return self._build_summary(course)

    def get_overview(self, user: User, course_id: int) -> CourseOverview:
        course = self._require_course(user, course_id)
        materials = self.repository.list_course_materials(course.id)
        points = self.repository.list_knowledge_points(course.id)
        chunks = self.repository.list_knowledge_chunks(course.id)
        return CourseOverview(
            course=self._build_summary(course, len(materials), len(points), len(chunks)),
            materials=[material.filename for material in materials],
            knowledge_points=[self._build_knowledge_point(point) for point in points],
            chunk_count=len(chunks),
            structure=CourseStructureSummary(**course.structure_json) if getattr(course, "structure_json", None) else None,
        )

    def get_knowledge_points(self, user: User, course_id: int) -> list[CourseKnowledgePoint]:
        course = self._require_course(user, course_id)
        return [self._build_knowledge_point(point) for point in self.repository.list_knowledge_points(course.id)]

    def get_knowledge_point_content(
        self,
        user: User,
        course_id: int,
        knowledge_point_id: int,
    ) -> CourseKnowledgePointContent:
        course = self._require_course(user, course_id)
        points = self.repository.list_knowledge_points(course.id)
        point_index = next((index for index, item in enumerate(points) if item.id == knowledge_point_id), None)
        if point_index is None:
            raise CourseNotFoundError("课程知识点不存在或无权访问。")

        point = points[point_index]
        materials_by_id = {item.id: item for item in self.repository.list_course_materials(course.id)}
        chunks = [
            item
            for item in self.repository.list_knowledge_chunks(course.id)
            if item.knowledge_point_id == point.id
        ][:12]
        resources = [
            item
            for item in self.repository.list_generated_resources(user.id, course.id)
            if item.knowledge_point_id == point.id
        ]
        sections = []
        for chunk in chunks:
            material = materials_by_id.get(chunk.material_id)
            metadata = chunk.metadata_json or {}
            source_title = material.filename if material is not None else str(metadata.get("source_filename") or "课程资料")
            sections.append(
                CourseKnowledgeSection(
                    chunk_id=str(chunk.id),
                    title=(chunk.section_title or point.chapter or point.title)[:255],
                    content=chunk.content.strip()[:1200],
                    source_title=source_title[:255],
                    page_number=chunk.page_number,
                )
            )

        return CourseKnowledgePointContent(
            knowledge_point=self._build_knowledge_point(point),
            sections=sections,
            related_resources=[resource_brief(item) for item in resources],
            previous_knowledge_point_id=str(points[point_index - 1].id) if point_index > 0 else None,
            next_knowledge_point_id=str(points[point_index + 1].id) if point_index + 1 < len(points) else None,
        )

    def get_mastery_map(self, user: User, course_id: int) -> CourseMasteryMap:
        course = self._require_course(user, course_id)
        knowledge_points = self.repository.list_knowledge_points(course.id)
        review_items = self.repository.list_weakness_review_items(user.id, course.id)
        resources = self.repository.list_generated_resources(user.id, course.id)
        tasks = self.repository.list_learning_tasks(user.id, course.id)
        practice_answers = self.repository.list_practice_answers(user.id, course.id)
        points = self._build_mastery_points(knowledge_points, review_items, resources, tasks, practice_answers)
        return CourseMasteryMap(
            course_id=str(course.id),
            summary=self._build_mastery_summary(points),
            points=points,
        )

    def get_learning_state(self, user: User, course_id: int) -> CourseLearningState:
        course = self._require_course(user, course_id)
        candidate_events = self.repository.list_weakness_candidate_events(user.id, course.id)
        self._sync_weakness_review_queue(user, course.id, candidate_events)
        review_items = self.repository.list_weakness_review_items(user.id, course.id)
        resources = self.repository.list_generated_resources(user.id, course.id)
        if self._sync_weakness_resource_recommendations(review_items, resources):
            self.repository.commit()
        profile = self.repository.get_profile(user.id)
        profile_json = normalize_profile_json(profile.profile_json if profile is not None else None)
        latest_event = max(candidate_events, key=lambda event: (event.created_at, event.id), default=None)
        latest_candidate = self._candidate_from_event(latest_event) if latest_event is not None else None
        path = self.repository.get_active_path(user.id, course.id)
        path_tasks = self.repository.list_tasks_for_path(path.id) if path is not None else []
        mastery_points = self._build_mastery_points(
            self.repository.list_knowledge_points(course.id),
            review_items,
            resources,
            self.repository.list_learning_tasks(user.id, course.id),
            self.repository.list_practice_answers(user.id, course.id),
        )
        resources_by_id = {resource.id: resource for resource in resources}
        context_service = context_service_from_repository(self.repository)
        learner_context = context_service.course_context(user.id, course.id) if context_service is not None else None
        active_weaknesses = [item.title for item in review_items if item.status in {"confirmed", "reviewing"}]
        fallback_goal = str(path.goal or "").strip() if path is not None else ""
        effective_goal = learner_context.course_goal if learner_context is not None else (fallback_goal or profile_json["learning_goal"])
        foundation_summary = learner_context.foundation_summary if learner_context is not None else profile_json["knowledge_foundation"]
        effective_weaknesses = list(learner_context.active_weaknesses) if learner_context is not None else active_weaknesses
        global_context = learner_context.global_context if learner_context is not None else None

        return CourseLearningState(
            course_id=str(course.id),
            profile_overlay=CourseProfileOverlay(
                learning_goal=effective_goal,
                knowledge_foundation=foundation_summary,
                weak_points=effective_weaknesses,
            ),
            learner_context=CourseLearnerContextResponse(
                profile_applied_version=global_context.profile_applied_version if global_context is not None else 0,
                context_hash=learner_context.context_hash if learner_context is not None else "legacy",
                completeness_score=global_context.completeness_score if global_context is not None else 0,
                evidence_confidence_score=global_context.evidence_confidence_score if global_context is not None else float(getattr(profile, "confidence_score", 0) or 0),
                trusted_dimensions=list(global_context.trusted_dimensions) if global_context is not None else [],
                advisory_dimensions=list(global_context.advisory_dimensions) if global_context is not None else [],
                course_goal=effective_goal,
                foundation_summary=foundation_summary,
                active_weaknesses=effective_weaknesses,
                mastery_average=learner_context.mastery_average if learner_context is not None else None,
                current_task_title=learner_context.current_task_title if learner_context is not None else None,
                recent_practice_score=learner_context.recent_practice_score if learner_context is not None else None,
                learning_preference=str(global_context.advisory_value("learning_preference") or "") if global_context is not None else "",
                cognitive_style=str(global_context.advisory_value("cognitive_style") or "") if global_context is not None else "",
                learning_pace=str(global_context.advisory_value("learning_pace") or "") if global_context is not None else "",
                motivation_interest=str(global_context.advisory_value("motivation_interest") or "") if global_context is not None else "",
            ),
            weakness_summary=self._build_weakness_summary(candidate_events, review_items),
            weakness_review_queue=[weakness_item_to_api(item, resources_by_id) for item in review_items if item.status != "dismissed"],
            path_summary=self._build_path_summary(path, path_tasks),
            mastery_summary=self._build_mastery_summary(mastery_points),
            evidence_summary=CourseEvidenceSummary(
                candidate_event_count=len(candidate_events),
                latest_trace_id=latest_candidate.trace_id if latest_candidate is not None else None,
                latest_source_title=latest_candidate.source_title if latest_candidate is not None else None,
                latest_section_title=latest_candidate.section_title if latest_candidate is not None else None,
            ),
        )

    def update_weakness_review_item(
        self,
        user: User,
        course_id: int,
        item_id: int,
        action: str,
    ) -> CourseWeaknessReviewItem:
        course = self._require_course(user, course_id)
        item = self.repository.get_weakness_review_item(user.id, course.id, item_id)
        if item is None:
            raise CourseNotFoundError("弱点复习项不存在或无权访问。")

        if action not in self.weakness_action_target_status:
            raise CourseWeaknessStateTransitionError("不支持的弱点复习操作。")

        allowed_actions = self.weakness_allowed_actions.get(item.status, set())
        if action not in allowed_actions:
            raise CourseWeaknessStateTransitionError("当前状态不允许执行这个操作。")

        target_status = self.weakness_action_target_status[action]
        if item.status == target_status:
            return weakness_item_to_api(item)

        try:
            item.status = target_status
            if target_status == "completed":
                item.next_review_at = datetime.now(UTC) + timedelta(days=7)
            item.updated_at = datetime.now(UTC)
            self.repository.commit()
            self.repository.refresh(item)
        except Exception:
            self.repository.rollback()
            raise

        return weakness_item_to_api(item)

    def _sync_weakness_review_queue(self, user: User, course_id: int, candidate_events: list[ProfileEvent]) -> None:
        existing_items = self.repository.list_weakness_review_items(user.id, course_id)
        existing_knowledge_point_ids = {item.knowledge_point_id for item in existing_items if item.knowledge_point_id is not None}
        existing_titles = {self._normalize_weakness_title(item.title) for item in existing_items if item.title.strip()}
        created_any = False

        try:
            for event in sorted(candidate_events, key=lambda item: (item.created_at, item.id)):
                candidate = self._candidate_from_event(event)
                if candidate is None:
                    continue

                normalized_title = self._normalize_weakness_title(candidate.title)
                if candidate.knowledge_point_id is not None:
                    if candidate.knowledge_point_id in existing_knowledge_point_ids:
                        continue
                    existing_knowledge_point_ids.add(candidate.knowledge_point_id)
                elif normalized_title in existing_titles:
                    continue

                now = datetime.now(UTC)
                self.repository.add_weakness_review_item(
                    WeaknessReviewItem(
                        user_id=user.id,
                        course_id=course_id,
                        knowledge_point_id=candidate.knowledge_point_id,
                        title=candidate.title,
                        source_type="course_question",
                        status="pending",
                        recommended_resource_ids=[],
                        next_review_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                existing_titles.add(normalized_title)
                created_any = True

            if created_any:
                self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

    def _ordered_materials(self, user_id: int, material_ids: list[int]) -> list[Material]:
        materials = self.repository.get_materials_for_user(user_id, material_ids)
        by_id = {material.id: material for material in materials}
        return [by_id[material_id] for material_id in material_ids if material_id in by_id]

    def _validate_materials(self, materials: list[Material], material_ids: list[int]) -> None:
        if len(materials) != len(material_ids):
            raise CourseGenerationError("资料不存在或无权访问。")

        for material in materials:
            if (
                material.parse_status != "completed"
                or material.ingestion_status != "confirmed"
                or not (material.quality_json or {}).get("passed")
                or not material.extracted_text
                or self._extension(material.filename) not in self.text_extensions
            ):
                raise CourseGenerationError("请先完成资料精细解析并确认目录，再生成课程。")

    def _parse_sections(self, materials: list[Material]) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        for material in materials:
            extension = self._extension(material.filename)
            text = material.extracted_text or ""
            if extension in {".md", ".markdown"}:
                sections.extend(self._parse_markdown(material, text))
            else:
                sections.extend(self._parse_plain_text(material, text))
        return sections

    def _parse_markdown(self, material: Material, text: str) -> list[ParsedSection]:
        lines = text.splitlines()
        heading_indexes: list[tuple[int, int, str]] = []
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            marker, _, title = stripped.partition(" ")
            if 1 <= len(marker) <= 3 and set(marker) == {"#"} and title.strip():
                heading_indexes.append((index, len(marker), title.strip()))

        if not heading_indexes:
            return self._parse_plain_text(material, text)

        sections: list[ParsedSection] = []
        current_chapter: str | None = None
        for heading_position, (line_index, level, title) in enumerate(heading_indexes):
            if level == 1:
                current_chapter = title
            next_line_index = heading_indexes[heading_position + 1][0] if heading_position + 1 < len(heading_indexes) else len(lines)
            content = self._clean_text("\n".join(lines[line_index + 1 : next_line_index]))
            if not content:
                content = title
            sections.append(
                ParsedSection(
                    title=title,
                    chapter=title if level == 1 else current_chapter,
                    content=content,
                    material=material,
                )
            )
        return sections

    def _parse_plain_text(self, material: Material, text: str) -> list[ParsedSection]:
        paragraphs = [self._clean_text(part) for part in text.replace("\r\n", "\n").split("\n\n")]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]
        return [
            ParsedSection(
                title=f"第 {index} 部分",
                chapter=None,
                content=paragraph,
                material=material,
            )
            for index, paragraph in enumerate(paragraphs, start=1)
        ]

    def _build_course_material(self, user: User, material: Material) -> CourseMaterial:
        return CourseMaterial(
            user_id=user.id,
            course_id=0,
            filename=material.filename,
            content_type=material.content_type,
            storage_path=material.storage_path,
            parse_status=material.parse_status,
            extracted_text=material.extracted_text,
            metadata_json={
                **(material.metadata_json or {}),
                "source_material_id": material.id,
                "generated_from_library": True,
            },
        )

    def _build_chunks(self, sections: list[ParsedSection]) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for index, section in enumerate(sections):
            for chunk_text in self._split_text(section.content):
                chunks.append(
                    KnowledgeChunk(
                        course_id=0,
                        material_id=None,  # type: ignore[arg-type]
                        knowledge_point_id=None,
                        content=chunk_text,
                        page_number=None,
                        section_title=section.title,
                        embedding=None,
                        metadata_json={
                            "source_material_id": section.material.id,
                            "knowledge_point_order": index,
                            "source_filename": section.material.filename,
                        },
                    )
                )
        return chunks

    def _best_effort_embed_chunks(self, user: User, chunks: list[KnowledgeChunk]) -> None:
        if self.embedding_service is None or not chunks:
            return
        try:
            apply_embeddings = getattr(self.embedding_service, "apply_embeddings", None)
            if callable(apply_embeddings):
                apply_embeddings(user, chunks)
                return

            batch = self.embedding_service.embed_texts(user, [chunk.content for chunk in chunks])
            vectors = list(getattr(batch, "vectors", []))
            if len(vectors) != len(chunks):
                return
            source = str(getattr(batch, "source", "unknown"))
            model = str(getattr(batch, "model", "unknown"))
            dimension = int(getattr(batch, "dimension", 1536))
            for chunk, vector in zip(chunks, vectors, strict=True):
                if len(vector) != dimension:
                    continue
                chunk.embedding = vector
                chunk.metadata_json = {
                    **(chunk.metadata_json or {}),
                    "embedding_source": source,
                    "embedding_model": model,
                    "embedding_dimension": dimension,
                }
        except Exception:
            return

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise CourseNotFoundError("课程不存在或无权访问。")
        return course

    @classmethod
    def _candidate_from_event(cls, event: ProfileEvent | None) -> WeaknessCandidate | None:
        if event is None:
            return None
        evidence = event.evidence_json or {}
        if evidence.get("source_type") != "course_question":
            return None
        citations = evidence.get("citations")
        citation = next((item for item in citations if isinstance(item, dict)), {}) if isinstance(citations, list) else {}
        section_title = cls._safe_title(citation.get("section_title"))
        source_title = cls._safe_title(citation.get("source_title"))
        title = section_title or source_title or "课程问答薄弱点"
        return WeaknessCandidate(
            title=title,
            knowledge_point_id=cls._safe_int(citation.get("knowledge_point_id")),
            trace_id=cls._safe_title(evidence.get("trace_id")) or None,
            source_title=source_title or None,
            section_title=section_title or None,
        )

    @staticmethod
    def _build_weakness_summary(candidate_events: list[ProfileEvent], review_items: list[WeaknessReviewItem]) -> CourseWeaknessSummary:
        latest_event = max(candidate_events, key=lambda event: (event.created_at, event.id), default=None)
        return CourseWeaknessSummary(
            candidate_event_count=len(candidate_events),
            pending_count=sum(1 for item in review_items if item.status == "pending"),
            confirmed_count=sum(1 for item in review_items if item.status == "confirmed"),
            reviewing_count=sum(1 for item in review_items if item.status == "reviewing"),
            completed_count=sum(1 for item in review_items if item.status == "completed"),
            dismissed_count=sum(1 for item in review_items if item.status == "dismissed"),
            latest_evidence_at=iso_timestamp(latest_event.created_at) if latest_event is not None else None,
        )

    @staticmethod
    def _build_path_summary(path: LearningPath | None, tasks: list[LearningTask]) -> CoursePathSummary:
        if path is None:
            return CoursePathSummary(
                status="not_started",
                message="学习路径尚未生成。",
                path_id=None,
                current_task_title=None,
                task_count=0,
                completed_task_count=0,
            )
        current_task = next((task for task in tasks if task.status == "doing"), None)
        if current_task is None:
            current_task = next((task for task in tasks if task.status == "todo"), None)
        completed_count = sum(1 for task in tasks if task.status == "completed")
        return CoursePathSummary(
            status=path.status,
            message="当前学习路径进行中。" if path.status == "active" else "学习路径已归档。",
            path_id=str(path.id),
            current_task_title=current_task.title if current_task is not None else None,
            task_count=len(tasks),
            completed_task_count=completed_count,
        )

    @classmethod
    def _build_mastery_points(
        cls,
        knowledge_points: list[KnowledgePoint],
        review_items: list[WeaknessReviewItem],
        resources: list[GeneratedResource],
        tasks: list[LearningTask],
        practice_answers: list[PracticeAnswer] | None = None,
    ) -> list[CourseMasteryPoint]:
        now = datetime.now(UTC)
        weaknesses_by_point: dict[int, list[WeaknessReviewItem]] = {}
        tasks_by_point: dict[int, list[LearningTask]] = {}
        resources_by_point: dict[int, list[GeneratedResource]] = {}
        answers_by_point: dict[int, list[PracticeAnswer]] = {}
        for item in review_items:
            if item.knowledge_point_id is not None:
                weaknesses_by_point.setdefault(item.knowledge_point_id, []).append(item)
        for task in tasks:
            if task.knowledge_point_id is not None:
                tasks_by_point.setdefault(task.knowledge_point_id, []).append(task)
        for resource in resources:
            if resource.knowledge_point_id is not None:
                resources_by_point.setdefault(resource.knowledge_point_id, []).append(resource)
        for answer in practice_answers or []:
            point_id = cls._safe_int((answer.question_json or {}).get("knowledge_point_id"))
            if point_id is not None:
                answers_by_point.setdefault(point_id, []).append(answer)

        points: list[CourseMasteryPoint] = []
        for point in knowledge_points:
            point_weaknesses = weaknesses_by_point.get(point.id, [])
            point_tasks = tasks_by_point.get(point.id, [])
            point_answers = answers_by_point.get(point.id, [])
            status, score, evidence_count, confidence, last_assessed_at = cls._mastery_measure(
                point_weaknesses,
                point_tasks,
                now,
                point_answers,
            )
            points.append(
                CourseMasteryPoint(
                    id=str(point.id),
                    title=point.title,
                    chapter=point.chapter,
                    order_index=point.order_index,
                    status=status,
                    score=score,
                    evidence_count=evidence_count,
                    confidence=confidence,
                    last_assessed_at=(
                        last_assessed_at.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                        if last_assessed_at is not None
                        else None
                    ),
                    prerequisite_ids=cls._safe_prerequisite_ids(point.prerequisites_json),
                    weakness_item_ids=[str(item.id) for item in point_weaknesses if item.status != "dismissed"],
                    recommended_resource_ids=[str(resource.id) for resource in resources_by_point.get(point.id, [])[:3]],
                )
            )
        return points

    @staticmethod
    def _mastery_measure(
        weaknesses: list[WeaknessReviewItem],
        tasks: list[LearningTask],
        now: datetime,
        practice_answers: list[PracticeAnswer] | None = None,
    ) -> tuple[str, int | None, int, float, datetime | None]:
        answered = [
            answer
            for answer in practice_answers or []
            if answer.answer_text is not None and (answer.feedback_json or {}).get("score") is not None
        ]
        active_weaknesses = [item for item in weaknesses if item.status in {"confirmed", "reviewing"}]
        completed_weaknesses = [item for item in weaknesses if item.status == "completed"]
        evidence_count = len(answered) + len(active_weaknesses) + len(completed_weaknesses)
        timestamps = [
            value
            for value in [
                *(getattr(answer, "created_at", None) for answer in answered),
                *(getattr(item, "updated_at", None) for item in weaknesses),
            ]
            if value is not None
        ]
        last_assessed_at = max(timestamps) if timestamps else None
        confidence = min(0.95, 0.55 + max(0, evidence_count - 1) * 0.08) if evidence_count else 0.0

        if answered:
            score = round(sum(CourseService._practice_answer_score(answer) for answer in answered) / len(answered))
            if active_weaknesses or score < 60:
                return "weak", min(score, 59), evidence_count, confidence, last_assessed_at
            if any(item.next_review_at is not None and item.next_review_at <= now for item in completed_weaknesses):
                return "recommended_review", score, evidence_count, confidence, last_assessed_at
            return ("mastered" if score >= 80 else "learning"), score, evidence_count, confidence, last_assessed_at
        if active_weaknesses:
            return "weak", 35, evidence_count, confidence, last_assessed_at
        if any(item.next_review_at is not None and item.next_review_at <= now for item in completed_weaknesses):
            return "recommended_review", 55, evidence_count, confidence, last_assessed_at
        if completed_weaknesses:
            return "learning", 65, evidence_count, confidence, last_assessed_at
        return "not_started", None, 0, 0.0, None

    @staticmethod
    def _build_mastery_summary(points: list[CourseMasteryPoint]) -> CourseMasterySummary:
        assessed_scores = [point.score for point in points if point.score is not None]
        return CourseMasterySummary(
            total_count=len(points),
            weak_count=sum(1 for point in points if point.status == "weak"),
            learning_count=sum(1 for point in points if point.status == "learning"),
            mastered_count=sum(1 for point in points if point.status == "mastered"),
            recommended_review_count=sum(1 for point in points if point.status == "recommended_review"),
            not_started_count=sum(1 for point in points if point.status == "not_started"),
            assessed_count=len(assessed_scores),
            unassessed_count=sum(1 for point in points if point.score is None),
            average_score=round(sum(assessed_scores) / len(assessed_scores)) if assessed_scores else None,
        )

    @classmethod
    def _sync_weakness_resource_recommendations(
        cls,
        review_items: list[WeaknessReviewItem],
        resources: list[GeneratedResource],
    ) -> bool:
        changed = False
        for item in review_items:
            if item.status in {"confirmed", "reviewing", "completed"}:
                recommended_ids = cls._recommend_resource_ids(resources, item.knowledge_point_id, item.title)
                if item.recommended_resource_ids != recommended_ids:
                    item.recommended_resource_ids = recommended_ids
                    changed = True
                if item.next_review_at is None:
                    item.next_review_at = datetime.now(UTC) + timedelta(days=3)
                    changed = True
        return changed

    @classmethod
    def _recommend_resource_ids(cls, resources: list[GeneratedResource], knowledge_point_id: int | None, title: str) -> list[int]:
        normalized_title = cls._normalize_weakness_title(title)
        matched: list[GeneratedResource] = []
        if knowledge_point_id is not None:
            matched.extend([resource for resource in resources if resource.knowledge_point_id == knowledge_point_id])
            if matched:
                return [resource.id for resource in matched[:3]]
        if len(matched) < 3 and normalized_title:
            matched.extend(
                [
                    resource
                    for resource in resources
                    if resource not in matched and normalized_title in cls._normalize_weakness_title(resource.title)
                ]
            )
        return [resource.id for resource in matched[:3]]

    @staticmethod
    def _safe_prerequisite_ids(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            try:
                result.append(str(int(item)))
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _safe_title(value: object) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())[:120]

    @staticmethod
    def _safe_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _practice_answer_score(answer: PracticeAnswer) -> int:
        try:
            return int((answer.feedback_json or {})["score"])
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_weakness_title(cls, value: str) -> str:
        return cls._safe_title(value).casefold()

    def _build_summary(
        self,
        course: Course,
        material_count: int | None = None,
        knowledge_point_count: int | None = None,
        chunk_count: int | None = None,
    ) -> CourseSummary:
        if material_count is None:
            material_count = len(self.repository.list_course_materials(course.id))
        if knowledge_point_count is None:
            knowledge_point_count = len(self.repository.list_knowledge_points(course.id))
        if chunk_count is None:
            chunk_count = len(self.repository.list_knowledge_chunks(course.id))

        return CourseSummary(
            id=str(course.id),
            title=course.title,
            description=course.description,
            subject=course.subject,
            source_type=course.source_type or "uploaded",
            status=course.status or "draft",
            agent_trace_id=getattr(course, "agent_trace_id", None),
            progress_percent=0,
            material_count=material_count,
            knowledge_point_count=knowledge_point_count,
            chunk_count=chunk_count,
        )

    @staticmethod
    def _build_knowledge_point(point: KnowledgePoint) -> CourseKnowledgePoint:
        return CourseKnowledgePoint(
            id=str(point.id),
            title=point.title,
            summary=point.summary,
            chapter=point.chapter,
            order_index=point.order_index,
            difficulty=point.difficulty,
            prerequisite_ids=[str(item) for item in (point.prerequisites_json or [])],
        )

    @classmethod
    def _split_text(cls, text: str) -> list[str]:
        if len(text) <= cls.chunk_size:
            return [text]
        return [text[index : index + cls.chunk_size] for index in range(0, len(text), cls.chunk_size)]

    @staticmethod
    def _summary(text: str) -> str:
        cleaned = CourseService._clean_text(text)
        return cleaned[:120]

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _extension(filename: str) -> str:
        return Path(filename).suffix.lower()
