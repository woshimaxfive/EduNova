from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    AgentRunLog,
    Course,
    GeneratedResource,
    KnowledgeChunk,
    KnowledgePoint,
    ResourceQualityScore,
    StudentProfile,
    User,
)
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.auth import AuthService
from backend.app.services.model_settings import ModelNotConfiguredError


NOW = datetime(2026, 7, 5, 14, 0, tzinfo=UTC)


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeResourceRepository:
    courses: list[Course] = field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    profiles: dict[int, StudentProfile] = field(default_factory=dict)
    resources: list[GeneratedResource] = field(default_factory=list)
    quality_scores: list[ResourceQualityScore] = field(default_factory=list)
    agent_logs: list[AgentRunLog] = field(default_factory=list)
    next_resource_id: int = 1001
    next_quality_id: int = 2001
    next_log_id: int = 3001
    committed: bool = False
    rolled_back: bool = False

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.id == course_id and course.owner_id == user_id), None)

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None:
        return next(
            (
                point
                for point in self.knowledge_points
                if point.id == knowledge_point_id and point.course_id == course_id
            ),
            None,
        )

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return sorted(
            [point for point in self.knowledge_points if point.course_id == course_id],
            key=lambda point: (point.order_index, point.id),
        )

    def list_course_chunks(self, course_id: int, knowledge_point_id: int | None = None) -> list[KnowledgeChunk]:
        chunks = [chunk for chunk in self.chunks if chunk.course_id == course_id]
        if knowledge_point_id is not None:
            chunks = [chunk for chunk in chunks if chunk.knowledge_point_id == knowledge_point_id]
        return sorted(chunks, key=lambda chunk: chunk.id)

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.profiles.get(user_id)

    def add_resource(self, resource: GeneratedResource) -> GeneratedResource:
        resource.id = self.next_resource_id
        self.next_resource_id += 1
        resource.created_at = resource.created_at or NOW
        resource.updated_at = resource.updated_at or NOW
        self.resources.append(resource)
        return resource

    def add_quality_score(self, score: ResourceQualityScore) -> ResourceQualityScore:
        score.id = self.next_quality_id
        self.next_quality_id += 1
        score.created_at = score.created_at or NOW
        self.quality_scores.append(score)
        return score

    def add_agent_log(self, log: AgentRunLog) -> AgentRunLog:
        log.id = self.next_log_id
        self.next_log_id += 1
        log.created_at = log.created_at or NOW
        self.agent_logs.append(log)
        return log

    def list_resources(
        self,
        user_id: int,
        *,
        course_id: int | None = None,
        resource_type: str | None = None,
    ) -> list[GeneratedResource]:
        resources = [resource for resource in self.resources if resource.user_id == user_id]
        if course_id is not None:
            resources = [resource for resource in resources if resource.course_id == course_id]
        if resource_type is not None:
            resources = [resource for resource in resources if resource.resource_type == resource_type]
        return sorted(resources, key=lambda resource: (resource.updated_at, resource.id), reverse=True)

    def get_resource_for_user(self, user_id: int, resource_id: int) -> GeneratedResource | None:
        return next(
            (resource for resource in self.resources if resource.user_id == user_id and resource.id == resource_id),
            None,
        )

    def list_quality_scores(self, resource_id: int) -> list[ResourceQualityScore]:
        return sorted([score for score in self.quality_scores if score.resource_id == resource_id], key=lambda item: item.id)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def refresh(self, _instance: object) -> None:
        return None


