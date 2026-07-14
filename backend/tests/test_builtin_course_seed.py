from __future__ import annotations

import io
from contextlib import redirect_stdout
from difflib import SequenceMatcher
from backend.app.data.builtin_courses.data_structures import (
    BUILTIN_DATA_STRUCTURES_COURSE,
    PACKAGE_DIR,
)
from backend.app.models import Course, CourseMaterial, KnowledgeChunk, KnowledgePoint, User
from backend.app.services.course_seed import (
    LEGACY_KNOWLEDGE_POINT_TITLES,
    _is_legacy_builtin_course,
    build_builtin_data_structures_course_graph,
    finalize_builtin_course_graph,
    refresh_builtin_data_structures_course,
)
from backend.app.services.rag import RagService


EXPECTED_CHAPTERS = [
    "数据结构、抽象数据类型与复杂度",
    "线性表",
    "栈与队列",
    "串、数组与广义表",
    "树与二叉树",
    "图及图算法",
    "查找与散列表",
    "排序",
]


def test_builtin_data_structures_package_has_fixed_complete_shape() -> None:
    package = BUILTIN_DATA_STRUCTURES_COURSE

    assert package["title"] == "数据结构与算法"
    assert package["slug"] == "data-structures-c-python"
    assert package["source_type"] == "builtin"
    assert package["visibility"] == "private"
    assert [chapter["title"] for chapter in package["chapters"]] == EXPECTED_CHAPTERS
    assert len(package["materials"]) == 9
    assert len(package["knowledge_points"]) == 56
    assert len(package["labs"]) == 16
    assert sum(len(point["sections"]) for point in package["knowledge_points"]) == 168
    assert package["expected_counts"]["chunks"] == 184

    point_keys = {point["key"] for point in package["knowledge_points"]}
    assert len(point_keys) == 56
    assert all(point["difficulty"] in {"easy", "medium", "hard"} for point in package["knowledge_points"])
    assert all(
        prerequisite in point_keys
        for point in package["knowledge_points"]
        for prerequisite in point["prerequisites"]
    )
    assert all(
        [section["kind"] for section in point["sections"]] == ["concept", "process", "pitfall"]
        for point in package["knowledge_points"]
    )
    assert all(point["learning_objective"].strip() for point in package["knowledge_points"])
    assert all(point["complexity"].strip() for point in package["knowledge_points"])
    assert all(point["check_question"].endswith(("。", "？", "?")) for point in package["knowledge_points"])
    assert sum("```c" in point["process"]["content"] for point in package["knowledge_points"]) >= 16


def test_builtin_course_materials_are_internal_and_do_not_include_textbook_file() -> None:
    package = BUILTIN_DATA_STRUCTURES_COURSE
    material_text = "\n".join(material["extracted_text"] for material in package["materials"])
    package_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PACKAGE_DIR.rglob("*")
        if path.is_file()
    )

    assert all(material["storage_path"].startswith("builtin://") for material in package["materials"])
    assert all(material["metadata_json"]["library_visible"] is False for material in package["materials"])
    assert all(not material["filename"].lower().endswith(".pdf") for material in package["materials"])
    assert "C:\\Users\\computer" not in package_text
    assert "临时存放" not in package_text
    assert "f(n)" not in material_text
    assert "KMP" in material_text
    assert "Dijkstra" in material_text
    assert "拓扑排序" in material_text
    assert "散列表" in material_text


def test_all_builtin_python_labs_run_with_expected_output() -> None:
    for lab in BUILTIN_DATA_STRUCTURES_COURSE["labs"]:
        stdout = io.StringIO()
        namespace: dict[str, object] = {}
        with redirect_stdout(stdout):
            exec(compile(lab["code"], f"<{lab['id']}>", "exec"), namespace, namespace)

        assert stdout.getvalue().strip() == lab["expected_output"].strip(), lab["id"]
        assert lab["edge_case"].strip()

        verification_stdout = io.StringIO()
        with redirect_stdout(verification_stdout):
            exec(
                compile(lab["verification_code"], f"<{lab['id']}-verification>", "exec"),
                namespace,
                namespace,
            )
        assert verification_stdout.getvalue() == "", lab["id"]


