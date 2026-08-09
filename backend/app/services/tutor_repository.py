from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.models import (
    AgentRunLog,
    AiJob,
    ChatMessage,
    ChatMessageAttachment,
    ChatSession,
    Course,
    CourseEnrollment,
    GeneratedResource,
    KnowledgePoint,
    Material,
)
from backend.app.schemas.tutor import TutorGeneratedResource, TutorResourceJob
from backend.app.services.tutor_contracts import SessionNotFoundError


class SqlAlchemyTutorSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sessions(self, user_id: int, scope: str, course_id: int | None = None) -> list[ChatSession]:
        statement = select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.scope == scope,
            ChatSession.archived_from_home.is_(False),
        )
        if course_id is not None:
            statement = statement.where(ChatSession.course_id == course_id)

        return list(self.db.scalars(statement.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())))

    def get_session_for_user(self, session_id: int, user_id: int) -> ChatSession | None:
        return self.db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
                ChatSession.archived_from_home.is_(False),
            )
        )

    def list_home_history(self, user_id: int, page: int, page_size: int, query: str) -> tuple[list[ChatSession], int]:
        filters = [
            ChatSession.user_id == user_id,
            ChatSession.scope == "home",
            ChatSession.archived_from_home.is_(False),
        ]
        if query:
            message_match = (
                select(ChatMessage.id)
                .where(
                    ChatMessage.session_id == ChatSession.id,
                    ChatMessage.content.icontains(query, autoescape=True),
                )
                .exists()
            )
            filters.append(or_(ChatSession.title.icontains(query, autoescape=True), message_match))
        total = int(self.db.scalar(select(func.count(ChatSession.id)).where(*filters)) or 0)
        sessions = list(
            self.db.scalars(
                select(ChatSession)
                .where(*filters)
                .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return sessions, total

    def find_history_match(self, session_id: int, query: str) -> str | None:
        if not query:
            return None
        return self.db.scalar(
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.content.icontains(query, autoescape=True),
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )

    def user_can_access_course(self, user_id: int, course_id: int) -> bool:
        owned_course = self.db.scalar(
            select(Course.id).where(
                Course.id == course_id,
                Course.owner_id == user_id,
            )
        )
        if owned_course is not None:
            return True

        enrollment = self.db.scalar(
            select(CourseEnrollment.id).where(
                CourseEnrollment.user_id == user_id,
                CourseEnrollment.course_id == course_id,
            )
        )
        return enrollment is not None

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        if not self.user_can_access_course(user_id, course_id):
            return None
        return self.db.scalar(select(Course).where(Course.id == course_id))

    def get_resource_for_user(self, user_id: int, resource_id: int) -> GeneratedResource | None:
        return self.db.scalar(
            select(GeneratedResource).where(
                GeneratedResource.id == resource_id,
                GeneratedResource.user_id == user_id,
            )
        )

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None:
        return self.db.scalar(
            select(KnowledgePoint).where(
                KnowledgePoint.id == knowledge_point_id,
                KnowledgePoint.course_id == course_id,
            )
        )

    def find_knowledge_point_for_topic(self, course_id: int, topic: str) -> KnowledgePoint | None:
        topic_key = self._topic_key(topic)
        if not topic_key:
            return None
        points = list(
            self.db.scalars(
                select(KnowledgePoint)
                .where(KnowledgePoint.course_id == course_id)
                .order_by(KnowledgePoint.order_index.asc(), KnowledgePoint.id.asc())
            )
        )
        exact = next((point for point in points if self._topic_key(point.title) == topic_key), None)
        if exact is not None:
            return exact
        candidates = [
            point
            for point in points
            if self._topic_key(point.title)
            and (self._topic_key(point.title) in topic_key or topic_key in self._topic_key(point.title))
        ]
        return max(candidates, key=lambda point: len(self._topic_key(point.title)), default=None)

    @staticmethod
    def _topic_key(value: object) -> str:
        return "".join(character for character in str(value or "").casefold() if character.isalnum())

    def list_messages(self, session_id: int) -> list[ChatMessage]:
        return list(
            self.db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            )
        )

    def get_assistant_message(self, user_id: int, session_id: int, message_id: int) -> ChatMessage | None:
        return self.db.scalar(
            select(ChatMessage).where(
                ChatMessage.id == message_id,
                ChatMessage.session_id == session_id,
                ChatMessage.user_id == user_id,
                ChatMessage.role == "assistant",
            )
        )

    def add_session(self, session: ChatSession) -> None:
        self.db.add(session)

    def add_message(self, message: ChatMessage) -> None:
        self.db.add(message)

    def pending_attachments(
        self, user_id: int, session_id: int, attachment_ids: list[int]
    ) -> list[ChatMessageAttachment]:
        if not attachment_ids:
            return []
        return list(
            self.db.scalars(
                select(ChatMessageAttachment)
                .where(
                    ChatMessageAttachment.id.in_(attachment_ids),
                    ChatMessageAttachment.user_id == user_id,
                    ChatMessageAttachment.session_id == session_id,
                    ChatMessageAttachment.status == "pending",
                    ChatMessageAttachment.message_id.is_(None),
                )
                .order_by(ChatMessageAttachment.id.asc())
            )
        )

    def bind_attachments(self, attachments: list[ChatMessageAttachment], message_id: int) -> None:
        for attachment in attachments:
            attachment.message_id = message_id
            attachment.status = "bound"
            attachment.expires_at = None
            self.db.add(attachment)

    def attachment_map(self, message_ids: list[int]) -> dict[int, list[ChatMessageAttachment]]:
        if not message_ids:
            return {}
        result: dict[int, list[ChatMessageAttachment]] = {}
        for attachment in self.db.scalars(
            select(ChatMessageAttachment)
            .where(ChatMessageAttachment.message_id.in_(message_ids))
            .order_by(ChatMessageAttachment.created_at.asc(), ChatMessageAttachment.id.asc())
        ):
            if attachment.message_id is not None:
                result.setdefault(attachment.message_id, []).append(attachment)
        return result

    def resource_job_map(self, user_id: int, message_ids: list[int]) -> dict[int, list[TutorResourceJob]]:
        if not message_ids:
            return {}

        messages = list(
            self.db.scalars(
                select(ChatMessage).where(
                    ChatMessage.id.in_(message_ids),
                    ChatMessage.user_id == user_id,
                )
            )
        )
        job_ids = {
            int(job_id)
            for message in messages
            for job_id in (message.resource_job_ids or [])
            if str(job_id).isdigit()
        }
        jobs = (
            {
                job.id: job
                for job in self.db.scalars(
                    select(AiJob).where(AiJob.user_id == user_id, AiJob.id.in_(job_ids))
                )
            }
            if job_ids
            else {}
        )
        resource_ids = {
            int(resource_id)
            for job in jobs.values()
            for resource_id in (job.result_json or {}).get("resource_ids", [])
            if str(resource_id).isdigit()
        }
        resources = (
            {
                resource.id: resource
                for resource in self.db.scalars(
                    select(GeneratedResource).where(
                        GeneratedResource.user_id == user_id,
                        GeneratedResource.id.in_(resource_ids),
                    )
                )
            }
            if resource_ids
            else {}
        )

        result: dict[int, list[TutorResourceJob]] = {}
        for message in messages:
            message_jobs = [
                self._resource_job_to_api(jobs[int(job_id)], resources)
                for job_id in message.resource_job_ids or []
                if str(job_id).isdigit() and int(job_id) in jobs
            ]
            if message_jobs:
                result[message.id] = message_jobs
        return result

    @staticmethod
    def _resource_job_to_api(
        job: AiJob,
        resources: dict[int, GeneratedResource],
    ) -> TutorResourceJob:
        linked_resources = [
            resources[int(resource_id)]
            for resource_id in (job.result_json or {}).get("resource_ids", [])
            if str(resource_id).isdigit() and int(resource_id) in resources
        ]
        return TutorResourceJob(
            job_id=str(job.id),
            status=job.status,
            label=job.label,
            error_message=job.error_message,
            resources=[
                TutorGeneratedResource(
                    id=str(resource.id),
                    title=resource.title,
                    resource_type=resource.resource_type,
                    course_id=str(resource.course_id) if resource.course_id is not None else None,
                )
                for resource in linked_resources
            ],
        )

    def register_resource_job(self, user_id: int, session_id: int, message_id: int, job_id: int) -> None:
        self.link_resource_job(user_id, session_id, message_id, job_id)
        self.db.commit()

    def link_resource_job(self, user_id: int, session_id: int, message_id: int, job_id: int) -> None:
        message = self.db.scalar(
            select(ChatMessage)
            .where(
                ChatMessage.id == message_id,
                ChatMessage.session_id == session_id,
                ChatMessage.user_id == user_id,
                ChatMessage.role == "assistant",
            )
            .with_for_update()
        )
        if message is None:
            raise SessionNotFoundError("回答不存在或无权访问。")
        message.resource_job_ids = list(dict.fromkeys([*(message.resource_job_ids or []), job_id]))
        self.db.add(message)

    def bound_attachments(
        self, user_id: int, session_id: int, message_ids: list[int]
    ) -> list[ChatMessageAttachment]:
        if not message_ids:
            return []
        return list(
            self.db.scalars(
                select(ChatMessageAttachment)
                .where(
                    ChatMessageAttachment.user_id == user_id,
                    ChatMessageAttachment.session_id == session_id,
                    ChatMessageAttachment.message_id.in_(message_ids),
                    ChatMessageAttachment.status == "bound",
                )
                .order_by(ChatMessageAttachment.created_at.desc(), ChatMessageAttachment.id.desc())
                .limit(3)
            )
        )

    def add_agent_log(self, log: AgentRunLog) -> None:
        self.db.add(log)

    def list_home_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        if not material_ids:
            return []
        unique_ids = list(dict.fromkeys(material_ids))[:10]
        return list(
            self.db.scalars(
                select(Material).where(
                    Material.user_id == user_id,
                    Material.id.in_(unique_ids),
                    Material.parse_status == "completed",
                    Material.ingestion_status == "confirmed",
                )
            )
        )

    def touch_session(self, session: ChatSession) -> None:
        session.updated_at = datetime.now(UTC)
        self.db.add(session)

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
