from __future__ import annotations


from backend.app.models import (
    CourseMaterial,
    KnowledgeChunk,
    Material,
    User,
)
from backend.app.services.course_contracts import (
    CourseGenerationError,
    ParsedSection,
)


class CourseContentMixin:
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
