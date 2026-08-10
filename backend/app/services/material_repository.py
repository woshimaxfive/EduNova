from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.app.models import (
    Course,
    CourseMaterial,
    CourseMaterialLink,
    KnowledgeChunk,
    KnowledgePoint,
    Material,
    MaterialChunk,
    MaterialComparisonRun,
)


class SqlAlchemyMaterialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def add_material(self, material: Material) -> None:
        self.db.add(material)
        self.db.flush()

    def add_material_chunks(self, chunks: list[MaterialChunk]) -> None:
        self.db.add_all(chunks)
        self.db.flush()

    def get_material_for_user(self, user_id: int, material_id: int) -> Material | None:
        return self.db.scalar(select(Material).where(Material.id == material_id, Material.user_id == user_id))

    def delete_material(self, material: Material) -> None:
        self.db.delete(material)

    def list_materials(
        self,
        user_id: int,
        course_id: int | None = None,
        unassigned: bool = False,
    ) -> list[Material]:
        statement = select(Material).where(Material.user_id == user_id)
        if course_id is not None:
            statement = statement.join(
                CourseMaterialLink,
                CourseMaterialLink.material_id == Material.id,
            ).where(CourseMaterialLink.course_id == course_id)
        if unassigned:
            linked_material = select(CourseMaterialLink.id).where(CourseMaterialLink.material_id == Material.id)
            statement = statement.where(~exists(linked_material))
        return list(self.db.scalars(statement.order_by(Material.created_at.desc(), Material.id.desc())))

    def list_material_chunks(self, user_id: int, material_id: int) -> list[MaterialChunk]:
        return list(
            self.db.scalars(
                select(MaterialChunk)
                .join(Material, Material.id == MaterialChunk.material_id)
                .where(Material.user_id == user_id, MaterialChunk.material_id == material_id)
                .order_by(MaterialChunk.chunk_index, MaterialChunk.id)
            )
        )

    def list_material_course_links(
        self,
        user_id: int,
        material_id: int,
    ) -> list[tuple[CourseMaterialLink, Course]]:
        rows = self.db.execute(
            select(CourseMaterialLink, Course)
            .join(Course, Course.id == CourseMaterialLink.course_id)
            .where(
                CourseMaterialLink.material_id == material_id,
                Course.owner_id == user_id,
            )
            .order_by(Course.updated_at.desc(), Course.id.desc())
        ).all()
        return [(link, course) for link, course in rows]

    def get_link(self, course_id: int, material_id: int) -> CourseMaterialLink | None:
        return self.db.scalar(
            select(CourseMaterialLink).where(
                CourseMaterialLink.course_id == course_id,
                CourseMaterialLink.material_id == material_id,
            )
        )

    def add_link(self, link: CourseMaterialLink) -> CourseMaterialLink:
        existing = self.get_link(link.course_id, link.material_id)
        if existing is not None:
            return existing
        self.db.add(link)
        self.db.flush()
        return link

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]:
        return list(
            self.db.scalars(
                select(CourseMaterial).where(CourseMaterial.course_id == course_id).order_by(CourseMaterial.id)
            )
        )

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint)
                .where(KnowledgePoint.course_id == course_id)
                .order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        return list(
            self.db.scalars(
                select(KnowledgeChunk).where(KnowledgeChunk.course_id == course_id).order_by(KnowledgeChunk.id)
            )
        )

    def add_comparison_run(self, run: MaterialComparisonRun) -> MaterialComparisonRun:
        self.db.add(run)
        self.db.flush()
        return run

    def get_comparison_run_for_user(
        self,
        user_id: int,
        comparison_id: int,
    ) -> MaterialComparisonRun | None:
        return self.db.scalar(
            select(MaterialComparisonRun).where(
                MaterialComparisonRun.id == comparison_id,
                MaterialComparisonRun.user_id == user_id,
            )
        )

    def get_latest_comparison_run(
        self,
        user_id: int,
        course_id: int,
    ) -> MaterialComparisonRun | None:
        return self.db.scalar(
            select(MaterialComparisonRun)
            .where(
                MaterialComparisonRun.user_id == user_id,
                MaterialComparisonRun.course_id == course_id,
            )
            .order_by(MaterialComparisonRun.created_at.desc(), MaterialComparisonRun.id.desc())
            .limit(1)
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)