@dataclass
class FakeModelSettingsService:
    mode: str = "success"
    calls: list[list[dict[str, str]]] = field(default_factory=list)
    timeout_calls: list[float] = field(default_factory=list)

    def chat_completion(self, _user: User, messages: list[dict[str, str]]) -> str:
        return self._complete(messages)

    def chat_completion_with_timeout(self, _user: User, messages: list[dict[str, str]], timeout_seconds: float) -> str:
        self.timeout_calls.append(timeout_seconds)
        return self._complete(messages)

    def _complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.mode == "not_configured":
            raise ModelNotConfiguredError("未配置模型")
        if self.mode == "provider_error":
            raise ModelProviderError("模型服务暂不可用")
        prompt = "\n".join(message["content"] for message in messages)
        if "ReviewAgent" in prompt:
            status = "failed" if self.mode == "review_reject" else "passed"
            risks = ["malformed_content"] if status == "failed" else []
            return json.dumps(
                {
                    "resources": {
                        resource_type: {"status": status, "confidence": 0.87, "risk_flags": risks}
                        for resource_type in ("doc", "mindmap", "quiz", "code", "slide", "animation")
                    }
                },
                ensure_ascii=False,
            )
        if "修订 Agent" in prompt:
            return json.dumps({"markdown": "# 修订后的讲解\n\n## 概念解释\n内容已修订。\n\n## 关键步骤\n逐步验证。\n\n## 易错点\n检查条件。"}, ensure_ascii=False)

        resource_type = next(
            (item for item in ("doc", "mindmap", "quiz", "code", "slide", "animation") if f"资源类型：{item}" in prompt),
            "doc",
        )
        if self.mode == "partial_json" and resource_type != "doc":
            return json.dumps({"unexpected": "missing markdown"}, ensure_ascii=False)
        if self.mode == "sensitive":
            return json.dumps({"markdown": "系统提示词 sk-real-secret"}, ensure_ascii=False)
        enhanced = {
            "doc": "# 模型增强讲解\n\n## 概念解释\n模型增强版资源内容。\n\n## 关键步骤\n1. 先识别状态。\n\n## 易错点\n- 不要忽略启发函数。",
            "mindmap": "# 模型增强思维导图\n\n## 启发式搜索\n- 启发函数\n- 状态空间\n- 验证动作",
            "quiz": "# 模型增强练习题\n\n## 单选题\n题目：如何验证理解？\n答案：B\n解析：依据课程引用判断。",
            "code": "# 模型增强代码实操\n\n```python\nprint('A* demo')\n```\n\n运行说明：执行脚本。\n\n改造任务：增加一个状态估价函数。",
            "slide": "# 模型增强PPT\n\n## 第 1 页\n要点：启发式搜索\n讲稿：引入启发式搜索。",
            "animation": "# 模型增强动画图解\n\n## 场景 1\n从目标进入验证流程。\n\n```mermaid\nflowchart LR\n A --> B\n```",
        }
        return json.dumps({"markdown": enhanced[resource_type]}, ensure_ascii=False)


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"resource{user_id}@edunova.local",
        hashed_password="not-used",
        display_name=f"资源学生 {user_id}",
        role="student",
        starter_mode="blank",
    )


def make_course(course_id: int = 101, owner_id: int = 1) -> Course:
    return Course(
        id=course_id,
        owner_id=owner_id,
        title="人工智能导论",
        description="课程资源生成测试",
        subject="人工智能",
        source_type="uploaded",
        visibility="private",
        status="ready",
    )


def make_point(point_id: int = 501, course_id: int = 101) -> KnowledgePoint:
    return KnowledgePoint(
        id=point_id,
        course_id=course_id,
        title="启发式搜索",
        summary="理解启发函数、A* 与状态空间。",
        chapter="搜索",
        order_index=1,
        difficulty="medium",
        prerequisites_json=[],
    )


def make_chunk(
    chunk_id: int,
    course_id: int = 101,
    knowledge_point_id: int | None = 501,
    content: str = "A* 搜索会结合已走代价和启发函数估计值来选择下一个状态。",
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        course_id=course_id,
        material_id=301,
        knowledge_point_id=knowledge_point_id,
        content=content,
        page_number=3,
        section_title="A* 搜索",
        metadata_json={"source_filename": "人工智能导论讲义.md"},
    )


def make_repo() -> FakeResourceRepository:
    return FakeResourceRepository(
        courses=[make_course(), make_course(202, owner_id=2)],
        knowledge_points=[make_point(), make_point(601, course_id=202)],
        chunks=[
            make_chunk(701),
            make_chunk(702, content="启发函数必须低估真实代价，才能保证 A* 在特定条件下的最优性。"),
            make_chunk(801, course_id=202, knowledge_point_id=601, content="别人课程的完整资料原文。"),
        ],
        profiles={
            1: StudentProfile(
                id=11,
                user_id=1,
                profile_json={
                    "learning_goal": "两周内掌握搜索算法",
                    "knowledge_foundation": "刚学完 Python",
                    "weak_points": ["启发函数"],
                    "learning_preference": "喜欢例题",
                },
                confidence_score=Decimal("0.72"),
            )
        },
    )


def make_service(repo: FakeResourceRepository, model_service: FakeModelSettingsService | None = None):
    from backend.app.services.resources import ResourceGenerationService

    return ResourceGenerationService(
        repository=repo,
        model_settings_service=model_service or FakeModelSettingsService(),
    )


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def resource_by_type(resources: list[GeneratedResource], resource_type: str) -> GeneratedResource:
    return next(resource for resource in resources if resource.resource_type == resource_type)


