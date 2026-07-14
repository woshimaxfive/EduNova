from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.data.builtin_courses.data_structures import BUILTIN_DATA_STRUCTURES_COURSE
from backend.app.models import (
    AgentRunLog,
    AiJob,
    Course,
    CourseMaterial,
    ExportJob,
    KnowledgeChunk,
    KnowledgePoint,
    Material,
    ModelCallRun,
    User,
)


SYSTEM_ACCOUNT = "system"
LEGACY_COURSE_SLUG = "ai-intro"
BUILTIN_COURSE_SLUG = "data-structures-c-python"
BUILTIN_POINT_KEY_ALIASES = {
    "balanced-multiway-trees": "balanced-binary-tree",
}
LEGACY_KNOWLEDGE_POINT_TITLES = {
    "人工智能概述",
    "搜索问题与状态空间",
    "启发式搜索",
    "知识表示",
    "机器学习基础",
    "监督学习",
    "神经网络",
    "反向传播",
    "自然语言处理",
    "计算机视觉",
    "智能体与多智能体",
    "AI 伦理与安全",
}


@dataclass(frozen=True)
class CourseSeedResult:
    created: bool
    course_id: int | None
    course_title: str
    knowledge_points: int
    chunks: int
    materials: int


@dataclass(frozen=True)
class BuiltinCourseSyncResult:
    removed_legacy_courses: int
    removed_legacy_materials: int
    migrated_users: int
    created_courses: int
    existing_courses: int


def _lab_content(lab: dict[str, Any]) -> str:
    return "\n".join(
        (
            lab["objective"],
            "",
            "```python",
            lab["code"].rstrip(),
            "```",
            "",
            f"预期输出：`{lab['expected_output']}`",
            f"边界检查：{lab['edge_case']}",
        )
    )


def _course_structure(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "learning_objectives": [
            objective
            for chapter in package["chapters"]
            for objective in chapter["learning_objectives"]
        ],
        "chapters": [
            {
                "key": chapter["key"],
                "title": chapter["title"],
                "order": chapter["order"],
                "knowledge_point_keys": [point["key"] for point in chapter["knowledge_points"]],
                "knowledge_points": [
                    {
                        "key": point["key"],
                        "title": point["title"],
                        "learning_objective": point["learning_objective"],
                        "complexity": point["complexity"],
                        "check_question": point["check_question"],
                    }
                    for point in chapter["knowledge_points"]
                ],
            }
            for chapter in package["chapters"]
        ],
        "supplemental_refs": package["bibliography"],
        "generation_mode": package["generation_mode"],
        "review_result": {
            "status": "passed",
            "mode": "handcrafted_validation",
            "knowledge_point_count": len(package["knowledge_points"]),
            "chunk_count": package["expected_counts"]["chunks"],
            "lab_count": len(package["labs"]),
            "retrieval_benchmark_count": len(package["quality_benchmarks"]["retrieval_cases"]),
        },
        "package_version": package["version"],
        "course_slug": package["slug"],
    }


def build_builtin_data_structures_course_graph(
    owner_user: User,
    package: dict[str, Any] = BUILTIN_DATA_STRUCTURES_COURSE,
) -> Course:
    course = Course(
        owner=owner_user,
        title=package["title"],
        description=package["description"],
        subject=package["subject"],
        source_type=package["source_type"],
        visibility=package["visibility"],
        status=package["status"],
        structure_json=_course_structure(package),
    )

    material_by_key: dict[str, CourseMaterial] = {}
    for material_data in package["materials"]:
        material = CourseMaterial(
            user=owner_user,
            course=course,
            filename=material_data["filename"],
            content_type=material_data["content_type"],
            storage_path=material_data["storage_path"],
            parse_status=material_data["parse_status"],
            extracted_text=material_data["extracted_text"],
            metadata_json={
                **material_data["metadata_json"],
                "package_version": package["version"],
                "owner_scope": "registered_user",
            },
        )
        material_by_key[material_data["key"]] = material

    point_by_key: dict[str, KnowledgePoint] = {}
    for point_data in package["knowledge_points"]:
        point = KnowledgePoint(
            course=course,
            title=point_data["title"],
            summary=point_data["summary"],
            chapter=point_data["chapter"],
            order_index=point_data["order_index"],
            difficulty=point_data["difficulty"],
            prerequisites_json=list(point_data["prerequisites"]),
        )
        point.builtin_key = point_data["key"]
        point.builtin_prerequisite_keys = list(point_data["prerequisites"])
        point_by_key[point_data["key"]] = point
        material = material_by_key[point_data["material_key"]]
        for section in point_data["sections"]:
            KnowledgeChunk(
                course=course,
                material=material,
                knowledge_point=point,
                content=section["content"],
                page_number=None,
                section_title=section["title"],
                embedding=None,
                metadata_json={
                    "course_slug": package["slug"],
                    "package_version": package["version"],
                    "knowledge_key": point_data["key"],
                    "section_kind": section["kind"],
                    "source": "builtin_seed",
                    "source_locator": f"{point_data['chapter']} / {point_data['title']} / {section['title']}",
                },
            )

    lab_material = material_by_key["python-labs"]
    for lab in package["labs"]:
        point = point_by_key[lab["knowledge_point_key"]]
        KnowledgeChunk(
            course=course,
            material=lab_material,
            knowledge_point=point,
            content=_lab_content(lab),
            page_number=None,
            section_title=lab["title"],
            embedding=None,
            metadata_json={
                "course_slug": package["slug"],
                "package_version": package["version"],
                "knowledge_key": lab["knowledge_point_key"],
                "section_kind": "python_lab",
                "lab_id": lab["id"],
                "source": "builtin_seed",
                "source_locator": f"Python 算法实验与常见错误 / {lab['title']}",
            },
        )
    return course


