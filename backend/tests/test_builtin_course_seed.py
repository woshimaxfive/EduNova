from backend.app.data.builtin_courses.ai_intro import BUILTIN_AI_INTRO_COURSE
from backend.app.models import Course, User
from backend.app.services.course_seed import (
    SYSTEM_USER_EMAIL,
    build_builtin_ai_intro_course_graph,
    seed_builtin_ai_intro_course,
)


EXPECTED_KNOWLEDGE_POINTS = {
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


class FakeSession:
    def __init__(
        self,
        existing_course: Course | None = None,
        existing_user: User | None = None,
    ) -> None:
        self.existing_course = existing_course
        self.existing_user = existing_user
        self.added = []
        self.flush_count = 0

    def scalar(self, statement):
        statement_text = str(statement)
        if "FROM courses" in statement_text:
            return self.existing_course
        if "FROM users" in statement_text:
            return self.existing_user
        return None

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        self.flush_count += 1
        for index, item in enumerate(self.added, start=1):
            if getattr(item, "id", None) is None:
                item.id = index


def test_builtin_ai_intro_course_package_has_required_learning_shape() -> None:
    package = BUILTIN_AI_INTRO_COURSE
    knowledge_points = package["knowledge_points"]

    assert package["title"] == "人工智能导论"
    assert package["source_type"] == "builtin"
    assert package["visibility"] == "public"
    assert package["status"] == "ready"
    assert len(knowledge_points) >= 12
    assert EXPECTED_KNOWLEDGE_POINTS <= {point["title"] for point in knowledge_points}
    assert sum(len(point["chunks"]) for point in knowledge_points) >= len(
        knowledge_points
    )

    for point in knowledge_points:
        assert point["summary"].strip()
        assert point["chapter"].strip()
        assert point["difficulty"] in {"easy", "medium", "hard"}
        for chunk in point["chunks"]:
            assert len(chunk["content"]) >= 40
            assert chunk["section_title"].strip()


def test_build_builtin_ai_intro_course_graph_maps_package_to_models() -> None:
    system_user = User(
        email=SYSTEM_USER_EMAIL,
        hashed_password="not-login-account",
        display_name="EduNova 系统",
        role="admin",
    )

    course = build_builtin_ai_intro_course_graph(system_user)

    assert course.title == "人工智能导论"
    assert course.source_type == "builtin"
    assert course.visibility == "public"
    assert course.status == "ready"
    assert course.owner is system_user
    assert len(course.materials) == 1
    assert course.materials[0].user is system_user
    assert course.materials[0].parse_status == "completed"
    assert "启发式搜索" in (course.materials[0].extracted_text or "")
    assert len(course.knowledge_points) >= 12
    assert [point.order_index for point in course.knowledge_points] == list(
        range(1, len(course.knowledge_points) + 1)
    )
    assert len(course.knowledge_chunks) >= len(course.knowledge_points)
    assert all(chunk.course is course for chunk in course.knowledge_chunks)
    assert all(chunk.material is course.materials[0] for chunk in course.knowledge_chunks)
    assert all(chunk.knowledge_point is not None for chunk in course.knowledge_chunks)
    assert all(chunk.embedding is None for chunk in course.knowledge_chunks)


def test_seed_builtin_ai_intro_course_creates_system_user_and_course_graph() -> None:
    session = FakeSession()

    result = seed_builtin_ai_intro_course(session)

    assert result.created is True
    assert result.course_title == "人工智能导论"
    assert result.knowledge_points >= 12
    assert result.chunks >= result.knowledge_points
    assert any(isinstance(item, User) for item in session.added)
    assert any(isinstance(item, Course) for item in session.added)
    assert session.flush_count == 1


def test_seed_builtin_ai_intro_course_is_idempotent_when_course_exists() -> None:
    existing_course = Course(
        id=42,
        title="人工智能导论",
        description="已存在课程",
        subject="人工智能",
        source_type="builtin",
        visibility="public",
        status="ready",
    )
    session = FakeSession(existing_course=existing_course)

    result = seed_builtin_ai_intro_course(session)

    assert result.created is False
    assert result.course_id == 42
    assert result.course_title == "人工智能导论"
    assert session.added == []
    assert session.flush_count == 0
