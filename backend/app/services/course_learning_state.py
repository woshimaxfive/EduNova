from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.models import (
    Course,
    CourseEnrollment,
    GeneratedResource,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    PracticeAnswer,
    ProfileEvent,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.courses import (
    CourseEvidenceSummary,
    CourseKnowledgePoint,
    CourseLearnerContextResponse,
    CourseLearnerProfile,
    CourseLearningState,
    CourseMasteryPoint,
    CourseMasterySummary,
    CoursePathSummary,
    CourseProfileOverlay,
    CourseProfileReadiness,
    CourseStageCompletion,
    CourseSummary,
    CourseWeaknessReviewItem,
    CourseWeaknessSummary,
    iso_timestamp,
    weakness_item_to_api,
)
from backend.app.schemas.profiles import normalize_profile_json
from backend.app.services.course_contracts import (
    CourseNotFoundError,
    CourseWeaknessStateTransitionError,
    WeaknessCandidate,
)
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.mastery_progress import is_review_due, latest_practice_score


class CourseLearningStateMixin:
    def get_learning_state(self, user: User, course_id: int) -> CourseLearningState:
        course = self._require_course(user, course_id)
        candidate_events = self.repository.list_weakness_candidate_events(user.id, course.id)
        self._sync_weakness_review_queue(user, course.id, candidate_events)
        review_items = self.repository.list_weakness_review_items(user.id, course.id)
        resources = self.repository.list_generated_resources(user.id, course.id)
        if self._sync_weakness_resource_recommendations(review_items, resources):
            self.repository.commit()
        profile = self.repository.get_profile(user.id)
        profile_json = normalize_profile_json(profile.profile_json if profile is not None else None)
        latest_event = max(candidate_events, key=lambda event: (event.created_at, event.id), default=None)
        latest_candidate = self._candidate_from_event(latest_event) if latest_event is not None else None
        path = self.repository.get_active_path(user.id, course.id)
        path_tasks = self.repository.list_tasks_for_path(path.id) if path is not None else []
        mastery_points = self._build_mastery_points(
            self.repository.list_knowledge_points(course.id),
            review_items,
            resources,
            self.repository.list_learning_tasks(user.id, course.id),
            self.repository.list_practice_answers(user.id, course.id),
        )
        resources_by_id = {resource.id: resource for resource in resources}
        context_service = context_service_from_repository(self.repository)
        learner_context = context_service.course_context(user.id, course.id) if context_service is not None else None
        active_weaknesses = [item.title for item in review_items if item.status in {"confirmed", "reviewing"}]
        fallback_goal = str(path.goal or "").strip() if path is not None else ""
        effective_goal = learner_context.course_goal if learner_context is not None else (fallback_goal or profile_json["learning_goal"])
        foundation_summary = learner_context.foundation_summary if learner_context is not None else profile_json["knowledge_foundation"]
        effective_weaknesses = list(learner_context.active_weaknesses) if learner_context is not None else active_weaknesses
        global_context = learner_context.global_context if learner_context is not None else None

        return CourseLearningState(
            course_id=str(course.id),
            profile_overlay=CourseProfileOverlay(
                learning_goal=effective_goal,
                knowledge_foundation=foundation_summary,
                weak_points=effective_weaknesses,
            ),
            learner_context=CourseLearnerContextResponse(
                profile_applied_version=global_context.profile_applied_version if global_context is not None else 0,
                context_hash=learner_context.context_hash if learner_context is not None else "legacy",
                completeness_score=global_context.completeness_score if global_context is not None else 0,
                evidence_confidence_score=global_context.evidence_confidence_score if global_context is not None else float(getattr(profile, "confidence_score", 0) or 0),
                trusted_dimensions=list(global_context.trusted_dimensions) if global_context is not None else [],
                advisory_dimensions=list(global_context.advisory_dimensions) if global_context is not None else [],
                course_goal=effective_goal,
                foundation_summary=foundation_summary,
                active_weaknesses=effective_weaknesses,
                mastery_average=learner_context.mastery_average if learner_context is not None else None,
                current_task_title=learner_context.current_task_title if learner_context is not None else None,
                recent_practice_score=learner_context.recent_practice_score if learner_context is not None else None,
                learning_preference=str(global_context.advisory_value("learning_preference") or "") if global_context is not None else "",
                cognitive_style=str(global_context.advisory_value("cognitive_style") or "") if global_context is not None else "",
                learning_pace=str(global_context.advisory_value("learning_pace") or "") if global_context is not None else "",
                motivation_interest=str(global_context.advisory_value("motivation_interest") or "") if global_context is not None else "",
            ),
            weakness_summary=self._build_weakness_summary(candidate_events, review_items),
            weakness_review_queue=[weakness_item_to_api(item, resources_by_id) for item in review_items if item.status != "dismissed"],
            path_summary=self._build_path_summary(path, path_tasks),
            mastery_summary=self._build_mastery_summary(mastery_points),
            evidence_summary=CourseEvidenceSummary(
                candidate_event_count=len(candidate_events),
                latest_trace_id=latest_candidate.trace_id if latest_candidate is not None else None,
                latest_source_title=latest_candidate.source_title if latest_candidate is not None else None,
                latest_section_title=latest_candidate.section_title if latest_candidate is not None else None,
            ),
            course_profile_readiness=self._course_profile(user.id, course.id, self._require_enrollment(user.id, course.id)).readiness,
            stage_completion=self._stage_completion(user, course.id, mastery_points=mastery_points),
        )

    def update_weakness_review_item(
        self,
        user: User,
        course_id: int,
        item_id: int,
        action: str,
    ) -> CourseWeaknessReviewItem:
        course = self._require_course(user, course_id)
        if self._require_enrollment(user.id, course.id).learning_status == "archived":
            raise CourseWeaknessStateTransitionError("课程已完成归档；请先恢复学习再更新薄弱点。")
        item = self.repository.get_weakness_review_item(user.id, course.id, item_id)
        if item is None:
            raise CourseNotFoundError("弱点复习项不存在或无权访问。")

        if action not in self.weakness_action_target_status:
            raise CourseWeaknessStateTransitionError("不支持的弱点复习操作。")

        allowed_actions = self.weakness_allowed_actions.get(item.status, set())
        if action not in allowed_actions:
            raise CourseWeaknessStateTransitionError("当前状态不允许执行这个操作。")

        target_status = self.weakness_action_target_status[action]
        if item.status == target_status:
            return weakness_item_to_api(item)

        try:
            item.status = target_status
            if target_status == "completed":
                item.next_review_at = datetime.now(UTC) + timedelta(days=7)
            item.updated_at = datetime.now(UTC)
            self.repository.commit()
            self.repository.refresh(item)
        except Exception:
            self.repository.rollback()
            raise

        return weakness_item_to_api(item)

    def _sync_weakness_review_queue(self, user: User, course_id: int, candidate_events: list[ProfileEvent]) -> None:
        existing_items = self.repository.list_weakness_review_items_for_update(user.id, course_id)
        existing_knowledge_point_ids = {item.knowledge_point_id for item in existing_items if item.knowledge_point_id is not None}
        existing_titles = {self._normalize_weakness_title(item.title) for item in existing_items if item.title.strip()}
        created_any = False

        try:
            for event in sorted(candidate_events, key=lambda item: (item.created_at, item.id)):
                candidate = self._candidate_from_event(event)
                if candidate is None:
                    continue

                normalized_title = self._normalize_weakness_title(candidate.title)
                if candidate.knowledge_point_id is not None:
                    if candidate.knowledge_point_id in existing_knowledge_point_ids:
                        continue
                    existing_knowledge_point_ids.add(candidate.knowledge_point_id)
                elif normalized_title in existing_titles:
                    continue

                now = datetime.now(UTC)
                self.repository.add_weakness_review_item(
                    WeaknessReviewItem(
                        user_id=user.id,
                        course_id=course_id,
                        knowledge_point_id=candidate.knowledge_point_id,
                        title=candidate.title,
                        source_type="course_question",
                        status="pending",
                        recommended_resource_ids=[],
                        next_review_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                existing_titles.add(normalized_title)
                created_any = True

            if created_any:
                self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

    def _base_profile_ready(self, user_id: int) -> bool:
        profile = self.repository.get_profile(user_id)
        if profile is None:
            return False
        values = normalize_profile_json(profile.profile_json)
        confidence = profile.dimension_confidence_json or {}
        return any(
            bool(values.get(key)) and float(confidence.get(key, 0) or 0) >= 50
            for key in ("learning_preference", "learning_pace")
        )

    def _course_profile(self, user_id: int, course_id: int, enrollment: CourseEnrollment) -> CourseLearnerProfile:
        values = enrollment.learning_context_json or {}
        confidence = enrollment.learning_context_confidence_json or {}
        goal_ready = bool(str(values.get("learning_goal") or "").strip()) and float(confidence.get("learning_goal", 0) or 0) >= 50
        foundation_ready = bool(str(values.get("knowledge_foundation") or "").strip()) and float(confidence.get("knowledge_foundation", 0) or 0) >= 50
        preference_ready = self._base_profile_ready(user_id)
        missing = []
        if not goal_ready:
            missing.append("learning_goal")
        if not foundation_ready:
            missing.append("knowledge_foundation")
        if not preference_ready:
            missing.append("learning_preference_or_pace")
        profile = self.repository.get_profile(user_id)
        legacy = normalize_profile_json(profile.profile_json if profile is not None else None)
        return CourseLearnerProfile(
            course_id=str(course_id),
            learning_goal=str(values.get("learning_goal") or ""),
            knowledge_foundation=str(values.get("knowledge_foundation") or ""),
            weak_points=[str(item) for item in values.get("weak_points", []) if str(item).strip()],
            dimension_confidence={key: float(value) for key, value in confidence.items() if isinstance(value, (int, float))},
            readiness=CourseProfileReadiness(
                ready=not missing,
                goal_ready=goal_ready,
                foundation_ready=foundation_ready,
                global_preference_ready=preference_ready,
                missing_fields=missing,
            ),
            legacy_suggestions={
                "learning_goal": legacy.get("learning_goal") or "",
                "knowledge_foundation": legacy.get("knowledge_foundation") or "",
                "weak_points": legacy.get("weak_points") or [],
            },
        )

    def _stage_completion(
        self,
        user: User,
        course_id: int,
        *,
        mastery_points: list[CourseMasteryPoint] | None = None,
    ) -> CourseStageCompletion:
        path = self.repository.get_active_path(user.id, course_id)
        tasks = self.repository.list_tasks_for_path(path.id) if path is not None else []
        path_completed = bool(tasks) and all(task.status == "completed" for task in tasks)
        required_ids = {task.knowledge_point_id for task in tasks if task.knowledge_point_id is not None}
        if mastery_points is None:
            mastery = self.get_mastery_map(user, course_id)
            mastery_points = mastery.points
        required_points = [point for point in mastery_points if int(point.id) in required_ids]
        assessed_count = sum(1 for point in required_points if point.score is not None)
        below_count = sum(1 for point in required_points if point.score is None or point.score < 75)
        weaknesses = self.repository.list_weakness_review_items(user.id, course_id)
        active_count = sum(1 for item in weaknesses if item.status in {"pending", "confirmed", "reviewing"})
        due_count = sum(1 for item in weaknesses if is_review_due(item))
        practices = self.repository.list_completed_practices(user.id, course_id)
        answers = self.repository.list_practice_answers(user.id, course_id)
        latest_practice = practices[0] if practices else None
        answers_by_session = {
            practice.id: [item for item in answers if item.session_id == practice.id]
            for practice in practices
        }
        fully_graded = any(
            session_answers and all((item.feedback_json or {}).get("score") is not None for item in session_answers)
            for session_answers in answers_by_session.values()
        )
        latest_report = self.repository.get_latest_report(user.id, course_id)
        report_fresh = bool(
            latest_report
            and latest_practice
            and latest_report.created_at >= latest_practice.updated_at
        )
        reasons = []
        if not path_completed:
            reasons.append("学习路径尚未完成")
        if not required_ids:
            reasons.append("学习路径尚未关联可评估知识点")
        if required_ids and assessed_count < len(required_ids):
            reasons.append("仍有路径知识点尚未形成掌握度证据")
        if below_count:
            reasons.append("仍有路径知识点掌握度低于75分")
        if active_count:
            reasons.append("仍有待处理薄弱点")
        if due_count:
            reasons.append("仍有到期复习任务")
        if not fully_graded:
            reasons.append("尚无一次完整评分的练习")
        if not report_fresh:
            reasons.append("最新报告尚未覆盖最近练习")
        return CourseStageCompletion(
            eligible=not reasons,
            path_completed=path_completed,
            assessed_point_count=assessed_count,
            required_point_count=len(required_ids),
            below_threshold_count=below_count,
            active_weakness_count=active_count,
            due_review_count=due_count,
            report_fresh=report_fresh,
            blocking_reasons=reasons,
        )

    @classmethod
    def _candidate_from_event(cls, event: ProfileEvent | None) -> WeaknessCandidate | None:
        if event is None:
            return None
        evidence = event.evidence_json or {}
        if evidence.get("source_type") != "course_question":
            return None
        citations = evidence.get("citations")
        citation = next((item for item in citations if isinstance(item, dict)), {}) if isinstance(citations, list) else {}
        section_title = cls._safe_title(citation.get("section_title"))
        source_title = cls._safe_title(citation.get("source_title"))
        title = section_title or source_title or "课程问答薄弱点"
        return WeaknessCandidate(
            title=title,
            knowledge_point_id=cls._safe_int(citation.get("knowledge_point_id")),
            trace_id=cls._safe_title(evidence.get("trace_id")) or None,
            source_title=source_title or None,
            section_title=section_title or None,
        )

    @staticmethod
    def _build_weakness_summary(candidate_events: list[ProfileEvent], review_items: list[WeaknessReviewItem]) -> CourseWeaknessSummary:
        latest_event = max(candidate_events, key=lambda event: (event.created_at, event.id), default=None)
        return CourseWeaknessSummary(
            candidate_event_count=len(candidate_events),
            pending_count=sum(1 for item in review_items if item.status == "pending"),
            confirmed_count=sum(1 for item in review_items if item.status == "confirmed"),
            reviewing_count=sum(1 for item in review_items if item.status == "reviewing"),
            completed_count=sum(1 for item in review_items if item.status == "completed"),
            dismissed_count=sum(1 for item in review_items if item.status == "dismissed"),
            latest_evidence_at=iso_timestamp(latest_event.created_at) if latest_event is not None else None,
        )

    @staticmethod
    def _build_path_summary(path: LearningPath | None, tasks: list[LearningTask]) -> CoursePathSummary:
        if path is None:
            return CoursePathSummary(
                status="not_started",
                message="学习路径尚未生成。",
                path_id=None,
                current_task_title=None,
                task_count=0,
                completed_task_count=0,
            )
        current_task = next((task for task in tasks if task.status == "doing"), None)
        if current_task is None:
            current_task = next((task for task in tasks if task.status == "todo"), None)
        completed_count = sum(1 for task in tasks if task.status == "completed")
        return CoursePathSummary(
            status=path.status,
            message="当前学习路径进行中。" if path.status == "active" else "学习路径已归档。",
            path_id=str(path.id),
            current_task_title=current_task.title if current_task is not None else None,
            task_count=len(tasks),
            completed_task_count=completed_count,
        )

    @classmethod
    def _build_mastery_points(
        cls,
        knowledge_points: list[KnowledgePoint],
        review_items: list[WeaknessReviewItem],
        resources: list[GeneratedResource],
        tasks: list[LearningTask],
        practice_answers: list[PracticeAnswer] | None = None,
    ) -> list[CourseMasteryPoint]:
        now = datetime.now(UTC)
        weaknesses_by_point: dict[int, list[WeaknessReviewItem]] = {}
        tasks_by_point: dict[int, list[LearningTask]] = {}
        resources_by_point: dict[int, list[GeneratedResource]] = {}
        answers_by_point: dict[int, list[PracticeAnswer]] = {}
        for item in review_items:
            if item.knowledge_point_id is not None:
                weaknesses_by_point.setdefault(item.knowledge_point_id, []).append(item)
        for task in tasks:
            if task.knowledge_point_id is not None:
                tasks_by_point.setdefault(task.knowledge_point_id, []).append(task)
        for resource in resources:
            if resource.knowledge_point_id is not None:
                resources_by_point.setdefault(resource.knowledge_point_id, []).append(resource)
        for answer in practice_answers or []:
            point_id = cls._safe_int((answer.question_json or {}).get("knowledge_point_id"))
            if point_id is not None:
                answers_by_point.setdefault(point_id, []).append(answer)

        points: list[CourseMasteryPoint] = []
        for point in knowledge_points:
            point_weaknesses = weaknesses_by_point.get(point.id, [])
            point_tasks = tasks_by_point.get(point.id, [])
            point_answers = answers_by_point.get(point.id, [])
            status, score, evidence_count, confidence, last_assessed_at = cls._mastery_measure(
                point_weaknesses,
                point_tasks,
                now,
                point_answers,
            )
            points.append(
                CourseMasteryPoint(
                    id=str(point.id),
                    title=point.title,
                    chapter=point.chapter,
                    order_index=point.order_index,
                    status=status,
                    score=score,
                    evidence_count=evidence_count,
                    confidence=confidence,
                    last_assessed_at=(
                        last_assessed_at.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                        if last_assessed_at is not None
                        else None
                    ),
                    prerequisite_ids=cls._safe_prerequisite_ids(point.prerequisites_json),
                    weakness_item_ids=[str(item.id) for item in point_weaknesses if item.status != "dismissed"],
                    recommended_resource_ids=[str(resource.id) for resource in resources_by_point.get(point.id, [])[:3]],
                )
            )
        return points

    def _mastery_measure(
        weaknesses: list[WeaknessReviewItem],
        tasks: list[LearningTask],
        now: datetime,
        practice_answers: list[PracticeAnswer] | None = None,
    ) -> tuple[str, int | None, int, float, datetime | None]:
        answered = [
            answer
            for answer in practice_answers or []
            if answer.answer_text is not None and (answer.feedback_json or {}).get("score") is not None
        ]
        active_weaknesses = [item for item in weaknesses if item.status in {"confirmed", "reviewing"}]
        completed_weaknesses = [item for item in weaknesses if item.status == "completed"]
        evidence_count = len(answered) + len(active_weaknesses) + len(completed_weaknesses)
        timestamps = [
            value
            for value in [
                *(getattr(answer, "created_at", None) for answer in answered),
                *(getattr(item, "updated_at", None) for item in weaknesses),
            ]
            if value is not None
        ]
        last_assessed_at = max(timestamps) if timestamps else None
        confidence = min(0.95, 0.55 + max(0, evidence_count - 1) * 0.08) if evidence_count else 0.0

        if answered:
            score = latest_practice_score(answered)
            if score is None:
                score = 0
            if active_weaknesses or score < 60:
                return "weak", score, evidence_count, confidence, last_assessed_at
            if any(is_review_due(item, now) for item in completed_weaknesses):
                return "recommended_review", score, evidence_count, confidence, last_assessed_at
            return ("mastered" if score >= 80 else "learning"), score, evidence_count, confidence, last_assessed_at
        if active_weaknesses:
            return "weak", 35, evidence_count, confidence, last_assessed_at
        if any(is_review_due(item, now) for item in completed_weaknesses):
            return "recommended_review", 55, evidence_count, confidence, last_assessed_at
        if completed_weaknesses:
            return "learning", 65, evidence_count, confidence, last_assessed_at
        return "not_started", None, 0, 0.0, None

    @staticmethod
    def _build_mastery_summary(points: list[CourseMasteryPoint]) -> CourseMasterySummary:
        assessed_scores = [point.score for point in points if point.score is not None]
        return CourseMasterySummary(
            total_count=len(points),
            weak_count=sum(1 for point in points if point.status == "weak"),
            learning_count=sum(1 for point in points if point.status == "learning"),
            mastered_count=sum(1 for point in points if point.status == "mastered"),
            recommended_review_count=sum(1 for point in points if point.status == "recommended_review"),
            not_started_count=sum(1 for point in points if point.status == "not_started"),
            assessed_count=len(assessed_scores),
            unassessed_count=sum(1 for point in points if point.score is None),
            average_score=round(sum(assessed_scores) / len(assessed_scores)) if assessed_scores else None,
        )

    @classmethod
    def _sync_weakness_resource_recommendations(
        cls,
        review_items: list[WeaknessReviewItem],
        resources: list[GeneratedResource],
    ) -> bool:
        changed = False
        for item in review_items:
            if item.status in {"confirmed", "reviewing", "completed"}:
                recommended_ids = cls._recommend_resource_ids(resources, item.knowledge_point_id, item.title)
                if item.recommended_resource_ids != recommended_ids:
                    item.recommended_resource_ids = recommended_ids
                    changed = True
                if item.next_review_at is None:
                    item.next_review_at = datetime.now(UTC) + timedelta(days=3)
                    changed = True
        return changed

    @classmethod
    def _recommend_resource_ids(cls, resources: list[GeneratedResource], knowledge_point_id: int | None, title: str) -> list[int]:
        normalized_title = cls._normalize_weakness_title(title)
        matched: list[GeneratedResource] = []
        if knowledge_point_id is not None:
            matched.extend([resource for resource in resources if resource.knowledge_point_id == knowledge_point_id])
            if matched:
                return [resource.id for resource in matched[:3]]
        if len(matched) < 3 and normalized_title:
            matched.extend(
                [
                    resource
                    for resource in resources
                    if resource not in matched and normalized_title in cls._normalize_weakness_title(resource.title)
                ]
            )
        return [resource.id for resource in matched[:3]]

    @staticmethod
    def _safe_prerequisite_ids(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            try:
                result.append(str(int(item)))
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _safe_title(value: object) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())[:120]

    @staticmethod
    def _safe_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _practice_answer_score(answer: PracticeAnswer) -> int:
        try:
            return int((answer.feedback_json or {})["score"])
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_weakness_title(cls, value: str) -> str:
        return cls._safe_title(value).casefold()

    def _build_summary(
        self,
        course: Course,
        material_count: int | None = None,
        knowledge_point_count: int | None = None,
        chunk_count: int | None = None,
        user_id: int | None = None,
        enrollment: CourseEnrollment | None = None,
        current_course_id: int | None = None,
    ) -> CourseSummary:
        if material_count is None:
            material_count = len(self.repository.list_course_materials(course.id))
        if knowledge_point_count is None:
            knowledge_point_count = len(self.repository.list_knowledge_points(course.id))
        if chunk_count is None:
            chunk_count = len(self.repository.list_knowledge_chunks(course.id))

        practiced_knowledge_point_count = 0
        if user_id is not None and knowledge_point_count > 0:
            answers = self.repository.list_practice_answers(user_id, course.id)
            practiced_kp_ids: set[int] = set()
            for answer in answers:
                kp_id = (answer.question_json or {}).get("knowledge_point_id")
                if kp_id is not None:
                    practiced_kp_ids.add(int(kp_id))
            practiced_knowledge_point_count = len(practiced_kp_ids)
            progress_percent = round(practiced_knowledge_point_count / knowledge_point_count * 100)
        else:
            progress_percent = 0

        return CourseSummary(
            id=str(course.id),
            title=course.title,
            description=course.description,
            subject=course.subject,
            source_type=course.source_type or "uploaded",
            status=course.status or "draft",
            agent_trace_id=getattr(course, "agent_trace_id", None),
            progress_percent=progress_percent,
            practiced_knowledge_point_count=practiced_knowledge_point_count,
            material_count=material_count,
            knowledge_point_count=knowledge_point_count,
            chunk_count=chunk_count,
            learning_status=(enrollment.learning_status or "active") if enrollment is not None else "active",
            last_accessed_at=iso_timestamp(enrollment.last_accessed_at) if enrollment is not None else None,
            completed_at=iso_timestamp(enrollment.completed_at) if enrollment is not None else None,
            is_current=course.id == current_course_id,
            profile_ready=self._course_profile(user_id, course.id, enrollment).readiness.ready if user_id is not None and enrollment is not None else False,
        )

    @staticmethod
    def _build_knowledge_point(point: KnowledgePoint) -> CourseKnowledgePoint:
        return CourseKnowledgePoint(
            id=str(point.id),
            title=point.title,
            summary=point.summary,
            chapter=point.chapter,
            order_index=point.order_index,
            difficulty=point.difficulty,
            prerequisite_ids=[str(item) for item in (point.prerequisites_json or [])],
        )

    @classmethod
    def _split_text(cls, text: str) -> list[str]:
        if len(text) <= cls.chunk_size:
            return [text]
        return [text[index : index + cls.chunk_size] for index in range(0, len(text), cls.chunk_size)]

    @staticmethod
    def _summary(text: str) -> str:
        cleaned = CourseLearningStateMixin._clean_text(text)
        return cleaned[:120]

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _extension(filename: str) -> str:
        return Path(filename).suffix.lower()
