from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.errors import make_trace_id
from backend.app.models import (
    Course,
    GeneratedResource,
    KnowledgePoint,
    PracticeAnswer,
    PracticeSession,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.practice import PracticeSessionDetail, SubmitPracticeAnswerItem, session_to_api


class PracticeNotFoundError(Exception):
    pass


class PracticeValidationError(Exception):
    pass


class PracticeRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]: ...

    def add_practice_session(self, session: PracticeSession) -> PracticeSession: ...

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None: ...

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]: ...

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

    def add_practice_session(self, session: PracticeSession) -> PracticeSession:
        self.db.add(session)
        self.db.flush()
        return session

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None:
        return self.db.scalar(select(PracticeSession).where(PracticeSession.id == session_id, PracticeSession.user_id == user_id))

    def list_answers_for_session(self, session_id: int) -> list[PracticeAnswer]:
        return list(self.db.scalars(select(PracticeAnswer).where(PracticeAnswer.session_id == session_id).order_by(PracticeAnswer.id)))

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
    is_correct: bool
    feedback: dict


class PracticeService:
    valid_difficulties = {"easy", "medium", "hard"}

    def __init__(self, repository: PracticeRepository) -> None:
        self.repository = repository

    def create_session(
        self,
        user: User,
        course_id: int,
        knowledge_point_ids: list[int],
        question_count: int,
        difficulty: str,
    ) -> PracticeSessionDetail:
        if question_count < 1 or question_count > 12:
            raise PracticeValidationError("题目数量必须在 1 到 12 之间。")
        if difficulty not in self.valid_difficulties:
            raise PracticeValidationError("练习难度只能是 easy、medium 或 hard。")

        course = self._require_course(user, course_id)
        points = self.repository.list_knowledge_points(course.id)
        selected_points = self._select_points(points, knowledge_point_ids)
        resources = self.repository.list_generated_resources(user.id, course.id)
        questions = self._build_questions(selected_points, resources, question_count, difficulty)
        if not questions:
            raise PracticeValidationError("当前课程还没有可用于生成练习的知识点。")

        agent_trace_id = make_trace_id()
        now = datetime.now(UTC)
        session = PracticeSession(
            user_id=user.id,
            course_id=course.id,
            title=f"{course.title} 练习",
            status="in_progress",
            agent_trace_id=agent_trace_id,
            score=None,
            created_at=now,
            updated_at=now,
        )
        try:
            self.repository.add_practice_session(session)
            placeholders = [
                PracticeAnswer(
                    session_id=session.id,
                    user_id=user.id,
                    question_json=question,
                    answer_text=None,
                    feedback_json={},
                    is_correct=None,
                    created_at=now,
                )
                for question in questions
            ]
            self.repository.replace_answers_for_session(session.id, placeholders)
            self.repository.commit()
            self.repository.refresh(session)
        except Exception:
            self.repository.rollback()
            raise
        return session_to_api(session, self.repository.list_answers_for_session(session.id))

    def get_session(self, user: User, session_id: int) -> PracticeSessionDetail:
        session = self._require_session(user, session_id)
        return session_to_api(session, self.repository.list_answers_for_session(session.id))

    def submit_answers(
        self,
        user: User,
        session_id: int,
        answers: list[SubmitPracticeAnswerItem | dict],
    ) -> PracticeSessionDetail:
        session = self._require_session(user, session_id)
        existing_answers = self.repository.list_answers_for_session(session.id)
        questions = [answer.question_json for answer in existing_answers if isinstance(answer.question_json, dict)]
        if not questions:
            raise PracticeValidationError("练习题目不存在。")
        normalized_answers = self._normalize_answers(answers)
        by_id = {question["id"]: question for question in questions}
        evaluated: list[EvaluatedAnswer] = []
        for answer in normalized_answers:
            question = by_id.get(answer["question_id"])
            if question is None:
                raise PracticeValidationError("提交的题目不属于当前练习。")
            answer_text = " ".join(str(answer["answer_text"]).split())
            if not answer_text:
                raise PracticeValidationError("答案不能为空。")
            evaluated.append(self._evaluate_answer(question, answer_text))

        if not evaluated:
            raise PracticeValidationError("至少提交一道题。")

        now = datetime.now(UTC)
        if not session.agent_trace_id:
            session.agent_trace_id = make_trace_id()
        score = round(sum(item.feedback["score"] for item in evaluated) / len(evaluated))
        practice_answers = [
            PracticeAnswer(
                session_id=session.id,
                user_id=user.id,
                question_json=item.question,
                answer_text=item.answer_text,
                feedback_json=item.feedback,
                is_correct=item.is_correct,
                created_at=now,
            )
            for item in evaluated
        ]

        try:
            self.repository.replace_answers_for_session(session.id, practice_answers)
            session.status = "completed"
            session.score = Decimal(str(score))
            session.updated_at = now
            self._sync_practice_weaknesses(user, session, evaluated)
            self.repository.commit()
            self.repository.refresh(session)
        except Exception:
            self.repository.rollback()
            raise

        return session_to_api(session, self.repository.list_answers_for_session(session.id))

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
    ) -> list[dict]:
        if not points:
            return []
        questions: list[dict] = []
        question_types = ["single_choice", "multiple_choice", "short_answer"]
        for index in range(question_count):
            point = points[index % len(points)]
            question_type = question_types[index % len(question_types)]
            keywords = self._keywords_for_point(point)
            resource_title = next((resource.title for resource in resources if resource.knowledge_point_id == point.id), None)
            question_id = f"q{index + 1}"
            base = {
                "id": question_id,
                "question_type": question_type,
                "knowledge_point_id": str(point.id),
                "knowledge_point_title": point.title,
                "keywords": keywords,
                "difficulty": difficulty,
                "explanation": f"复习{point.title}时，需要围绕{keywords[0]}、{keywords[1]}和课程引用说明理解依据。",
                "source_summary": resource_title or point.summary or point.title,
            }
            if question_type == "single_choice":
                questions.append(
                    {
                        **base,
                        "prompt": f"关于{point.title}，哪一项最符合课程复习重点？",
                        "options": [keywords[0], "无关概念", "跳过资料依据", "只背结论"],
                        "correct_answer": keywords[0],
                    }
                )
            elif question_type == "multiple_choice":
                questions.append(
                    {
                        **base,
                        "prompt": f"复习{point.title}时，哪些信息可以作为答题依据？",
                        "options": [keywords[0], keywords[1], "课程引用", "无关提示"],
                        "correct_answer": [keywords[1], "课程引用"],
                    }
                )
            else:
                questions.append(
                    {
                        **base,
                        "prompt": f"请用{keywords[0]}、{keywords[1]}和复习线索解释{point.title}。",
                        "options": [],
                        "correct_answer": "；".join(keywords),
                        "keywords": ["概念", "误区", "复习线索"],
                    }
                )
        return questions

    @staticmethod
    def _keywords_for_point(point: KnowledgePoint) -> list[str]:
        words = [part for part in " ".join([point.title, point.summary or "", point.chapter or ""]).replace("，", " ").replace("。", " ").split() if part]
        keywords = list(dict.fromkeys([point.title, "关键概念", "课程引用", "常见误区", *words]))
        return keywords[:4] if len(keywords) >= 4 else [*keywords, "复习线索"][:4]

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
            score = min(100, round(100 * len(matched) / max(len(keywords[:3]), 1)))
            is_correct = score >= 60
        missing = [keyword for keyword in keywords[:3] if keyword not in matched]
        feedback = {
            "score": score,
            "message": "已掌握关键依据。" if is_correct else "这道题暴露了需要复习的知识点。",
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
