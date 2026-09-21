from __future__ import annotations

import re
from typing import Any

from backend.app.models import Course, KnowledgeChunk, KnowledgePoint, StudentProfile
from backend.app.services.resource_artifacts import ArtifactBuildInput, build_resource_content
from backend.app.services.resource_contracts import (
    RESOURCE_EXCERPT_LIMIT,
    ResourceContext,
    ResourceDraft,
    SafeCitation,
)
from backend.app.services.resource_intent import personalization_summary


def build_resource_contexts(
    chunks: list[KnowledgeChunk],
    knowledge_point: KnowledgePoint | None,
    context_points: list[KnowledgePoint],
) -> list[ResourceContext]:
    point_by_id = {point.id: point for point in context_points}
    if knowledge_point is not None:
        point_by_id[knowledge_point.id] = knowledge_point

    selected_chunks = list(chunks)
    if knowledge_point is not None:
        point_key = resource_context_label_key(knowledge_point.title)
        direct_matches = [
            chunk
            for chunk in selected_chunks
            if point_key
            and (
                point_key in resource_context_label_key(chunk.section_title)
                or resource_context_label_key(chunk.section_title) in point_key
            )
        ]
        # 课程构建可能把相邻知识点的章节覆盖切片一并保留下来；存在精确章节证据时，
        # 只使用直接命中的切片，避免资源主题被相邻章节稀释。
        if direct_matches:
            selected_chunks = direct_matches

    contexts: list[ResourceContext] = []
    for chunk in selected_chunks[:5]:
        metadata = chunk.metadata_json or {}
        source_title = safe_resource_title(metadata.get("source_filename") or "课程资料")
        section_title = safe_resource_title(chunk.section_title)
        point = point_by_id.get(chunk.knowledge_point_id or 0) or knowledge_point
        fallback_title = point.title if point is not None else "课程知识点"
        citation = SafeCitation(
            chunk_id=chunk.id,
            knowledge_point_id=chunk.knowledge_point_id,
            source_title=source_title or "课程资料",
            section_title=section_title or fallback_title,
            page_number=chunk.page_number,
        )
        contexts.append(
            ResourceContext(
                citation=citation,
                excerpt=safe_resource_excerpt(chunk.content),
                keywords=resource_context_keywords(point, section_title, chunk.content),
            )
        )
    return contexts


def summarize_resource_profile(profile: StudentProfile | None) -> dict[str, Any]:
    if profile is None:
        return {
            "learning_goal": "",
            "knowledge_foundation": "",
            "weak_points": [],
            "learning_preference": "",
        }
    data = profile.profile_json or {}
    weak_points = data.get("weak_points")
    return {
        "learning_goal": safe_resource_title(data.get("learning_goal")),
        "knowledge_foundation": safe_resource_title(data.get("knowledge_foundation")),
        "weak_points": weak_points if isinstance(weak_points, list) else [],
        "learning_preference": safe_resource_title(data.get("learning_preference")),
    }


def build_resource_draft(
    *,
    resource_type: str,
    course: Course,
    knowledge_point: KnowledgePoint | None,
    context_points: list[KnowledgePoint],
    contexts: list[ResourceContext],
    profile_summary: dict[str, Any],
    difficulty: str,
    intent: dict[str, Any] | None = None,
) -> ResourceDraft:
    topic = knowledge_point.title if knowledge_point is not None else (
        context_points[0].title if context_points else course.title
    )
    title_map = {
        "doc": f"{topic}个性化讲解",
        "mindmap": f"{topic}思维导图",
        "quiz": f"{topic}练习题",
        "code": f"{topic}代码实操",
        "slide": f"{topic}PPT",
        "animation": f"{topic}动画图解",
    }
    citation_lines = [
        f"- {context.citation.section_title}（{context.citation.source_title}）"
        for context in contexts
    ] or ["- 当前课程知识点摘要"]
    excerpt_lines = [
        f"- [{context.citation.chunk_id}] {context.citation.section_title}：{context.excerpt}"
        for context in contexts
        if context.excerpt
    ] or [f"- {topic}：请先补充课程资料以提高依据。"]
    weak_points = "、".join(str(item) for item in profile_summary.get("weak_points", [])[:3]) or "暂无明确薄弱点"
    profile_goal = str(profile_summary.get("learning_goal") or "完成本知识点的理解和应用")
    foundation = str(profile_summary.get("knowledge_foundation") or "按当前课程进度复习")
    source = ArtifactBuildInput(
        resource_type=resource_type,
        topic=topic,
        course_title=course.title,
        difficulty=difficulty,
        citation_lines=citation_lines,
        excerpt_lines=excerpt_lines,
        weak_points=weak_points,
        profile_goal=profile_goal,
        foundation=foundation,
        learning_preference=str(profile_summary.get("learning_preference") or ""),
        citation_refs=[context.citation.chunk_id for context in contexts],
    )
    content_json = build_resource_content(source)
    if intent:
        content_json = {
            **content_json,
            "intent": intent,
            "personalization_summary": personalization_summary(intent),
        }
    return ResourceDraft(
        title=title_map[resource_type],
        markdown=str(content_json["markdown"]),
        content_json={
            **content_json,
            "context_keywords": sorted({keyword for context in contexts for keyword in context.keywords})[:12],
            "profile_overlay": {
                "learning_goal": profile_summary.get("learning_goal", ""),
                "knowledge_foundation": profile_summary.get("knowledge_foundation", ""),
                "weak_points": profile_summary.get("weak_points", []),
                "learning_preference": profile_summary.get("learning_preference", ""),
            },
        },
        source=source,
    )


def safe_resource_title(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())[:120]


def safe_resource_excerpt(value: object) -> str:
    cleaned = " ".join(str(value or "").split())
    for marker in ("系统提示词", "模型输入", "API Key", "api key", "sk-", "完整资料原文", "资料原文"):
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].strip()
    if not cleaned:
        return "课程片段为空"
    if len(cleaned) <= RESOURCE_EXCERPT_LIMIT:
        safe_length = max(16, min(len(cleaned) - 1, RESOURCE_EXCERPT_LIMIT // 2))
        return f"{cleaned[:safe_length]}..."
    return f"{cleaned[:RESOURCE_EXCERPT_LIMIT]}..."


def resource_context_label_key(value: object) -> str:
    cleaned = re.sub(r"^\s*(?:第\s*)?\d+(?:\.\d+)*(?:\s*[章节])?\s*", "", str(value or ""))
    return "".join(character for character in cleaned.casefold() if character.isalnum())


def resource_context_keywords(point: KnowledgePoint | None, section_title: str, content: str) -> list[str]:
    candidates = [
        point.title if point is not None else "",
        section_title,
        *(token.strip("，。；：、,.()（）[]【】") for token in str(content or "").split()),
    ]
    keywords: list[str] = []
    for candidate in candidates:
        cleaned = safe_resource_title(candidate)
        if 2 <= len(cleaned) <= 24 and cleaned not in keywords:
            keywords.append(cleaned)
        if len(keywords) >= 8:
            break
    return keywords