def assert_usable_resource_content(resources: list[GeneratedResource]) -> None:
    content_by_type = {resource.resource_type: resource.content_json["markdown"] for resource in resources}
    assert "概念解释" in content_by_type["doc"]
    assert "关键步骤" in content_by_type["doc"]
    assert "易错点" in content_by_type["doc"]
    assert resource_by_type(resources, "mindmap").content_json["artifact"]["kind"] == "mindmap"
    assert "markmap_markdown" in resource_by_type(resources, "mindmap").content_json["artifact"]
    assert "单选题" in content_by_type["quiz"]
    assert "答案" in content_by_type["quiz"]
    assert "解析" in content_by_type["quiz"]
    assert "```python" in content_by_type["code"]
    assert "运行说明" in content_by_type["code"]
    assert "改造任务" in content_by_type["code"]
    assert "第 1 页" in content_by_type["slide"]
    assert "讲稿" in content_by_type["slide"]
    if "animation" in content_by_type:
        assert resource_by_type(resources, "animation").content_json["artifact"]["kind"] == "animation"
        assert len(resource_by_type(resources, "animation").content_json["artifact"]["scenes"]) >= 3


def test_resources_route_requires_login() -> None:
    client = TestClient(create_app())

    list_response = client.get("/api/v1/resources")
    generate_response = client.post("/api/v1/resources/generate", json={"course_id": 101, "resource_types": ["doc"]})
    detail_response = client.get("/api/v1/resources/1")
    quality_response = client.get("/api/v1/resources/1/quality")

    assert list_response.status_code == 401
    assert generate_response.status_code == 401
    assert detail_response.status_code == 401
    assert quality_response.status_code == 401


def test_generate_six_resource_types_persists_v2_artifacts_quality_scores_and_parallel_worker_trace() -> None:
    repo = make_repo()
    model_service = FakeModelSettingsService(mode="success")

    result = as_dict(
        make_service(repo, model_service).generate_resources(
            make_user(),
            course_id=101,
            knowledge_point_id=501,
            resource_types=["doc", "mindmap", "quiz", "code", "slide", "animation", "doc"],
            learning_goal="期末前会做搜索题",
            difficulty="medium",
        )
    )

    assert result["agent_trace_id"].startswith("trace_")
    assert [resource["resource_type"] for resource in result["resources"]] == ["doc", "mindmap", "quiz", "code", "slide", "animation"]
    assert len(repo.resources) == 6
    assert len(repo.quality_scores) == 30
    assert [log.agent_name for log in repo.agent_logs[:4]] == ["profile", "retrieve", "diagnosis", "planner"]
    worker_logs = [log for log in repo.agent_logs if log.step_index == 5]
    assert {log.agent_name for log in worker_logs} == {
        "DocWorker",
        "MindmapWorker",
        "QuizWorker",
        "CodeWorker",
        "SlideWorker",
        "AnimationWorker",
    }
    assert [log.agent_name for log in repo.agent_logs if log.step_index >= 6] == ["aggregate", "ReviewAgent", "persist"]
    assert all(resource.user_id == 1 and resource.course_id == 101 for resource in repo.resources)
    assert all(resource.status == "completed" for resource in repo.resources)
    assert all(resource.review_status == "passed" for resource in repo.resources)
    assert all(resource.agent_trace_id == result["agent_trace_id"] for resource in repo.resources)
    assert all(resource.content_json["metadata"]["agent_trace_id"] == result["agent_trace_id"] for resource in repo.resources)
    assert all(resource.content_json["metadata"]["generation_mode"] == "model_enhanced" for resource in repo.resources)
    assert all(resource.content_json["schema_version"] == 2 for resource in repo.resources)
    assert all(resource.content_json["metadata"]["review_mode"] == "model_and_rules" for resource in repo.resources)
    assert all(resource["agent_trace_id"] == result["agent_trace_id"] for resource in result["resources"])
    assert all(log.metadata_json["workflow"] == "resource_generation" for log in repo.agent_logs)
    assert all(log.metadata_json["artifact_type"] == "generated_resource" for log in repo.agent_logs)
    assert set(result["quality_scores"].keys()) == {resource["id"] for resource in result["resources"]}
    assert len(model_service.calls) == 7
    assert model_service.timeout_calls == [5.0] * 7
    assert_usable_resource_content(repo.resources)
    assert repo.committed is True