def finalize_builtin_course_graph(course: Course) -> None:
    point_by_key = {
        str(getattr(point, "builtin_key", "")): point
        for point in course.knowledge_points
        if getattr(point, "builtin_key", None)
    }
    if len(point_by_key) != len(course.knowledge_points):
        raise ValueError("内置课程知识点 key 未完整保留。")
    for point in course.knowledge_points:
        prerequisite_keys = list(getattr(point, "builtin_prerequisite_keys", []))
        point.prerequisites_json = [
            point_by_key[key].id
            for key in prerequisite_keys
            if key in point_by_key and point_by_key[key].id is not None
        ]


def _course_has_slug(course: Course, slug: str) -> bool:
    return (course.structure_json or {}).get("course_slug") == slug or any(
        (material.metadata_json or {}).get("course_slug") == slug
        for material in course.materials
    )


def _is_legacy_builtin_course(course: Course) -> bool:
    if course.source_type != "builtin":
        return False
    if (
        course.owner_id is None
        and course.owner is None
        and _course_has_slug(course, BUILTIN_COURSE_SLUG)
    ):
        return True
    if _course_has_slug(course, LEGACY_COURSE_SLUG):
        return True
    if any(
        (material.metadata_json or {}).get("source") in {"builtin_seed", "starter_copy"}
        and (material.metadata_json or {}).get("course_slug") != BUILTIN_COURSE_SLUG
        for material in course.materials
    ):
        return True
    return (
        course.owner_id is None
        and not course.materials
        and not (course.structure_json or {})
        and {point.title for point in course.knowledge_points} == LEGACY_KNOWLEDGE_POINT_TITLES
    )


def _find_course_for_user(db: Session, user_id: int, slug: str) -> Course | None:
    courses = list(
        db.scalars(
            select(Course).where(Course.owner_id == user_id, Course.source_type == "builtin")
        )
    )
    return next((course for course in courses if _course_has_slug(course, slug)), None)


def _material_package_key(material: CourseMaterial) -> str | None:
    metadata = material.metadata_json or {}
    if metadata.get("material_kind") == "lab":
        return "python-labs"
    chapter_key = metadata.get("chapter_key")
    return str(chapter_key) if chapter_key else None


def _point_package_key(point: KnowledgePoint) -> str | None:
    for chunk in point.knowledge_chunks:
        key = (chunk.metadata_json or {}).get("knowledge_key")
        if key:
            return BUILTIN_POINT_KEY_ALIASES.get(str(key), str(key))
    return None