def test_builtin_course_uses_point_specific_guidance_without_near_duplicates() -> None:
    points = BUILTIN_DATA_STRUCTURES_COURSE["knowledge_points"]
    objectives = [point["learning_objective"] for point in points]
    questions = [point["check_question"] for point in points]

    assert len(set(objectives)) == len(points)
    assert len(set(questions)) == len(points)
    assert all(28 <= len(value) <= 120 for value in objectives)
    assert all(20 <= len(value) <= 120 for value in questions)

    for values in (objectives, questions):
        for index, current in enumerate(values):
            for other in values[index + 1 :]:
                assert SequenceMatcher(None, current, other).ratio() < 0.82


def test_builtin_course_keyword_rag_quality_benchmarks_hit_expected_points() -> None:
    owner = User(
        id=9,
        account="rag_student",
        hashed_password="not-used",
        display_name="检索学习者",
        role="student",
        starter_mode="data_structures",
    )
    course = build_builtin_data_structures_course_graph(owner)
    cases = BUILTIN_DATA_STRUCTURES_COURSE["quality_benchmarks"]["retrieval_cases"]
    point_payloads = {
        point["key"]: " ".join(
            [
                point["summary"],
                point["learning_objective"],
                point["check_question"],
                *(section["content"] for section in point["sections"]),
            ]
        )
        for point in BUILTIN_DATA_STRUCTURES_COURSE["knowledge_points"]
    }

    for case in cases:
        query = case["query"].strip().lower()
        terms = RagService._query_terms(query)
        ranked = sorted(
            (
                (RagService._score_chunk(chunk, query, terms), chunk)
                for chunk in course.knowledge_chunks
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        top_keys: list[str] = []
        for score, chunk in ranked:
            key = str((chunk.metadata_json or {}).get("knowledge_key") or "")
            if score <= 0 or not key or key in top_keys:
                continue
            top_keys.append(key)
            if len(top_keys) == 3:
                break

        expected_key = case["expected_point_key"]
        assert expected_key in top_keys, (case["query"], expected_key, top_keys)
        payload = point_payloads[expected_key]
        assert all(term.casefold() in payload.casefold() for term in case["required_terms"]), case


def test_build_builtin_course_graph_maps_materials_points_chunks_and_prerequisites() -> None:
    user = User(
        id=7,
        account="student",
        hashed_password="not-used",
        display_name="学习者",
        role="student",
        starter_mode="data_structures",
    )

    course = build_builtin_data_structures_course_graph(user)
    for index, point in enumerate(course.knowledge_points, start=101):
        point.id = index
    finalize_builtin_course_graph(course)

    point_ids = {point.id for point in course.knowledge_points}
    assert course.title == "数据结构与算法"
    assert course.owner is user
    assert course.structure_json["package_version"] == "2026.07.14.2"
    assert len(course.materials) == 9
    assert len(course.knowledge_points) == 56
    assert len(course.knowledge_chunks) == 184
    assert all(chunk.course is course for chunk in course.knowledge_chunks)
    assert all(chunk.material in course.materials for chunk in course.knowledge_chunks)
    assert all(chunk.knowledge_point in course.knowledge_points for chunk in course.knowledge_chunks)
    assert all(chunk.embedding is None for chunk in course.knowledge_chunks)
    assert all(
        prerequisite_id in point_ids
        for point in course.knowledge_points
        for prerequisite_id in point.prerequisites_json
    )


def test_existing_builtin_course_refreshes_in_place_when_package_shape_is_incomplete() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.deleted: list[object] = []
            self.added: list[object] = []

        def add(self, value: object) -> None:
            self.added.append(value)

        def flush(self) -> None:
            return None

        def delete(self, value: object) -> None:
            self.deleted.append(value)

    user = User(
        id=10,
        account="existing_student",
        hashed_password="not-used",
        display_name="已有学习者",
        role="student",
        starter_mode="data_structures",
    )
    course = build_builtin_data_structures_course_graph(user)
    missing_keys = {"multiway-search-trees", "external-sorting"}
    missing_points = [
        point
        for point in course.knowledge_points
        if getattr(point, "builtin_key", None) in missing_keys
    ]
    missing_chunks = [
        chunk for chunk in course.knowledge_chunks if chunk.knowledge_point in missing_points
    ]
    for chunk in missing_chunks:
        course.knowledge_chunks.remove(chunk)
    for point in missing_points:
        course.knowledge_points.remove(point)
    for index, point in enumerate(course.knowledge_points, start=201):
        point.id = index
    for index, chunk in enumerate(course.knowledge_chunks, start=501):
        chunk.id = index
    finalize_builtin_course_graph(course)

    original_course_id = 88
    course.id = original_course_id
    course.structure_json = {**course.structure_json, "package_version": "2026.07.14.2"}
    first_chunk = course.knowledge_chunks[0]
    first_chunk.content = "旧版内容"
    first_chunk.embedding = [0.1, 0.2]
    first_chunk.embedding_provider = "legacy"
    first_chunk.embedding_model = "legacy-model"
    first_chunk.embedding_dimension = 2
    first_chunk.embedding_profile_hash = "legacy-profile"

    session = FakeSession()
    refresh_builtin_data_structures_course(session, course)  # type: ignore[arg-type]

    assert course.id == original_course_id
    assert course.structure_json["package_version"] == "2026.07.14.2"
    assert len(course.knowledge_points) == 56
    assert len(course.knowledge_chunks) == 184
    assert first_chunk.content != "旧版内容"
    assert first_chunk.embedding is None
    assert first_chunk.embedding_provider is None
    assert session.deleted == []
    assert len([value for value in session.added if isinstance(value, KnowledgePoint)]) == 2
    assert len([value for value in session.added if isinstance(value, KnowledgeChunk)]) == 6


def test_source_attribution_only_contains_public_bibliography() -> None:
    attribution = (PACKAGE_DIR / "source_attribution.md").read_text(encoding="utf-8")

    assert "数据结构（C语言版）（第2版）" in attribution
    assert "人民邮电出版社" in attribution
    assert "978-7-115-37950-4" in attribution
    assert "C:\\Users" not in attribution
    assert ".pdf" not in attribution.casefold()


def test_legacy_course_detection_uses_internal_marker_or_strict_structure_not_title_only() -> None:
    owner = User(
        id=8,
        account="owner",
        hashed_password="not-used",
        display_name="课程作者",
        role="student",
        starter_mode="blank",
    )
    marked = Course(
        owner=owner,
        title="任意旧内置课标题",
        source_type="builtin",
        visibility="private",
        status="ready",
        structure_json={},
    )
    CourseMaterial(
        user=owner,
        course=marked,
        filename="legacy.md",
        content_type="text/markdown",
        storage_path="builtin://legacy.md",
        parse_status="completed",
        metadata_json={"source": "starter_copy", "course_slug": "ai-intro"},
    )
    assert _is_legacy_builtin_course(marked) is True

    orphan = Course(
        owner_id=None,
        title="人工智能导论",
        source_type="builtin",
        visibility="public",
        status="ready",
        structure_json={},
    )
    for index, title in enumerate(sorted(LEGACY_KNOWLEDGE_POINT_TITLES), start=1):
        KnowledgePoint(
            course=orphan,
            title=title,
            summary="历史知识点",
            chapter="历史章节",
            order_index=index,
            difficulty="medium",
            prerequisites_json=[],
        )
    assert _is_legacy_builtin_course(orphan) is True

    orphan_data_structures = Course(
        owner_id=None,
        title="数据结构与算法",
        source_type="builtin",
        visibility="public",
        status="ready",
        structure_json={"course_slug": "data-structures-c-python"},
    )
    assert _is_legacy_builtin_course(orphan_data_structures) is True

    user_course = Course(
        owner=owner,
        title="人工智能导论",
        source_type="uploaded",
        visibility="private",
        status="ready",
        structure_json={},
    )
    CourseMaterial(
        user=owner,
        course=user_course,
        filename="用户课程来源.md",
        content_type="text/markdown",
        storage_path="uploads/user-course.md",
        parse_status="completed",
        metadata_json={"source": "builtin_seed", "course_slug": "ai-intro"},
    )
    assert _is_legacy_builtin_course(user_course) is False

    current = build_builtin_data_structures_course_graph(owner)
    assert _is_legacy_builtin_course(current) is False
