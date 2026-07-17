from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import (
    ChatSession,
    Course,
    CourseEnrollment,
    GeneratedResource,
    KnowledgePoint,
    Material,
    PracticeAnswer,
    PracticeSession,
    StudentProfile,
    User,
)
from backend.app.schemas.dashboard import (
    DashboardConversation,
    DashboardCourse,
    DashboardMaterial,
    DashboardResource,
    DashboardSummary,
    EmptyState,
    EvidenceSummary,
    MaterialLibrarySummary,
    ProfileSummary,
)


class DashboardRepository(Protocol):
    def get_profile(self, user_id: int) -> StudentProfile | None: ...

    def list_recent_courses(self, user_id: int, limit: int) -> list[Course]: ...

    def list_course_enrollments(self, user_id: int, course_ids: list[int]) -> list[CourseEnrollment]: ...

    def list_recent_materials(self, user_id: int, limit: int) -> list[Material]: ...

    def count_materials(self, user_id: int) -> int: ...

    def count_unassigned_materials(self, user_id: int) -> int: ...

    def list_recent_home_conversations(self, user_id: int, limit: int) -> list[ChatSession]: ...

    def list_recent_resources(self, user_id: int, limit: int) -> list[GeneratedResource]: ...

    def knowledge_point_counts(self, course_ids: list[int]) -> dict[int, int]: ...

    def practiced_knowledge_point_ids(self, user_id: int, course_ids: list[int]) -> dict[int, set[int]]: ...

    def latest_practice_times(self, user_id: int, course_ids: list[int]) -> dict[int, datetime]: ...


class SqlAlchemyDashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def list_recent_courses(self, user_id: int, limit: int) -> list[Course]:
        return list(
            self.db.scalars(
                select(Course)
                .where(Course.owner_id == user_id)
                .order_by(Course.updated_at.desc(), Course.id.desc())
                .limit(limit)
            )
        )

    def list_course_enrollments(self, user_id: int, course_ids: list[int]) -> list[CourseEnrollment]:
        if not course_ids:
            return []

        return list(
            self.db.scalars(
                select(CourseEnrollment).where(
                    CourseEnrollment.user_id == user_id,
                    CourseEnrollment.course_id.in_(course_ids),
                )
            )
        )

    def list_recent_materials(self, user_id: int, limit: int) -> list[Material]:
        return list(
            self.db.scalars(
                select(Material)
                .where(Material.user_id == user_id)
                .order_by(Material.created_at.desc(), Material.id.desc())
                .limit(limit)
            )
        )

    def count_materials(self, user_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(Material).where(Material.user_id == user_id)
            )
            or 0
        )

    def count_unassigned_materials(self, user_id: int) -> int:
        from backend.app.models import CourseMaterialLink

        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Material)
                .where(
                    Material.user_id == user_id,
                    ~select(CourseMaterialLink.id)
                    .where(CourseMaterialLink.material_id == Material.id)
                    .exists(),
                )
            )
            or 0
        )

    def list_recent_home_conversations(self, user_id: int, limit: int) -> list[ChatSession]:
        return list(
            self.db.scalars(
                select(ChatSession)
                .where(
                    ChatSession.user_id == user_id,
                    ChatSession.scope == "home",
                    ChatSession.archived_from_home.is_(False),
                )
                .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
                .limit(limit)
            )
        )

    def list_recent_resources(self, user_id: int, limit: int) -> list[GeneratedResource]:
        return list(
            self.db.scalars(
                select(GeneratedResource)
                .where(GeneratedResource.user_id == user_id)
                .order_by(GeneratedResource.updated_at.desc(), GeneratedResource.id.desc())
                .limit(limit)
            )
        )

    def knowledge_point_counts(self, course_ids: list[int]) -> dict[int, int]:
        if not course_ids:
            return {}
        rows = (
            self.db.execute(
                select(KnowledgePoint.course_id, func.count(KnowledgePoint.id))
                .where(KnowledgePoint.course_id.in_(course_ids))
                .group_by(KnowledgePoint.course_id)
            )
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def practiced_knowledge_point_ids(self, user_id: int, course_ids: list[int]) -> dict[int, set[int]]:
        if not course_ids:
            return {}
        rows = (
            self.db.execute(
                select(PracticeAnswer.question_json["knowledge_point_id"].as_integer(), PracticeSession.course_id)
                .join(PracticeSession, PracticeSession.id == PracticeAnswer.session_id)
                .where(PracticeAnswer.user_id == user_id, PracticeSession.course_id.in_(course_ids))
                .distinct()
            )
            .all()
        )
        result: dict[int, set[int]] = {cid: set() for cid in course_ids}
        for kp_id, course_id in rows:
            if kp_id is not None:
                result.setdefault(course_id, set()).add(kp_id)
        return result

    def latest_practice_times(self, user_id: int, course_ids: list[int]) -> dict[int, datetime]:
        if not course_ids:
            return {}
        rows = (
            self.db.execute(
                select(PracticeSession.course_id, func.max(PracticeSession.created_at))
                .where(PracticeSession.user_id == user_id, PracticeSession.course_id.in_(course_ids))
                .group_by(PracticeSession.course_id)
            )
            .all()
        )
        return {row[0]: row[1] for row in rows}


class DashboardService:
    def __init__(self, repository: DashboardRepository, now: datetime | None = None) -> None:
        self.repository = repository
        self.now = now

    def build_summary(self, user: User) -> DashboardSummary:
        profile = self.repository.get_profile(user.id)
        courses = self.repository.list_recent_courses(user.id, limit=3)
        if not courses:
            course_ids: list[int] = []
        else:
            course_ids = [course.id for course in courses]
        enrollments = self.repository.list_course_enrollments(user.id, course_ids)
        materials = self.repository.list_recent_materials(user.id, limit=5)
        conversations = self.repository.list_recent_home_conversations(user.id, limit=12)
        resources = self.repository.list_recent_resources(user.id, limit=3)

        kp_counts = self.repository.knowledge_point_counts(course_ids)
        practiced = self.repository.practiced_knowledge_point_ids(user.id, course_ids)
        latest_times = self.repository.latest_practice_times(user.id, course_ids)

        sorted_courses = sorted(
            courses,
            key=lambda c: (latest_times.get(c.id) or c.updated_at),
            reverse=True,
        )
        recent_courses = self._build_courses(sorted_courses, enrollments, kp_counts, practiced)
        recent_materials = [self._build_material(material) for material in materials]
        recent_resources = [self._build_resource(resource) for resource in resources]

        return DashboardSummary(
            profile_summary=self._build_profile(user, profile),
            recent_conversations=[
                DashboardConversation(
                    id=str(conversation.id),
                    title=conversation.title,
                    meta=self._relative_label(conversation.updated_at),
                    scope="home",
                    updated_at=self._iso_timestamp(conversation.updated_at),
                )
                for conversation in conversations
            ],
            recent_courses=recent_courses,
            material_library_summary=MaterialLibrarySummary(
                material_count=self.repository.count_materials(user.id),
                unassigned_count=self.repository.count_unassigned_materials(user.id),
            ),
            recent_materials=recent_materials,
            recent_resources=recent_resources,
            command_suggestions=self._build_command_suggestions(user, recent_courses, recent_materials),
            evidence_summary=self._build_evidence_summary(resources),
            empty_state=self._build_empty_state(user, recent_courses, conversations, recent_resources, profile),
        )

    @staticmethod
    def _build_profile(user: User, profile: StudentProfile | None) -> ProfileSummary:
        profile_json = profile.profile_json if profile is not None else {}
        return ProfileSummary(
            display_name=user.display_name,
            starter_mode=user.starter_mode,
            has_profile=profile is not None,
            knowledge_foundation=profile_json.get("knowledge_foundation"),
            learning_goal=profile_json.get("learning_goal"),
        )

    @staticmethod
    def _build_courses(
        courses: list[Course],
        enrollments: list[CourseEnrollment],
        kp_counts: dict[int, int],
        practiced: dict[int, set[int]],
    ) -> list[DashboardCourse]:
        result: list[DashboardCourse] = []

        for course in courses:
            total_kps = kp_counts.get(course.id, 0)
            practiced_kps = practiced.get(course.id, set())
            if total_kps > 0:
                progress_pct = round(len(practiced_kps) / total_kps * 100)
            else:
                progress_pct = 0
            progress = Decimal(progress_pct)

            focus = course.subject or course.description or "等待生成学习重点"
            if practiced_kps:
                focus = f"{course.subject or '课程'} · 已练习 {len(practiced_kps)}/{total_kps} 个知识点"

            result.append(
                DashboardCourse(
                    id=str(course.id),
                    title=course.title,
                    source_type=course.source_type,
                    progress_label=DashboardService._progress_label(progress),
                    practiced_knowledge_point_count=len(practiced_kps),
                    knowledge_point_count=total_kps,
                    focus=focus,
                    next="继续学习" if progress > 0 else "开始学习",
                )
            )

        return result

    @staticmethod
    def _progress_label(progress: Decimal) -> str:
        if progress <= 0:
            return "未开始"

        normalized = progress.quantize(Decimal("1")) if progress == progress.to_integral() else progress.normalize()
        return f"{normalized}%"

    def _build_material(self, material: Material) -> DashboardMaterial:
        metadata = material.metadata_json or {}
        return DashboardMaterial(
            id=str(material.id),
            title=material.filename,
            type=DashboardService._material_type(material),
            detail=DashboardService._parse_status_label(material.parse_status),
            modified=self._date_label(material.created_at),
            size=str(metadata.get("size_label") or metadata.get("size") or ""),
        )

    @staticmethod
    def _material_type(material: Material) -> str:
        extension = material.filename.rsplit(".", 1)[-1].upper() if "." in material.filename else ""
        if extension and len(extension) <= 5:
            return extension

        if "/" in material.content_type:
            return material.content_type.rsplit("/", 1)[-1].upper()[:5] or "FILE"

        return "FILE"

    @staticmethod
    def _parse_status_label(parse_status: str) -> str:
        labels = {
            "completed": "已解析",
            "uploaded": "等待解析",
            "pending": "等待解析",
            "parsing": "解析中",
            "failed": "解析失败",
        }
        return labels.get(parse_status, parse_status)

    @staticmethod
    def _build_resource(resource: GeneratedResource) -> DashboardResource:
        return DashboardResource(
            id=str(resource.id),
            title=resource.title,
            resource_type=resource.resource_type,
            status=resource.status,
            course_id=str(resource.course_id) if resource.course_id is not None else None,
            updated_at=DashboardService._iso_timestamp(resource.updated_at),
        )

    @staticmethod
    def _build_command_suggestions(
        user: User,
        courses: list[DashboardCourse],
        materials: list[DashboardMaterial],
    ) -> list[str]:
        if not courses and not materials:
            return ["上传第一份资料", "先和 EduNova 聊聊我的学习情况", "用资料生成一门课程"]

        suggestions: list[str] = []
        if courses:
            course_title = DashboardService._short_title(courses[0].title)
            suggestions.extend([f"继续学习《{course_title}》", f"帮我复习《{course_title}》的薄弱点"])
        if materials:
            material_title = DashboardService._short_title(materials[0].title)
            suggestions.append(f"根据《{material_title}》整理复习重点")
        if len(suggestions) < 3:
            suggestions.append("先帮我拆解下一步复习计划")
        return suggestions[:3]

    @staticmethod
    def _short_title(title: str, limit: int = 16) -> str:
        normalized = " ".join(title.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit]}…"

    @staticmethod
    def _build_evidence_summary(resources: list[GeneratedResource]) -> EvidenceSummary:
        citation_count = sum(len(resource.citation_json or []) for resource in resources)
        low_evidence_count = len(
            [
                resource
                for resource in resources
                if resource.confidence_score is not None and Decimal(resource.confidence_score) < Decimal("0.60")
            ]
        )
        return EvidenceSummary(
            citation_count=citation_count,
            latest_trace_id=None,
            low_evidence_count=low_evidence_count,
        )

    @staticmethod
    def _build_empty_state(
        user: User,
        courses: list[DashboardCourse],
        conversations: list[ChatSession],
        resources: list[DashboardResource],
        profile: StudentProfile | None,
    ) -> EmptyState:
        if not courses and not conversations and not resources and profile is None:
            return EmptyState(
                kind="blank",
                title="还没有课程",
                description="上传资料后可直接问，也可生成课程。",
                action_label="上传资料",
            )

        if (
            user.starter_mode == "data_structures"
            and courses
            and not conversations
            and not resources
            and profile is None
        ):
            return EmptyState(
                kind="starter",
                title="从数据结构与算法开始",
                description="内置课程已经进入你的学习空间，可以直接阅读课程内容或开始提问。",
                action_label="开始学习",
            )

        return EmptyState(
            kind="active",
            title="继续学习",
            description="从最近课程、资料或历史对话继续。",
            action_label="继续学习",
        )

    def _relative_label(self, value: datetime | None) -> str:
        if value is None:
            return "刚刚"

        current = self._current_time()
        comparable = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        delta = current - comparable

        if delta.total_seconds() < 3600:
            return "刚刚"
        if comparable.date() == current.date():
            return "今天"
        if (current.date() - comparable.date()).days == 1:
            return "昨天"
        return comparable.strftime("%m-%d")

    def _date_label(self, value: datetime | None) -> str:
        if value is None:
            return "今天"

        current = self._current_time()
        comparable = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if comparable.date() == current.date():
            return "今天"
        if (current.date() - comparable.date()).days == 1:
            return "昨天"
        return comparable.strftime("%m-%d")

    def _current_time(self) -> datetime:
        current = self.now or datetime.now(UTC)
        return current if current.tzinfo is not None else current.replace(tzinfo=UTC)

    @staticmethod
    def _iso_timestamp(value: datetime | None) -> str:
        timestamp = value or datetime.now(UTC)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
        return timestamp.isoformat().replace("+00:00", "Z")
