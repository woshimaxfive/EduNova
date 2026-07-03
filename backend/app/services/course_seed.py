from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data.builtin_courses.ai_intro import BUILTIN_AI_INTRO_COURSE
from backend.app.models import Course, CourseMaterial, KnowledgeChunk, KnowledgePoint, User


SYSTEM_USER_EMAIL = "system@edunova.local"
SYSTEM_USER_DISPLAY_NAME = "EduNova 系统"
SYSTEM_USER_PASSWORD_MARKER = "not-login-account"


@dataclass(frozen=True)
class CourseSeedResult:
    created: bool
    course_id: int | None
    course_title: str
    knowledge_points: int
    chunks: int
    materials: int


def _package_counts(package: dict = BUILTIN_AI_INTRO_COURSE) -> tuple[int, int]:
    knowledge_points = len(package["knowledge_points"])
    chunks = sum(len(point["chunks"]) for point in package["knowledge_points"])
    return knowledge_points, chunks


def _build_extracted_text(package: dict = BUILTIN_AI_INTRO_COURSE) -> str:
    sections: list[str] = []
    for point in package["knowledge_points"]:
        sections.append(f"## {point['title']}")
        sections.append(point["summary"])
        for chunk in point["chunks"]:
            sections.append(f"### {chunk['section_title']}")
            sections.append(chunk["content"])
    return "\n\n".join(sections)


def build_builtin_ai_intro_course_graph(
    owner_user: User,
    package: dict = BUILTIN_AI_INTRO_COURSE,
) -> Course:
    course = Course(
        owner=owner_user,
        title=package["title"],
        description=package["description"],
        subject=package["subject"],
        source_type=package["source_type"],
        visibility=package["visibility"],
        status=package["status"],
    )
    material_data = package["material"]
    material = CourseMaterial(
        user=owner_user,
        course=course,
        filename=material_data["filename"],
        content_type=material_data["content_type"],
        storage_path=material_data["storage_path"],
        parse_status=material_data["parse_status"],
        extracted_text=_build_extracted_text(package),
        metadata_json=material_data["metadata_json"],
    )

    for index, point_data in enumerate(package["knowledge_points"], start=1):
        point = KnowledgePoint(
            course=course,
            title=point_data["title"],
            summary=point_data["summary"],
            chapter=point_data["chapter"],
            order_index=index,
            difficulty=point_data["difficulty"],
            prerequisites_json=point_data["prerequisites"],
        )
        for chunk_data in point_data["chunks"]:
            KnowledgeChunk(
                course=course,
                material=material,
                knowledge_point=point,
                content=chunk_data["content"],
                page_number=chunk_data["page_number"],
                section_title=chunk_data["section_title"],
                embedding=None,
                metadata_json={
                    "course_slug": package["slug"],
                    "knowledge_key": point_data["key"],
                    "source": "builtin_seed",
                },
            )

    return course


def _get_or_create_system_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == SYSTEM_USER_EMAIL))
    if user is not None:
        return user

    user = User(
        email=SYSTEM_USER_EMAIL,
        hashed_password=SYSTEM_USER_PASSWORD_MARKER,
        display_name=SYSTEM_USER_DISPLAY_NAME,
        role="admin",
    )
    db.add(user)
    return user


def seed_builtin_ai_intro_course(
    db: Session,
    package: dict = BUILTIN_AI_INTRO_COURSE,
) -> CourseSeedResult:
    existing_course = db.scalar(
        select(Course).where(
            Course.title == package["title"],
            Course.source_type == package["source_type"],
        )
    )
    knowledge_points, chunks = _package_counts(package)

    if existing_course is not None:
        return CourseSeedResult(
            created=False,
            course_id=existing_course.id,
            course_title=existing_course.title,
            knowledge_points=knowledge_points,
            chunks=chunks,
            materials=1,
        )

    system_user = _get_or_create_system_user(db)
    course = build_builtin_ai_intro_course_graph(system_user, package)
    db.add(course)
    db.flush()

    return CourseSeedResult(
        created=True,
        course_id=course.id,
        course_title=course.title,
        knowledge_points=knowledge_points,
        chunks=chunks,
        materials=1,
    )