def refresh_builtin_data_structures_course(
    db: Session,
    course: Course,
    package: dict[str, Any] = BUILTIN_DATA_STRUCTURES_COURSE,
) -> None:
    expected = package["expected_counts"]
    package_is_current = (course.structure_json or {}).get("package_version") == package["version"]
    package_shape_is_current = (
        len(course.materials) == expected["materials"]
        and len(course.knowledge_points) == expected["knowledge_points"]
        and len(course.knowledge_chunks) == expected["chunks"]
    )
    if package_is_current and package_shape_is_current:
        return

    course.title = package["title"]
    course.description = package["description"]
    course.subject = package["subject"]
    course.source_type = package["source_type"]
    course.visibility = package["visibility"]
    course.status = package["status"]
    course.structure_json = _course_structure(package)

    material_by_key = {
        key: material
        for material in course.materials
        if (key := _material_package_key(material)) is not None
    }
    for material_data in package["materials"]:
        material = material_by_key.get(material_data["key"])
        if material is None:
            material = CourseMaterial(user=course.owner, course=course)
            db.add(material)
            material_by_key[material_data["key"]] = material
        material.filename = material_data["filename"]
        material.content_type = material_data["content_type"]
        material.storage_path = material_data["storage_path"]
        material.parse_status = material_data["parse_status"]
        material.extracted_text = material_data["extracted_text"]
        material.metadata_json = {
            **material_data["metadata_json"],
            "package_version": package["version"],
            "owner_scope": "registered_user",
        }

    point_by_key = {
        key: point
        for point in course.knowledge_points
        if (key := _point_package_key(point)) is not None
    }
    for point_data in package["knowledge_points"]:
        point = point_by_key.get(point_data["key"])
        if point is None:
            point = KnowledgePoint(course=course)
            db.add(point)
            point_by_key[point_data["key"]] = point
        point.title = point_data["title"]
        point.summary = point_data["summary"]
        point.chapter = point_data["chapter"]
        point.order_index = point_data["order_index"]
        point.difficulty = point_data["difficulty"]
        point.builtin_key = point_data["key"]
        point.builtin_prerequisite_keys = list(point_data["prerequisites"])

    db.flush()
    finalize_builtin_course_graph(course)

    chunk_by_identity: dict[tuple[str, ...], KnowledgeChunk] = {}
    for chunk in course.knowledge_chunks:
        metadata = chunk.metadata_json or {}
        key = metadata.get("knowledge_key")
        if key:
            key = BUILTIN_POINT_KEY_ALIASES.get(str(key), str(key))
        lab_id = metadata.get("lab_id")
        section_kind = metadata.get("section_kind")
        if lab_id:
            chunk_by_identity[("lab", str(lab_id))] = chunk
        elif key and section_kind:
            chunk_by_identity[("point", str(key), str(section_kind))] = chunk

    used_chunk_ids: set[int] = set()
    for point_data in package["knowledge_points"]:
        point = point_by_key[point_data["key"]]
        material = material_by_key[point_data["material_key"]]
        for section in point_data["sections"]:
            identity = ("point", point_data["key"], section["kind"])
            chunk = chunk_by_identity.get(identity)
            if chunk is None:
                chunk = KnowledgeChunk(course=course, material=material, knowledge_point=point)
                db.add(chunk)
            chunk.material = material
            chunk.knowledge_point = point
            chunk.content = section["content"]
            chunk.page_number = None
            chunk.section_title = section["title"]
            chunk.embedding = None
            chunk.embedding_provider = None
            chunk.embedding_model = None
            chunk.embedding_dimension = None
            chunk.embedding_profile_hash = None
            chunk.embedding_updated_at = None
            chunk.metadata_json = {
                "course_slug": package["slug"],
                "package_version": package["version"],
                "knowledge_key": point_data["key"],
                "section_kind": section["kind"],
                "source": "builtin_seed",
                "source_locator": f"{point_data['chapter']} / {point_data['title']} / {section['title']}",
            }
            if chunk.id is not None:
                used_chunk_ids.add(chunk.id)

    lab_material = material_by_key["python-labs"]
    for lab in package["labs"]:
        identity = ("lab", lab["id"])
        point = point_by_key[lab["knowledge_point_key"]]
        chunk = chunk_by_identity.get(identity)
        if chunk is None:
            chunk = KnowledgeChunk(course=course, material=lab_material, knowledge_point=point)
            db.add(chunk)
        chunk.material = lab_material
        chunk.knowledge_point = point
        chunk.content = _lab_content(lab)
        chunk.page_number = None
        chunk.section_title = lab["title"]
        chunk.embedding = None
        chunk.embedding_provider = None
        chunk.embedding_model = None
        chunk.embedding_dimension = None
        chunk.embedding_profile_hash = None
        chunk.embedding_updated_at = None
        chunk.metadata_json = {
            "course_slug": package["slug"],
            "package_version": package["version"],
            "knowledge_key": lab["knowledge_point_key"],
            "section_kind": "python_lab",
            "lab_id": lab["id"],
            "source": "builtin_seed",
            "source_locator": f"Python 算法实验与常见错误 / {lab['title']}",
        }
        if chunk.id is not None:
            used_chunk_ids.add(chunk.id)

    for chunk in list(course.knowledge_chunks):
        if chunk.id is not None and chunk.id not in used_chunk_ids:
            db.delete(chunk)

    valid_point_keys = {point["key"] for point in package["knowledge_points"]}
    for point in list(course.knowledge_points):
        key = _point_package_key(point)
        if key is not None and key not in valid_point_keys:
            db.delete(point)

    db.flush()


