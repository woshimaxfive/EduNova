from __future__ import annotations

from datetime import UTC
from pathlib import Path
import re

from backend.app.models import Course, KnowledgeChunk, KnowledgePoint, Material, MaterialComparisonRun
from backend.app.schemas.materials import (
    MaterialComparisonCitation,
    MaterialComparisonPoint,
    MaterialComparisonResult,
    MaterialComparisonSummary,
)
from backend.app.services.material_contracts import MaterialEvidence, MaterialRepository


class MaterialComparisonBuilder:
    """Builds the deterministic, evidence-bounded material comparison draft."""

    def __init__(
        self,
        repository: MaterialRepository,
        *,
        parsed_text_extensions: set[str],
        exam_title_keywords: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.parsed_text_extensions = parsed_text_extensions
        self.exam_title_keywords = exam_title_keywords

    def build_result(
        self,
        course: Course,
        material_ids: list[int],
        knowledge_points: list[KnowledgePoint],
        evidence: list[MaterialEvidence],
    ) -> MaterialComparisonResult:
        unique_material_ids = list(dict.fromkeys(material_ids))
        material_ids_with_evidence = {item.material_id for item in evidence}
        concept_groups = self.group_evidence(evidence)
        citations = self._build_citations(evidence)
        points = [self._comparison_point(title, items) for title, items in concept_groups.items()]
        points.sort(key=self._comparison_rank, reverse=True)

        repeated = [point for point in points if len(point.material_ids) >= 2]
        exam_likely = [
            point
            for point in points
            if len(point.material_ids) >= 2
            or any(self._is_exam_material(title) for title in point.source_titles)
        ]
        materials_only = [
            point
            for point in points
            if len(point.material_ids) == 1
            and not any(self._is_exam_material(title) for title in point.source_titles)
        ]
        questions_only = [
            point
            for point in points
            if len(point.material_ids) == 1
            and all(self._is_exam_material(title) for title in point.source_titles)
        ]
        covered_titles = {self._normalize_title(point.title) for point in points}
        missing_review = [
            MaterialComparisonPoint(
                title=point.title,
                material_ids=[],
                source_titles=[],
                reason="所选资料暂未覆盖这个课程知识点，建议补看课程资料或教师提纲。",
                confidence="low",
                support_count=0,
                knowledge_point_id=str(point.id),
            )
            for point in knowledge_points
            if self._normalize_title(point.title) not in covered_titles
        ]

        return MaterialComparisonResult(
            course_id=str(course.id),
            material_ids=[str(material_id) for material_id in unique_material_ids],
            summary=MaterialComparisonSummary(
                compared_material_count=len(unique_material_ids),
                comparable_material_count=len(material_ids_with_evidence),
                matched_concept_count=len(points),
                citation_count=len(citations),
                message="已基于课程知识切片和安全短摘录完成资料对比。",
            ),
            repeated_concepts=repeated[:8],
            exam_likely_points=exam_likely[:8],
            materials_only_points=materials_only[:8],
            questions_only_points=questions_only[:8],
            missing_review_points=missing_review[:8],
            priority_order=points[:10],
            citations=citations[:12],
        )

    @staticmethod
    def run_to_api(run: MaterialComparisonRun) -> MaterialComparisonResult:
        payload = dict(run.result_json or {})
        payload.update(
            {
                "id": str(run.id),
                "course_id": str(run.course_id),
                "material_ids": [str(item) for item in (run.material_ids_json or [])],
                "agent_trace_id": run.agent_trace_id,
                "generation_mode": run.generation_mode,
                "review_mode": run.review_mode,
                "created_at": run.created_at.astimezone(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        )
        return MaterialComparisonResult(**payload)

    def build_evidence(
        self,
        course_id: int,
        materials: list[Material],
        knowledge_points: list[KnowledgePoint],
    ) -> list[MaterialEvidence]:
        materials_by_id = {material.id: material for material in materials}
        source_ids = set(materials_by_id)
        points_by_id = {point.id: point for point in knowledge_points}
        course_materials = self.repository.list_course_materials(course_id)
        source_id_by_course_material_id = {
            course_material.id: self._safe_int((course_material.metadata_json or {}).get("source_material_id"))
            for course_material in course_materials
        }
        evidence: list[MaterialEvidence] = []

        for chunk in self.repository.list_knowledge_chunks(course_id):
            source_material_id = self._source_material_id_for_chunk(chunk, source_id_by_course_material_id)
            if source_material_id not in source_ids:
                continue
            material = materials_by_id[source_material_id]
            point = points_by_id.get(chunk.knowledge_point_id) if chunk.knowledge_point_id is not None else None
            title = point.title if point is not None else (chunk.section_title or self._title_from_text(chunk.content))
            evidence.append(
                MaterialEvidence(
                    material_id=material.id,
                    source_title=material.filename,
                    title=title,
                    content=chunk.content,
                    section_title=chunk.section_title,
                    page_number=chunk.page_number,
                    knowledge_point_id=point.id if point is not None else None,
                    confidence="high" if point is not None else "medium",
                )
            )

        material_ids_with_chunks = {item.material_id for item in evidence}
        for material in materials:
            if material.id in material_ids_with_chunks:
                continue
            if (
                material.parse_status != "completed"
                or material.ingestion_status != "confirmed"
                or not material.extracted_text
                or self._extension(material.filename) not in self.parsed_text_extensions
            ):
                continue
            evidence.extend(self._fallback_text_evidence(material, knowledge_points))
        return evidence

    def group_evidence(self, evidence: list[MaterialEvidence]) -> dict[str, list[MaterialEvidence]]:
        groups: dict[str, list[MaterialEvidence]] = {}
        display_titles: dict[str, str] = {}
        for item in evidence:
            title = item.title.strip() or "资料重点"
            group_key = self._concept_group_key(item)
            groups.setdefault(group_key, []).append(item)
            display_title = self._display_comparison_title(title)
            current_title = display_titles.get(group_key)
            if current_title is None or self._is_exam_material(current_title):
                display_titles[group_key] = display_title
        return {display_titles.get(group_key, group_key): items for group_key, items in groups.items()}

    def _fallback_text_evidence(
        self,
        material: Material,
        knowledge_points: list[KnowledgePoint],
    ) -> list[MaterialEvidence]:
        lines = [
            self._clean_text(part)
            for part in material.extracted_text.replace("\r\n", "\n").splitlines()
        ] if material.extracted_text else []
        lines = [line for line in lines if line]
        if not lines and material.extracted_text:
            lines = [self._clean_text(material.extracted_text)]

        evidence: list[MaterialEvidence] = []
        for line in lines[:12]:
            point = next((item for item in knowledge_points if item.title and item.title in line), None)
            title = point.title if point is not None else self._title_from_text(line)
            evidence.append(
                MaterialEvidence(
                    material_id=material.id,
                    source_title=material.filename,
                    title=title,
                    content=line,
                    section_title=title,
                    page_number=None,
                    knowledge_point_id=point.id if point is not None else None,
                    confidence="medium" if point is not None else "low",
                )
            )
        return evidence

    def _source_material_id_for_chunk(
        self,
        chunk: KnowledgeChunk,
        source_id_by_course_material_id: dict[int, int | None],
    ) -> int | None:
        source_material_id = self._safe_int((chunk.metadata_json or {}).get("source_material_id"))
        if source_material_id is not None:
            return source_material_id
        return source_id_by_course_material_id.get(chunk.material_id)

    @classmethod
    def _concept_group_key(cls, item: MaterialEvidence) -> str:
        combined = f"{item.title} {item.section_title or ''} {item.content[:500]}".casefold()
        aliases = (
            (
                "concept:a-star",
                (r"\ba\s*\*", r"\bastar\b", r"a星", r"启发式搜索", r"f\s*\(n\)\s*=\s*g\s*\(n\)\s*\+\s*h\s*\(n\)"),
            ),
            ("concept:backpropagation", (r"反向传播", r"误差反传", r"back\s*propagation", r"\bbackprop\b")),
            ("concept:forward-propagation", (r"前向传播", r"forward\s*propagation")),
            ("concept:gradient-descent", (r"梯度下降", r"gradient\s*descent")),
        )
        for key, patterns in aliases:
            if any(re.search(pattern, combined, re.IGNORECASE) for pattern in patterns):
                return key
        if item.knowledge_point_id is not None:
            return f"knowledge-point:{item.knowledge_point_id}"
        return cls._normalize_title(item.title)

    def _comparison_point(self, title: str, evidence: list[MaterialEvidence]) -> MaterialComparisonPoint:
        material_ids = sorted({item.material_id for item in evidence})
        source_titles = sorted({item.source_title for item in evidence})
        knowledge_point_id = next(
            (item.knowledge_point_id for item in evidence if item.knowledge_point_id is not None),
            None,
        )
        if len(material_ids) >= 2:
            reason = "多份资料重复出现，适合作为优先复习重点。"
            confidence = "high"
        elif all(self._is_exam_material(title) for title in source_titles):
            reason = "只在试题或样题类资料出现，建议作为查漏补缺题型。"
            confidence = "medium"
        else:
            reason = "只在单份资料出现，建议结合课程目标判断是否补看。"
            confidence = "medium"
        return MaterialComparisonPoint(
            title=title,
            material_ids=[str(material_id) for material_id in material_ids],
            source_titles=source_titles,
            reason=reason,
            confidence=confidence,
            support_count=len(evidence),
            knowledge_point_id=str(knowledge_point_id) if knowledge_point_id is not None else None,
        )

    def _comparison_rank(self, point: MaterialComparisonPoint) -> tuple[int, int, int, str]:
        exam_score = 1 if any(self._is_exam_material(title) for title in point.source_titles) else 0
        return (len(point.material_ids), exam_score, point.support_count, point.title)

    def _build_citations(self, evidence: list[MaterialEvidence]) -> list[MaterialComparisonCitation]:
        citations: list[MaterialComparisonCitation] = []
        seen: set[tuple[int, str]] = set()
        for item in evidence:
            key = (item.material_id, item.title)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                MaterialComparisonCitation(
                    id=f"m{item.material_id}-{len(citations) + 1}",
                    material_id=str(item.material_id),
                    source_title=item.source_title,
                    section_title=item.section_title,
                    page_number=item.page_number,
                    excerpt=self._safe_excerpt(item.content),
                    confidence=item.confidence,
                )
            )
        return citations

    def _is_exam_material(self, title: str) -> bool:
        return any(keyword in title for keyword in self.exam_title_keywords)

    def _title_from_text(self, text: str) -> str:
        cleaned = self._clean_text(text)
        for separator in ("：", ":", "。", "，", ",", " "):
            if separator in cleaned:
                candidate = cleaned.split(separator, 1)[0].strip()
                if candidate:
                    return candidate[:40]
        return cleaned[:40] or "资料重点"

    def _safe_excerpt(self, text: str, limit: int = 80) -> str:
        cleaned = self._clean_text(text)
        for marker in ("SECRET", "API Key", "系统提示词", "模型输入", "完整资料原文"):
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0].strip()
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[:limit].rstrip()}..."

    @classmethod
    def _display_comparison_title(cls, title: str) -> str:
        return cls._strip_exam_title_prefix(title).strip() or title.strip() or "资料重点"

    @classmethod
    def _normalize_title(cls, title: str) -> str:
        cleaned = cls._strip_exam_title_prefix(title)
        return "".join(cleaned.lower().split())

    @staticmethod
    def _strip_exam_title_prefix(title: str) -> str:
        cleaned = title.strip()
        for prefix in ("期末样题", "期末试题", "样题", "试题", "真题", "考试", "复习", "试题独有"):
            for separator in ("：", ":", "-", "—"):
                marker = f"{prefix}{separator}"
                if cleaned.startswith(marker):
                    return cleaned[len(marker) :].strip()
        return cleaned

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extension(filename: str) -> str:
        return Path(filename).suffix.lower()