def test_generate_uses_usable_deterministic_source_when_model_is_unavailable() -> None:
    repo = make_repo()
    model_service = FakeModelSettingsService(mode="provider_error")

    result = as_dict(
        make_service(repo, model_service).generate_resources(
            make_user(),
            course_id=101,
            knowledge_point_id=501,
            resource_types=["doc"],
            learning_goal="",
            difficulty="easy",
        )
    )

    resource = result["resources"][0]
    assert resource["review_status"] == "passed"
    assert resource["confidence_score"] >= 0.7
    assert resource["content_json"]["metadata"]["generation_mode"] == "deterministic_source"
    assert "模型增强版" not in resource["content_json"]["markdown"]
    assert "概念解释" in resource["content_json"]["markdown"]
    assert "关键步骤" in resource["content_json"]["markdown"]
    assert "易错点" in resource["content_json"]["markdown"]
    assert "启发式搜索" in resource["title"]
    review_log = next(log for log in repo.agent_logs if log.agent_name == "ReviewAgent")
    assert review_log.status == "warning"
    assert review_log.metadata_json["review_mode"] == "rules_only"
    assert resource["content_json"]["metadata"]["review_mode"] == "rules_only"
    assert result["warnings"] == ["模型审核暂不可用，资源已通过本地结构与安全规则审核。"]


def test_generate_provider_failure_keeps_all_resource_types_usable_with_per_worker_fallback() -> None:
    repo = make_repo()
    model_service = FakeModelSettingsService(mode="provider_error")

    result = as_dict(
        make_service(repo, model_service).generate_resources(
            make_user(),
            course_id=101,
            knowledge_point_id=501,
            resource_types=["doc", "mindmap", "quiz", "code", "slide", "animation"],
            learning_goal="",
            difficulty="medium",
        )
    )

    assert len(result["resources"]) == 6
    assert len(repo.resources) == 6
    assert all(resource.review_status == "passed" for resource in repo.resources)
    assert all(resource.content_json["metadata"]["generation_mode"] == "deterministic_source" for resource in repo.resources)
    assert_usable_resource_content(repo.resources)
    assert len(model_service.calls) == 7
    assert model_service.timeout_calls == [5.0] * 7
    assert repo.committed is True


def test_generate_applies_partial_model_enhancement_and_keeps_missing_types_deterministic() -> None:
    repo = make_repo()
    model_service = FakeModelSettingsService(mode="partial_json")

    make_service(repo, model_service).generate_resources(
        make_user(),
        course_id=101,
        knowledge_point_id=501,
        resource_types=["doc", "quiz"],
        learning_goal="考前复习",
        difficulty="medium",
    )

    doc = resource_by_type(repo.resources, "doc")
    quiz = resource_by_type(repo.resources, "quiz")
    assert doc.content_json["metadata"]["generation_mode"] == "model_enhanced"
    assert "模型增强版资源内容" in doc.content_json["markdown"]
    assert quiz.content_json["metadata"]["generation_mode"] == "deterministic_source"
    assert "解析" in quiz.content_json["markdown"]
    assert len(model_service.calls) == 3


def test_review_agent_rejects_then_repairs_once_before_persisting() -> None:
    repo = make_repo()
    model_service = FakeModelSettingsService(mode="review_reject")

    result = as_dict(
        make_service(repo, model_service).generate_resources(
            make_user(),
            course_id=101,
            knowledge_point_id=501,
            resource_types=["doc"],
            learning_goal="解释启发式搜索",
            difficulty="medium",
        )
    )

    assert len(result["resources"]) == 1
    resource = repo.resources[0]
    assert resource.review_status == "passed"
    assert resource.content_json["metadata"]["repair_count"] == 1
    assert "修订后的讲解" in resource.content_json["markdown"]
    assert any(log.agent_name == "RepairAgent" and log.metadata_json["repair_count"] == 1 for log in repo.agent_logs)


def test_generate_rejects_sensitive_model_output_and_preserves_deterministic_content() -> None:
    repo = make_repo()
    model_service = FakeModelSettingsService(mode="sensitive")

    make_service(repo, model_service).generate_resources(
        make_user(),
        course_id=101,
        knowledge_point_id=501,
        resource_types=["doc"],
        learning_goal="",
        difficulty="medium",
    )

    resource = repo.resources[0]
    assert resource.review_status == "passed"
    assert resource.content_json["metadata"]["generation_mode"] == "deterministic_source"
    assert "系统提示词" not in resource.content_json["markdown"]
    assert "sk-real-secret" not in resource.content_json["markdown"]


