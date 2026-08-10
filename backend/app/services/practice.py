from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from typing import Protocol

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.services.paths import PathReplanResult
from backend.app.services.learner_context import context_service_from_repository
from backend.app.models import (
    Course,
    GeneratedResource,
    KnowledgeChunk,
    KnowledgePoint,
    PracticeAnswer,
    PracticeSession,
    StudentProfile,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.practice import PracticeSessionDetail, PracticeSessionSummary, SubmitPracticeAnswerItem, session_to_api, session_to_summary


class PracticeNotFoundError(Exception):
    pass


class PracticeValidationError(Exception):
    pass


class PracticeGenerationError(PracticeValidationError):
    pass


class PracticeModelService(Protocol):
    def chat_completion_for_task(self, user: User, messages: list[dict[str, str]], profile: ModelTaskProfile) -> str: ...


class PracticePathService(Protocol):
    def replan_after_assessment(self, user: User, course_id: int, assessment_session_id: int) -> PathReplanResult: ...


class PracticeProfileService(Protocol):
    def ingest_learning_signal(
        self,
        *,
        user: User,
        source_type: str,
        source_ref_type: str,
        source_ref_id: int,
        suggested_updates: dict[str, object],
        suggested_confidence: dict[str, float] | None = None,
        course_id: int | None = None,
        parent_trace_id: str | None = None,
    ) -> object | None: ...


class PracticeRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]: ...

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]: ...

    def add_practice_session(self, session: PracticeSession) -> PracticeSession: ...

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None: ...

    def get_latest_practice_session_for_user(self, user_id: int, course_id: int) -> PracticeSession | None: ...

    def list_recent_completed_practice_sessions(self, user_id: int, course_id: int, limit: int = 5) -> list[PracticeSession]: ...

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]: ...

    def list_answers_for_course(self, user_id: int, course_id: int) -> list[PracticeAnswer]: ...

    def get_profile(self, user_id: int) -> StudentProfile | None: ...

    def replace_answers_for_session(self, session_id: int, answers: list[PracticeAnswer]) -> list[PracticeAnswer]: ...

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]: ...

    def add_weakness_review_item(self, item: WeaknessReviewItem) -> WeaknessReviewItem: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class SqlAlchemyPracticeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint).where(KnowledgePoint.course_id == course_id).order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return list(
            self.db.scalars(
                select(GeneratedResource)
                .where(GeneratedResource.user_id == user_id, GeneratedResource.course_id == course_id)
                .order_by(GeneratedResource.updated_at.desc(), GeneratedResource.id.desc())
            )
        )

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        return list(
            self.db.scalars(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.course_id == course_id)
                .order_by(KnowledgeChunk.knowledge_point_id, KnowledgeChunk.id)
            )
        )

    def add_practice_session(self, session: PracticeSession) -> PracticeSession:
        self.db.add(session)
        self.db.flush()
        return session

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None:
        return self.db.scalar(select(PracticeSession).where(PracticeSession.id == session_id, PracticeSession.user_id == user_id))

    def get_latest_practice_session_for_user(self, user_id: int, course_id: int) -> PracticeSession | None:
        return self.db.scalar(
            select(PracticeSession)
            .where(PracticeSession.user_id == user_id, PracticeSession.course_id == course_id)
            .order_by(case((PracticeSession.status == "in_progress", 0), else_=1), PracticeSession.updated_at.desc(), PracticeSession.id.desc())
            .limit(1)
        )

    def list_recent_completed_practice_sessions(self, user_id: int, course_id: int, limit: int = 5) -> list[PracticeSession]:
        return list(
            self.db.scalars(
                select(PracticeSession)
                .where(
                    PracticeSession.user_id == user_id,
                    PracticeSession.course_id == course_id,
                    PracticeSession.status == "completed",
                )
                .order_by(PracticeSession.updated_at.desc(), PracticeSession.id.desc())
                .limit(limit)
            )
        )

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]:
        return list(self.db.scalars(select(PracticeAnswer).where(PracticeAnswer.session_id == session_id).order_by(PracticeAnswer.id)))

    def list_answers_for_course(self, user_id: int, course_id: int) -> list[PracticeAnswer]:
        return list(
            self.db.scalars(
                select(PracticeAnswer)
                .join(PracticeSession, PracticeSession.id == PracticeAnswer.session_id)
                .where(PracticeAnswer.user_id == user_id, PracticeSession.course_id == course_id, PracticeSession.status == "completed")
                .order_by(PracticeAnswer.created_at.desc(), PracticeAnswer.id.desc())
            )
        )

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def replace_answers_for_session(self, session_id: int, answers: list[PracticeAnswer]) -> list[PracticeAnswer]:
        for answer in self.list_answers_for_session(session_id):
            self.db.delete(answer)
        self.db.flush()
        for answer in answers:
            self.db.add(answer)
        self.db.flush()
        return answers

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return list(
            self.db.scalars(select(WeaknessReviewItem).where(WeaknessReviewItem.user_id == user_id, WeaknessReviewItem.course_id == course_id))
        )

    def add_weakness_review_item(self, item: WeaknessReviewItem) -> WeaknessReviewItem:
        self.db.add(item)
        self.db.flush()
        return item

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)