def install_builtin_data_structures_course(db: Session, user: User) -> CourseSeedResult:
    existing = _find_course_for_user(db, user.id, BUILTIN_COURSE_SLUG)
    package = BUILTIN_DATA_STRUCTURES_COURSE
    if existing is not None:
        refresh_builtin_data_structures_course(db, existing, package)
        return CourseSeedResult(
            created=False,
            course_id=existing.id,
            course_title=existing.title,
            knowledge_points=package["expected_counts"]["knowledge_points"],
            chunks=package["expected_counts"]["chunks"],
            materials=package["expected_counts"]["materials"],
        )

    course = build_builtin_data_structures_course_graph(user, package)
    db.add(course)
    db.flush()
    finalize_builtin_course_graph(course)
    db.flush()
    return CourseSeedResult(
        created=True,
        course_id=course.id,
        course_title=course.title,
        knowledge_points=len(course.knowledge_points),
        chunks=len(course.knowledge_chunks),
        materials=len(course.materials),
    )


def _safe_delete_export_files(paths: list[str]) -> None:
    root = Path(get_settings().export_dir).resolve()
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        else:
            path = path.resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.is_file():
            path.unlink()


def sync_builtin_courses(db: Session) -> BuiltinCourseSyncResult:
    builtin_courses = list(db.scalars(select(Course).where(Course.source_type == "builtin")))
    legacy_courses = [course for course in builtin_courses if _is_legacy_builtin_course(course)]
    legacy_course_ids = [course.id for course in legacy_courses if course.id is not None]
    affected_user_ids = {
        course.owner_id
        for course in legacy_courses
        if course.owner_id is not None and (course.owner is None or course.owner.account != SYSTEM_ACCOUNT)
    }

    export_paths: list[str] = []
    if legacy_course_ids:
        export_paths = [
            value
            for value in db.scalars(
                select(ExportJob.file_path).where(
                    ExportJob.course_id.in_(legacy_course_ids),
                    ExportJob.file_path.is_not(None),
                )
            )
            if value
        ]
        trace_ids = set(
            value
            for value in db.scalars(
                select(AgentRunLog.trace_id).where(AgentRunLog.course_id.in_(legacy_course_ids))
            )
            if value
        )
        ai_jobs = list(db.scalars(select(AiJob).where(AiJob.course_id.in_(legacy_course_ids))))
        trace_ids.update(job.agent_trace_id for job in ai_jobs if job.agent_trace_id)
        ai_job_ids = [job.id for job in ai_jobs if job.id is not None]
        model_call_filters = []
        if trace_ids:
            model_call_filters.append(ModelCallRun.trace_id.in_(trace_ids))
        if ai_job_ids:
            model_call_filters.append(ModelCallRun.ai_job_id.in_(ai_job_ids))
        for condition in model_call_filters:
            db.execute(delete(ModelCallRun).where(condition))
        db.execute(delete(AgentRunLog).where(AgentRunLog.course_id.in_(legacy_course_ids)))
        db.execute(delete(AiJob).where(AiJob.course_id.in_(legacy_course_ids)))
        for course in legacy_courses:
            db.delete(course)

    legacy_materials = [
        material
        for material in db.scalars(select(Material))
        if (material.metadata_json or {}).get("course_slug") == LEGACY_COURSE_SLUG
        and (material.metadata_json or {}).get("owner_scope") == "registered_user"
    ]
    for material in legacy_materials:
        db.delete(material)

    users = list(db.scalars(select(User).where(User.role == "student")))
    migrated_users = 0
    for user in users:
        if user.starter_mode == "ai_intro" or user.id in affected_user_ids:
            user.starter_mode = "data_structures"
            migrated_users += 1

    db.flush()
    created_courses = 0
    existing_courses = 0
    for user in users:
        if user.starter_mode != "data_structures":
            continue
        result = install_builtin_data_structures_course(db, user)
        if result.created:
            created_courses += 1
        else:
            existing_courses += 1

    db.commit()
    _safe_delete_export_files(export_paths)
    return BuiltinCourseSyncResult(
        removed_legacy_courses=len(legacy_courses),
        removed_legacy_materials=len(legacy_materials),
        migrated_users=migrated_users,
        created_courses=created_courses,
        existing_courses=existing_courses,
    )