def test_generate_scopes_course_and_knowledge_point_to_current_user() -> None:
    from backend.app.services.resources import ResourceNotFoundError

    service = make_service(make_repo())

    with pytest.raises(ResourceNotFoundError):
        service.generate_resources(make_user(1), course_id=202, knowledge_point_id=601, resource_types=["doc"])

    with pytest.raises(ResourceNotFoundError):
        service.generate_resources(make_user(1), course_id=101, knowledge_point_id=601, resource_types=["doc"])


def test_resource_list_detail_and_quality_are_user_scoped_and_filterable() -> None:
    repo = make_repo()
    service = make_service(repo)
    service.generate_resources(make_user(), course_id=101, knowledge_point_id=501, resource_types=["doc", "quiz"])
    repo.resources.append(
        GeneratedResource(
            id=9999,
            user_id=2,
            course_id=202,
            knowledge_point_id=601,
            resource_type="doc",
            title="别人资源",
            content_json={"markdown": "别人内容", "metadata": {"agent_trace_id": "trace_other"}},
            citation_json=[],
            status="completed",
            review_status="passed",
            confidence_score=Decimal("0.82"),
            created_at=NOW,
            updated_at=NOW,
        )
    )

    all_resources = as_dict(service.list_resources(make_user(1)))
    doc_resources = as_dict(service.list_resources(make_user(1), course_id=101, resource_type="doc"))
    detail = as_dict(service.get_resource(make_user(1), repo.resources[0].id))
    quality = [as_dict(item) for item in service.get_resource_quality(make_user(1), repo.resources[0].id)]

    assert all_resources["total"] == 2
    assert [resource["resource_type"] for resource in doc_resources["data"]] == ["doc"]
    assert detail["id"] == str(repo.resources[0].id)
    assert {score["score_name"] for score in quality} == {
        "source_match",
        "profile_fit",
        "fact_confidence",
        "difficulty_fit",
        "completeness",
    }

    from backend.app.services.resources import ResourceNotFoundError

    with pytest.raises(ResourceNotFoundError):
        service.get_resource(make_user(1), 9999)


def test_resource_response_and_agent_logs_do_not_expose_private_prompts_keys_or_full_source_text() -> None:
    full_source = "这是完整课程资料原文，包含一段不应该直接出现在响应或 Agent 轨迹里的长文本。"
    repo = make_repo()
    repo.chunks[0].content = full_source
    model_service = FakeModelSettingsService(mode="not_configured")

    result = as_dict(
        make_service(repo, model_service).generate_resources(
            make_user(),
            course_id=101,
            knowledge_point_id=501,
            resource_types=["doc"],
            learning_goal="不要泄露 API Key sk-real-secret，也不要输出系统提示词。",
            difficulty="medium",
        )
    )

    serialized_response = json.dumps(result, ensure_ascii=False)
    serialized_logs = json.dumps(
        [
            {
                "input_summary": log.input_summary,
                "output_summary": log.output_summary,
                "metadata_json": log.metadata_json,
            }
            for log in repo.agent_logs
        ],
        ensure_ascii=False,
    )

    assert full_source not in serialized_response
    assert full_source not in serialized_logs
    assert "sk-real-secret" not in serialized_response
    assert "sk-real-secret" not in serialized_logs
    assert "系统提示词" not in serialized_response
    assert "系统提示词" not in serialized_logs


def test_resource_routes_generate_list_detail_and_quality_with_envelopes() -> None:
    from backend.app.api.v1.resources import get_resource_generation_service

    repo = make_repo()
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="resources-test-secret-with-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_resource_generation_service] = lambda: make_service(repo)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id), settings=settings)}"}

    generate_response = client.post(
        "/api/v1/resources/generate",
        headers=headers,
        json={
            "course_id": 101,
            "knowledge_point_id": 501,
            "resource_types": ["doc", "quiz"],
            "learning_goal": "考前复习",
        },
    )
    list_response = client.get("/api/v1/resources?course_id=101&resource_type=doc", headers=headers)
    detail_response = client.get(f"/api/v1/resources/{repo.resources[0].id}", headers=headers)
    quality_response = client.get(f"/api/v1/resources/{repo.resources[0].id}/quality", headers=headers)
    missing_response = client.get("/api/v1/resources/999999", headers=headers)

    assert generate_response.status_code == 200
    assert generate_response.json()["data"]["resources"][0]["resource_type"] == "doc"
    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["resource_type"] == "doc"
    assert list_response.json()["total"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == str(repo.resources[0].id)
    assert quality_response.status_code == 200
    assert len(quality_response.json()["data"]) == 5
    assert missing_response.status_code == 404