@dataclass(frozen=True)
class EvaluatedAnswer:
    question: dict
    answer_text: str
    is_correct: bool | None
    feedback: dict


class PracticeService:
    valid_difficulties = {"easy", "medium", "hard", "adaptive"}

    def __init__(
        self,
        repository: PracticeRepository,
        model_service: PracticeModelService | None = None,
        trace_recorder: AgentTraceRecorder | None = None,
        path_service: PracticePathService | None = None,
        profile_service: PracticeProfileService | None = None,
    ) -> None:
        self.repository = repository
        self.model_service = model_service
        self.trace_recorder = trace_recorder
        self.path_service = path_service
        self.profile_service = profile_service

    def create_session(
        self,
        user: User,
        course_id: int,
        knowledge_point_ids: list[int],
        question_count: int,
        difficulty: str,
        weakness_item_id: int | None = None,
    ) -> PracticeSessionDetail:
        if question_count < 1 or question_count > 12:
            raise PracticeValidationError("题目数量必须在 1 到 12 之间。")
        if difficulty not in self.valid_difficulties:
            raise PracticeValidationError("练习难度只能是 adaptive、easy、medium 或 hard。")
        from backend.app.agents.assessment import AssessmentGraphRunner

        return AssessmentGraphRunner(self).create_session(
            user=user,
            course_id=course_id,
            knowledge_point_ids=knowledge_point_ids,
            weakness_item_id=weakness_item_id,
            question_count=question_count,
            difficulty=difficulty,
        )

    def get_session(self, user: User, session_id: int) -> PracticeSessionDetail:
        session = self._require_session(user, session_id)
        return session_to_api(session, self.repository.list_answers_for_session(session.id))

    def get_latest_session(self, user: User, course_id: int) -> PracticeSessionDetail | None:
        self._require_course(user, course_id)
        session = self.repository.get_latest_practice_session_for_user(user.id, course_id)
        if session is None:
            return None
        return session_to_api(session, self.repository.list_answers_for_session(session.id))

    def list_recent_completed_sessions(self, user: User, course_id: int, limit: int = 5) -> list[PracticeSessionSummary]:
        self._require_course(user, course_id)
        return [session_to_summary(session) for session in self.repository.list_recent_completed_practice_sessions(user.id, course_id, limit)]

    def save_draft(
        self,
        user: User,
        session_id: int,
        answers: list[SubmitPracticeAnswerItem | dict],
    ) -> PracticeSessionDetail:
        session = self._require_session(user, session_id)
        if session.status != "in_progress":
            raise PracticeValidationError("已完成练习不能修改草稿。")
        rows = self.repository.list_answers_for_session(session.id)
        by_question = {str((row.question_json or {}).get("id") or ""): row for row in rows}
        submitted: dict[str, str] = {}
        for item in answers:
            payload = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            question_id = str(payload.get("question_id") or "")
            if question_id not in by_question:
                raise PracticeValidationError("草稿包含不属于当前练习的题目。")
            submitted[question_id] = " ".join(str(payload.get("answer_text") or "").split())[:2000]
        for question_id, answer_text in submitted.items():
            by_question[question_id].answer_text = answer_text
            by_question[question_id].feedback_json = {}
            by_question[question_id].is_correct = None
        now = datetime.now(UTC)
        session.assessment_json = {**(session.assessment_json or {}), "draft_saved_at": now.isoformat().replace("+00:00", "Z")}
        session.updated_at = now
        try:
            self.repository.commit()
            self.repository.refresh(session)
        except Exception:
            self.repository.rollback()
            raise
        return session_to_api(session, self.repository.list_answers_for_session(session.id))

    def submit_answers(
        self,
        user: User,
        session_id: int,
        answers: list[SubmitPracticeAnswerItem | dict],
    ) -> PracticeSessionDetail:
        from backend.app.agents.assessment import AssessmentGraphRunner

        return AssessmentGraphRunner(self).submit_answers(user=user, session_id=session_id, answers=answers)

    def regrade_answers(self, user: User, session_id: int) -> PracticeSessionDetail:
        from backend.app.agents.assessment import AssessmentGraphRunner

        return AssessmentGraphRunner(self).regrade_answers(user=user, session_id=session_id)

    def resolve_difficulty(self, user: User, course_id: int, points: list[KnowledgePoint], requested: str) -> str:
        if requested != "adaptive":
            return requested
        point_ids = {point.id for point in points}
        weaknesses = self.repository.list_weakness_review_items(user.id, course_id)
        if any(item.status in {"confirmed", "reviewing"} and item.knowledge_point_id in point_ids for item in weaknesses):
            return "easy"
        answers = self.repository.list_answers_for_course(user.id, course_id)
        scores: list[int] = []
        for answer in answers:
            question = answer.question_json or {}
            if question.get("knowledge_point_id") not in point_ids:
                continue
            feedback = answer.feedback_json or {}
            if feedback.get("score") is not None:
                scores.append(int(feedback["score"]))
            if len(scores) >= max(3, len(points) * 2):
                break
        if scores:
            average = sum(scores) / len(scores)
            if average < 45:
                return "easy"
            if average < 75:
                return "medium"
            context_service = context_service_from_repository(self.repository)
            global_context = context_service.global_context(user.id) if context_service is not None else None
            profile = self.repository.get_profile(user.id)
            foundation = str(
                global_context.trusted_value("knowledge_foundation")
                if global_context is not None
                else (profile.profile_json if profile is not None else {}).get("knowledge_foundation") or ""
            )
            return "medium" if any(word in foundation for word in ("入门", "薄弱", "刚开始")) else "hard"
        context_service = context_service_from_repository(self.repository)
        global_context = context_service.global_context(user.id) if context_service is not None else None
        profile = self.repository.get_profile(user.id)
        foundation = str(
            global_context.trusted_value("knowledge_foundation")
            if global_context is not None
            else (profile.profile_json if profile is not None else {}).get("knowledge_foundation") or ""
        )
        if any(word in foundation for word in ("入门", "薄弱", "刚开始")):
            return "easy"
        if any(word in foundation for word in ("扎实", "熟练", "基础较稳")):
            return "hard"
        return "medium"

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise PracticeNotFoundError("课程不存在或无权访问。")
        return course

    def _require_session(self, user: User, session_id: int) -> PracticeSession:
        session = self.repository.get_practice_session_for_user(user.id, session_id)
        if session is None:
            raise PracticeNotFoundError("练习不存在或无权访问。")
        return session

    def _select_points(self, points: list[KnowledgePoint], knowledge_point_ids: list[int]) -> list[KnowledgePoint]:
        if not knowledge_point_ids:
            return points
        selected_ids = list(dict.fromkeys(knowledge_point_ids))
        by_id = {point.id: point for point in points}
        if any(point_id not in by_id for point_id in selected_ids):
            raise PracticeNotFoundError("知识点不存在或不属于当前课程。")
        return [by_id[point_id] for point_id in selected_ids]

    def _build_questions(
        self,
        points: list[KnowledgePoint],
        resources: list[GeneratedResource],
        question_count: int,
        difficulty: str,
        chunks: list[KnowledgeChunk] | None = None,
    ) -> list[dict]:
        if not points:
            return []
        chunks = chunks or []
        evidence_by_point = {
            point.id: self._evidence_for_point(point, chunks, resources)
            for point in points
        }
        all_statements = [
            (point_id, row["text"])
            for point_id, rows in evidence_by_point.items()
            for row in rows
        ]
        questions: list[dict] = []
        question_types = (
            ["short_answer"]
            if question_count == 1
            else ["single_choice", "multiple_choice", "short_answer"]
        )
        for index in range(question_count):
            point = points[index % len(points)]
            evidence = evidence_by_point[point.id]
            target_statements = [row["text"] for row in evidence]
            distractors = [text for point_id, text in all_statements if point_id != point.id and text not in target_statements]
            requested_type = question_types[index % len(question_types)]
            question_type = requested_type
            if question_type in {"single_choice", "multiple_choice"} and len(distractors) < 3:
                distractors = [*distractors, *self._safe_distractors(point, target_statements)]
                distractors = list(dict.fromkeys(distractors))
            keywords = self._keywords_for_evidence(point, " ".join(target_statements))
            question_id = f"q{index + 1}"
            focus = ("概念含义", "关键关系", "应用条件", "推导思路", "常见误区", "实际应用")[index % 6]
            citation_refs = [str(row["chunk_id"]) for row in evidence if row["chunk_id"] is not None][:3]
            statement_index = (index + index // len(question_types)) % len(target_statements)
            source_excerpt = target_statements[statement_index]
            required_scope_term = self._short_answer_scope_term(source_excerpt)
            base = {
                "id": question_id,
                "question_type": question_type,
                "knowledge_point_id": str(point.id),
                "knowledge_point_title": point.title,
                "keywords": keywords,
                "difficulty": difficulty,
                "explanation": f"课程证据指出：{source_excerpt}",
                "source_summary": source_excerpt,
                "source_excerpt": source_excerpt,
                "required_scope_term": required_scope_term,
                "citation_refs": citation_refs,
                "prompt_version": "assessment-v3.3",
                "generation_mode": "deterministic_source",
                "quality": {"evidence_bound": bool(citation_refs), "answer_locked": True},
            }
            if question_type == "single_choice":
                correct = source_excerpt
                options = [correct, *distractors[:3]]
                rotation = index % len(options)
                options = options[rotation:] + options[:rotation]
                questions.append(
                    {
                        **base,
                        "prompt": f"根据课程资料，哪一项最准确地描述“{point.title}”？",
                        "options": options,
                        "correct_answer": correct,
                    }
                )
            elif question_type == "multiple_choice":
                correct = [
                    target_statements[(statement_index + offset) % len(target_statements)]
                    for offset in range(min(2, len(target_statements)))
                ]
                options = [*correct, *distractors[: max(0, 4 - len(correct))]]
                rotation = index % len(options)
                options = options[rotation:] + options[:rotation]
                questions.append(
                    {
                        **base,
                        "prompt": f"根据课程资料，哪些表述直接属于“{point.title}”？",
                        "options": options,
                        "correct_answer": correct,
                    }
                )
            else:
                answer_scope = required_scope_term or point.title
                if answer_scope == point.title:
                    prompt = (
                        f"请从{focus}角度说明“{answer_scope}”的核心含义，"
                        "并结合课程范围内的具体情境解释这一认识为何重要。"
                    )
                else:
                    prompt = f"请从{focus}角度解释“{answer_scope}”，并说明它与“{point.title}”的关系。"
                questions.append(
                    {
                        **base,
                        "prompt": prompt,
                        "options": [],
                        "correct_answer": source_excerpt,
                        "keywords": keywords[:3],
                    }
                )
        return questions

    @staticmethod
    def _short_answer_scope_term(source_excerpt: str) -> str:
        """提取简答题必须点名的最小作答对象，避免开放题干配合唯一参考答案。"""
        normalized = " ".join(str(source_excerpt or "").split()).strip("，。；：:、 \t\r\n")
        if not normalized:
            return ""
        prefix = re.split(
            r"(?:是指|指的是|是|描述|关注|表示|用于|体现|包括|反映|说明|强调|要求|具有|衡量|估计)",
            normalized,
            maxsplit=1,
        )[0].strip("，。；：:、 \t\r\n")
        if 2 <= len(prefix) <= 24:
            return prefix
        return ""

    @staticmethod
    def _safe_distractors(point: KnowledgePoint, statements: list[str]) -> list[str]:
        topic = point.title
        return [
            f"“{topic}”只研究彼此孤立的对象，不考虑对象之间的联系。",
            f"“{topic}”只关注具体实现细节，不涉及抽象关系或适用条件。",
            f"“{topic}”与实际问题情境无关，任何场景都应采用同一种处理方式。",
        ]

    @staticmethod
    def _keywords_for_evidence(point: KnowledgePoint, evidence: str) -> list[str]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_*+()\-]{1,24}|[一-龥]{2,8}", f"{point.title} {point.summary or ''} {evidence}")
        keywords = list(dict.fromkeys([point.title, *tokens]))
        return (keywords + ["核心关系", "应用条件", "推导过程"])[:4]

    @classmethod
    def _evidence_for_point(
        cls,
        point: KnowledgePoint,
        chunks: list[KnowledgeChunk],
        resources: list[GeneratedResource],
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for chunk in chunks:
            if chunk.knowledge_point_id != point.id:
                continue
            for sentence in cls._sentences(chunk.content):
                rows.append({"chunk_id": chunk.id, "text": sentence})
                if len(rows) >= 3:
                    return rows
        fallback = point.summary or next(
            (resource.title for resource in resources if resource.knowledge_point_id == point.id),
            point.title,
        )
        sentences = cls._sentences(fallback)
        return [{"chunk_id": None, "text": sentence} for sentence in sentences[:3]] or [{"chunk_id": None, "text": point.title}]

    @staticmethod
    def _sentences(content: str) -> list[str]:
        sentences = [" ".join(item.split())[:220] for item in re.split(r"[。！？!?；;\n]+", str(content or ""))]
        return list(dict.fromkeys(item for item in sentences if len(item) >= 8))

    @staticmethod
    def _normalize_answers(answers: list[SubmitPracticeAnswerItem | dict]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for answer in answers:
            if isinstance(answer, SubmitPracticeAnswerItem):
                normalized.append({"question_id": answer.question_id, "answer_text": answer.answer_text})
            else:
                normalized.append(
                    {
                        "question_id": str(answer.get("question_id") or ""),
                        "answer_text": str(answer.get("answer_text") or ""),
                    }
                )
        return normalized

    def _evaluate_answer(self, question: dict, answer_text: str) -> EvaluatedAnswer:
        question_type = question.get("question_type")
        keywords = [str(item) for item in question.get("keywords") or []]
        matched = [keyword for keyword in keywords if keyword and keyword.casefold() in answer_text.casefold()]
        if question_type == "single_choice":
            expected = str(question.get("correct_answer") or "")
            is_correct = answer_text.strip().casefold() == expected.casefold()
            score = 100 if is_correct else 0
        elif question_type == "multiple_choice":
            expected_values = [str(item) for item in question.get("correct_answer") or []]
            normalized_answer = {part.strip().casefold() for part in answer_text.replace("，", ",").split(",") if part.strip()}
            normalized_expected = {part.casefold() for part in expected_values}
            is_correct = normalized_expected.issubset(normalized_answer)
            score = 100 if is_correct else round(100 * len(normalized_expected.intersection(normalized_answer)) / max(len(normalized_expected), 1))
        else:
            return EvaluatedAnswer(
                question=question,
                answer_text=answer_text,
                is_correct=None,
                feedback={
                    "score": None,
                    "grading_status": "ungraded",
                    "message": "简答题暂未评分，可稍后重试。",
                    "matched_concepts": [],
                    "missing_concepts": [],
                    "confidence": None,
                    "matched_keywords": [],
                    "missing_keywords": [],
                    "explanation": str(question.get("explanation") or ""),
                },
            )
        missing = [keyword for keyword in keywords[:3] if keyword not in matched]
        feedback = {
            "score": score,
            "grading_status": "deterministic",
            "message": "已掌握关键依据。" if is_correct else "这道题暴露了需要复习的知识点。",
            "matched_concepts": [],
            "missing_concepts": [],
            "confidence": 1.0,
            "matched_keywords": matched,
            "missing_keywords": missing,
            "explanation": str(question.get("explanation") or ""),
        }
        return EvaluatedAnswer(question=question, answer_text=answer_text, is_correct=is_correct, feedback=feedback)

    def _sync_practice_weaknesses(self, user: User, session: PracticeSession, evaluated: list[EvaluatedAnswer]) -> None:
        existing = self.repository.list_weakness_review_items(user.id, int(session.course_id or 0))
        existing_point_ids = {item.knowledge_point_id for item in existing if item.knowledge_point_id is not None}
        existing_titles = {" ".join(item.title.split()).casefold() for item in existing}
        for item in evaluated:
            if item.feedback["score"] >= 60:
                continue
            point_id = self._safe_int(item.question.get("knowledge_point_id"))
            title = str(item.question.get("knowledge_point_title") or "练习薄弱点")[:120]
            normalized_title = " ".join(title.split()).casefold()
            if point_id is not None and point_id in existing_point_ids:
                continue
            if point_id is None and normalized_title in existing_titles:
                continue
            now = datetime.now(UTC)
            self.repository.add_weakness_review_item(
                WeaknessReviewItem(
                    user_id=user.id,
                    course_id=session.course_id,
                    knowledge_point_id=point_id,
                    title=title,
                    source_type="practice_assessment",
                    status="confirmed",
                    recommended_resource_ids=[],
                    next_review_at=now + timedelta(days=3),
                    created_at=now,
                    updated_at=now,
                )
            )
            if point_id is not None:
                existing_point_ids.add(point_id)
            existing_titles.add(normalized_title)

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
