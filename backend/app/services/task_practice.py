"""Import a bound quiz into the existing server-authoritative assessment pipeline."""
from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import ConflictDomainError, NotFoundDomainError, ValidationDomainError
from backend.app.models import GeneratedResource, KnowledgeChunk, LearningTask, PracticeAnswer, PracticeSession, User
from backend.app.schemas.practice import PracticeQuestion, session_to_api
from backend.app.services.paths import PathService, SqlAlchemyPathRepository
from backend.app.services.task_resource_binding import binding_status, exact_item, resource_snapshot


def quiz_questions(resource: GeneratedResource, task: LearningTask, valid_refs: set[int]) -> list[dict]:
    artifact = (resource.content_json or {}).get("artifact") or {}
    if not isinstance(artifact, dict):
        raise ValidationDomainError("测验资源格式无效。")
    raw_questions = artifact.get("questions") or []
    if artifact.get("kind") != "quiz" or not isinstance(raw_questions, list) or not 1 <= len(raw_questions) <= 12:
        raise ValidationDomainError("绑定资源不包含可导入的测验。")
    questions = []
    seen = set()
    for raw in raw_questions:
        if not isinstance(raw, dict):
            raise ValidationDomainError("测验题目格式无效。")
        question_id = str(raw.get("id") or "")
        refs = raw.get("citation_refs") or []
        if not isinstance(refs, list) or not refs or any(not str(ref).isdigit() or int(ref) not in valid_refs for ref in refs):
            raise ValidationDomainError("测验题目引用缺失或不属于当前课程。")
        if not question_id or len(question_id) > 80 or question_id in seen:
            raise ValidationDomainError("测验题目 ID 缺失或重复。")
        seen.add(question_id)
        options = raw.get("options") or []
        if not isinstance(options, list) or any(not isinstance(option, dict) or not option.get("key") or not option.get("text") for option in options):
            raise ValidationDomainError("测验选项格式无效。")
        if any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in ("prompt", "explanation")):
            raise ValidationDomainError("测验题干或解析为空。")
        by_key = {str(option["key"]): str(option["text"]) for option in options}
        answer = raw.get("answer")
        kind = raw.get("type")
        if kind in {"single_choice", "multiple_choice"}:
            keys = answer if isinstance(answer, list) else [answer]
            if (len(by_key) != len(options) or len(options) < 2 or not keys
                    or (kind == "single_choice" and isinstance(answer, list))
                    or any(str(key) not in by_key for key in keys)):
                raise ValidationDomainError("测验答案与选项不一致。")
            answer = [by_key[str(key)] for key in keys] if kind == "multiple_choice" else by_key[str(answer)]
        elif kind != "short_answer" or not isinstance(answer, str) or not answer.strip():
            raise ValidationDomainError("测验题型或参考答案无效。")
        question = PracticeQuestion(
            id=question_id, question_type=kind, knowledge_point_id=str(task.knowledge_point_id) if task.knowledge_point_id else None,
            knowledge_point_title=task.title, prompt=raw.get("prompt", ""), options=list(by_key.values()),
            option_ids=list(by_key), correct_answer=answer, keywords=[], explanation=raw.get("explanation", ""),
            difficulty=(task.learning_bundle_json or {}).get("difficulty", "medium"),
            citation_refs=[str(ref) for ref in refs], generation_mode="bound_resource", prompt_version="bound-quiz-v1",
        ).model_dump()
        if not question["prompt"].strip() or not question["explanation"].strip():
            raise ValidationDomainError("测验题干或解析为空。")
        questions.append(question)
    return questions


class TaskPracticeService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User, task_id: int, resource_id: int):
        try:
            task = self.db.scalar(select(LearningTask).where(LearningTask.id == task_id, LearningTask.user_id == user.id)
                                  .with_for_update().execution_options(populate_existing=True))
            if task is None:
                raise NotFoundDomainError("学习任务不存在或无权访问。")
            repo = SqlAlchemyPathRepository(self.db)
            path = repo.get_path_for_user(user.id, task.path_id)
            PathService(repo)._require_course(user, int(task.course_id or 0))
            if not repo.is_course_active(user.id, int(task.course_id or 0)):
                raise ConflictDomainError("课程已归档，请先恢复学习。")
            if path is None or path.approval_status != "approved":
                raise ConflictDomainError("只有已批准计划的精确资源可以形成任务测验。")
            resource = self.db.scalar(select(GeneratedResource).where(GeneratedResource.id == resource_id, GeneratedResource.user_id == user.id))
            item = exact_item(task, resource_id)
            if item is None or binding_status(task, item, resource) != "verified" or resource.resource_type != "quiz":
                raise ConflictDomainError("测验资源未精确绑定、未通过审核或版本已变化。")
            existing = self.db.scalar(select(PracticeSession).where(
                PracticeSession.user_id == user.id,
                PracticeSession.assessment_json["source_binding"]["task_id"].astext == str(task_id),
                PracticeSession.assessment_json["source_binding"]["resource"]["resource_id"].astext == str(resource_id),
            ).order_by(PracticeSession.id))
            if existing is not None:
                rows = list(self.db.scalars(select(PracticeAnswer).where(PracticeAnswer.session_id == existing.id).order_by(PracticeAnswer.id)))
                result = session_to_api(existing, rows)
                self.db.rollback()
                return result
            valid_refs = set(self.db.scalars(select(KnowledgeChunk.id).where(KnowledgeChunk.course_id == task.course_id)))
            questions = quiz_questions(resource, task, valid_refs)
            provenance = {"schema_version": 1, "path_id": path.id, "task_id": task.id,
                          "resource": resource_snapshot(resource), "grading_contract": "existing_assessment_pipeline",
                          "answer_visibility": "source_resource_contains_reference_answers"}
            session = PracticeSession(user_id=user.id, course_id=task.course_id, title=resource.title[:255], status="in_progress",
                                      assessment_json={"source_binding": provenance, "generation_mode": "bound_resource"})
            self.db.add(session)
            self.db.flush()
            rows = [PracticeAnswer(session_id=session.id, user_id=user.id, question_id=question["id"],
                                   question_json={**deepcopy(question), "source_binding": provenance}, feedback_json={}) for question in questions]
            self.db.add_all(rows)
            self.db.commit()
            return session_to_api(session, rows)
        except Exception:
            self.db.rollback()
            raise
