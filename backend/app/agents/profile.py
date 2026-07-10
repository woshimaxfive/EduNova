from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, review_contract, safe_text
from backend.app.api.errors import make_trace_id
from backend.app.models import ProfileEvent, StudentProfile, User
from backend.app.schemas.profiles import PROFILE_DIMENSIONS, ProfileChatResponse, event_to_api, profile_to_api


class ProfileState(TypedDict, total=False):
    trace_id: str
    operation: str
    user: User
    user_id: int
    course_id: int | None
    message: str
    source_type: str
    source_ref_type: str | None
    source_ref_id: int | None
    parent_trace_id: str | None
    suggested_updates: dict[str, Any]
    profile: StudentProfile
    deterministic_updates: dict[str, Any]
    proposed_updates: dict[str, Any]
    proposal_confidence: dict[str, float]
    applied_updates: dict[str, Any]
    generation_mode: str
    review_mode: str
    review_result: dict[str, Any]
    needs_repair: bool
    repair_count: int
    event: ProfileEvent
    response: ProfileChatResponse


class ProfileGraphRunner:
    workflow = "profile"

    def __init__(self, service: Any) -> None:
        self.service = service
        self.graph = self._build_graph()

    def update_by_chat(self, user: User, message: str) -> ProfileChatResponse:
        state: ProfileState = {
            "trace_id": make_trace_id(),
            "operation": "explicit_chat",
            "user": user,
            "user_id": user.id,
            "course_id": None,
            "message": message.strip(),
            "source_type": "profile_chat",
            "source_ref_type": None,
            "source_ref_id": None,
            "suggested_updates": {},
            "repair_count": 0,
        }
        return self.graph.invoke(state)["response"]

    def ingest_learning_signal(
        self,
        *,
        user: User,
        source_type: str,
        source_ref_type: str,
        source_ref_id: int,
        suggested_updates: dict[str, Any],
        course_id: int | None = None,
        parent_trace_id: str | None = None,
    ) -> ProfileEvent | None:
        if not suggested_updates:
            return None
        state: ProfileState = {
            "trace_id": make_trace_id(),
            "operation": "learning_signal",
            "user": user,
            "user_id": user.id,
            "course_id": course_id,
            "message": "",
            "source_type": source_type,
            "source_ref_type": source_ref_type,
            "source_ref_id": source_ref_id,
            "parent_trace_id": parent_trace_id,
            "suggested_updates": suggested_updates,
            "repair_count": 0,
        }
        return self.graph.invoke(state).get("event")

    def _build_graph(self):
        graph = StateGraph(ProfileState)
        graph.add_node("collect_context", self._collect_context_node)
        graph.add_node("extract", self._extract_node)
        graph.add_node("evidence_gate", self._evidence_gate_node)
        graph.add_node("review", self._review_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("apply", self._apply_node)
        graph.add_node("persist_event", self._persist_node)
        graph.add_edge(START, "collect_context")
        graph.add_edge("collect_context", "extract")
        graph.add_edge("extract", "evidence_gate")
        graph.add_edge("evidence_gate", "review")
        graph.add_conditional_edges("review", lambda state: "repair" if state.get("needs_repair") else "apply", {"repair": "repair", "apply": "apply"})
        graph.add_edge("repair", "apply")
        graph.add_edge("apply", "persist_event")
        graph.add_edge("persist_event", END)
        return graph.compile()

    def _collect_context_node(self, state: ProfileState) -> dict[str, Any]:
        def work():
            profile = self.service.repository.get_profile(int(state["user_id"]))
            if profile is None:
                profile = StudentProfile(
                    user_id=int(state["user_id"]),
                    profile_json=self.service._empty_profile(),
                    confidence_score=Decimal("0.00"),
                    dimension_confidence_json={},
                    updated_reason=None,
                )
                self.service.repository.add_profile(profile)
                self.service.repository.flush()
            return {"profile": profile}, "已读取用户级画像和安全证据摘要。", "completed", {}

        return self._run_node(state, "collect_context", 1, "读取当前画像与证据计数", work)

    def _extract_node(self, state: ProfileState) -> dict[str, Any]:
        def work():
            if state.get("operation") == "learning_signal":
                deterministic = self._sanitize_updates(state.get("suggested_updates", {}))
                confidence = {key: 0.78 for key in deterministic}
                return {
                    "deterministic_updates": deterministic,
                    "proposed_updates": deterministic,
                    "proposal_confidence": confidence,
                    "generation_mode": "deterministic_source",
                }, f"已形成 {len(deterministic)} 个学习行为画像提案。", "completed", {"candidate_count": len(deterministic)}

            deterministic = self._sanitize_updates(self.service._extract_profile_updates(str(state.get("message") or "")))
            proposed = dict(deterministic)
            confidence = {key: 0.72 for key in proposed}
            model_used = False
            if self.service.model_service is not None:
                try:
                    raw = self.service.model_service.chat_completion(
                        state["user"],
                        [
                            {
                                "role": "system",
                                "content": (
                                    "你是 ProfileGraph 的画像抽取 Agent。只输出 JSON。"
                                    "仅允许八个既定画像字段，不得输出原始思维链或敏感内容。"
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"学生回答：{safe_text(state.get('message'), limit=1200)}\n"
                                    "返回 {\"updates\":{},\"confidence\":{}}，confidence 取 0 到 1。"
                                ),
                            },
                        ],
                    )
                    payload = parse_json_object(raw)
                    model_updates = self._sanitize_updates(payload.get("updates") if isinstance(payload, dict) else {})
                    for key, value in model_updates.items():
                        proposed[key] = value
                    raw_confidence = payload.get("confidence") if isinstance(payload, dict) else {}
                    if isinstance(raw_confidence, dict):
                        for key in proposed:
                            try:
                                confidence[key] = min(1.0, max(0.0, float(raw_confidence.get(key, confidence.get(key, 0.72)))))
                            except (TypeError, ValueError):
                                pass
                    model_used = bool(model_updates)
                except Exception:
                    model_used = False
            return {
                "deterministic_updates": deterministic,
                "proposed_updates": proposed,
                "proposal_confidence": confidence,
                "generation_mode": "model_enhanced" if model_used else "deterministic_source",
            }, f"已抽取 {len(proposed)} 个画像维度。", "completed" if model_used else "warning", {"model_used": model_used, "candidate_count": len(proposed)}

        return self._run_node(state, "extract", 2, "抽取白名单画像维度", work)

    def _evidence_gate_node(self, state: ProfileState) -> dict[str, Any]:
        def work():
            proposed = dict(state.get("proposed_updates", {}))
            if state.get("operation") == "explicit_chat":
                return {"applied_updates": proposed}, "显式画像回答通过证据门控。", "completed", {"applied_count": len(proposed)}

            events = self.service.repository.list_events(int(state["user_id"]), 100)
            applied: dict[str, Any] = {}
            for dimension, value in proposed.items():
                normalized = self._normalized_value(value)
                refs = {(str(state.get("source_ref_type") or ""), int(state.get("source_ref_id") or 0))}
                confidence_values = [float(state.get("proposal_confidence", {}).get(dimension, 0.0))]
                for event in events:
                    proposal = getattr(event, "proposal_json", None) or {}
                    if event.status != "candidate" or self._normalized_value(proposal.get(dimension)) != normalized:
                        continue
                    refs.add((str(event.source_ref_type or ""), int(event.source_ref_id or 0)))
                    if event.confidence_score is not None:
                        confidence_values.append(float(event.confidence_score))
                aggregate = sum(confidence_values) / max(1, len(confidence_values))
                if len(refs) >= 2 and aggregate >= 0.75:
                    applied[dimension] = value
            status = "completed" if applied else "warning"
            return {"applied_updates": applied}, (
                f"{len(applied)} 个重复高置信信号可自动更新画像。" if applied else "单次学习信号保留为候选证据。"
            ), status, {"applied_count": len(applied), "candidate_count": len(proposed) - len(applied)}

        return self._run_node(state, "evidence_gate", 3, "按独立来源与置信度决定是否应用", work)

    def _review_node(self, state: ProfileState) -> dict[str, Any]:
        def work():
            risks = self._risks(state.get("proposed_updates", {}))
            model_review = None
            if state.get("generation_mode") == "model_enhanced" and self.service.model_service is not None:
                try:
                    raw = self.service.model_service.chat_completion(
                        state["user"],
                        [
                            {"role": "system", "content": "你是 ProfileGraph ReviewAgent。只输出 JSON，不得补充画像字段。"},
                            {
                                "role": "user",
                                "content": (
                                    f"审核维度：{','.join(state.get('proposed_updates', {}).keys())}。"
                                    "返回 {\"review_status\":\"passed|revise\",\"confidence\":0.0,"
                                    "\"risk_flags\":[],\"safety_summary\":\"\"}。"
                                ),
                            },
                        ],
                    )
                    model_review = review_contract(parse_json_object(raw), default_summary="画像字段与隐私边界审核完成。")
                except Exception:
                    model_review = None
            if model_review and model_review["review_status"] == "revise":
                risks.extend(str(item) for item in model_review["risk_flags"])
            risks = list(dict.fromkeys(risks))
            if risks:
                review = {
                    "review_status": "revise",
                    "confidence": model_review["confidence"] if model_review else 0.45,
                    "risk_flags": risks,
                    "safety_summary": model_review["safety_summary"] if model_review else "画像提案需要按白名单规则修订。",
                }
                return {"review_result": review, "review_mode": "model_and_rules" if model_review else "rules_only", "needs_repair": True}, review["safety_summary"], "warning", review
            review = model_review or {
                "review_status": "warning",
                "confidence": 0.64,
                "risk_flags": [],
                "safety_summary": "模型审核不可用，已完成字段、长度和隐私规则审核。",
            }
            return {"review_result": review, "review_mode": "model_and_rules" if model_review else "rules_only", "needs_repair": False}, review["safety_summary"], "completed" if model_review else "warning", review

        return self._run_node(state, "review", 4, "审核画像字段、证据和隐私边界", work)

    def _repair_node(self, state: ProfileState) -> dict[str, Any]:
        def work():
            repaired = self._sanitize_updates(state.get("deterministic_updates", {}))
            applied = {key: value for key, value in state.get("applied_updates", {}).items() if key in repaired}
            review = {
                "review_status": "passed",
                "confidence": 0.64,
                "risk_flags": [],
                "safety_summary": "已回退到确定性画像提案并通过规则复核。",
            }
            return {"proposed_updates": repaired, "applied_updates": applied, "review_result": review, "repair_count": 1, "generation_mode": "deterministic_source"}, review["safety_summary"], "completed", {**review, "repair_count": 1}

        return self._run_node(state, "repair", 5, "按审核结果修订一次画像提案", work)

    def _apply_node(self, state: ProfileState) -> dict[str, Any]:
        def work():
            applied = dict(state.get("applied_updates", {}))
            profile = state["profile"]
            if applied:
                profile.profile_json = self.service._merge_profile_json(profile.profile_json, applied)
                dimension_confidence = dict(getattr(profile, "dimension_confidence_json", None) or {})
                for key in applied:
                    proposed_confidence = float(state.get("proposal_confidence", {}).get(key, 0.72)) * 100
                    dimension_confidence[key] = round(max(float(dimension_confidence.get(key, 0)), proposed_confidence), 2)
                profile.dimension_confidence_json = dimension_confidence
                values = [float(value) for value in dimension_confidence.values() if isinstance(value, (int, float))]
                profile.confidence_score = Decimal(str(round(sum(values) / len(values), 2))) if values else Decimal("0.00")
                profile.updated_reason = self.service._change_summary(self.service._changed_labels(applied))
                profile.updated_at = datetime.now(UTC)
            return {"profile": profile}, f"已应用 {len(applied)} 个画像维度。", "completed" if applied else "warning", {"applied_count": len(applied)}

        return self._run_node(state, "apply", 6, "更新长期画像与逐维可信度", work)

    def _persist_node(self, state: ProfileState) -> dict[str, Any]:
        started = perf_counter()
        proposed = dict(state.get("proposed_updates", {}))
        applied = dict(state.get("applied_updates", {}))
        profile = state["profile"]
        event = ProfileEvent(
            user_id=int(state["user_id"]),
            profile_id=profile.id,
            dimension="profile_chat" if state.get("operation") == "explicit_chat" else (next(iter(proposed), "learning_signal")),
            change_summary=profile.updated_reason if applied and profile.updated_reason else "学习行为证据待更多信号确认",
            evidence_json={
                "source_type": state.get("source_type"),
                "updated_dimensions": list(applied),
                "candidate_dimensions": [key for key in proposed if key not in applied],
                "trace_id": state["trace_id"],
                "parent_trace_id": state.get("parent_trace_id"),
            },
            agent_trace_id=state["trace_id"],
            source_type=str(state.get("source_type") or "learning_signal"),
            source_ref_type=state.get("source_ref_type"),
            source_ref_id=state.get("source_ref_id"),
            status="applied" if applied else "candidate",
            confidence_score=Decimal(str(round(sum(state.get("proposal_confidence", {}).values()) / max(1, len(state.get("proposal_confidence", {}))), 2))),
            proposal_json=proposed,
            applied_at=datetime.now(UTC) if applied else None,
        )
        try:
            self.service.repository.add_event(event)
            self.service.repository.flush()
            self.service.repository.commit()
        except Exception as exc:
            self.service.repository.rollback()
            self._record(state, "persist_event", 7, "failed", "持久化画像与证据事件", "持久化失败，业务事务已回滚。", {"error_code": exc.__class__.__name__}, started)
            raise
        events = self.service.repository.list_events(int(state["user_id"]), 100)
        summary = self.service._evidence_summary(events)
        response = ProfileChatResponse(
            reply="已更新你的学习画像。" if applied else "已记录这条学习证据，后续会结合更多信号判断。",
            agent_trace_id=state["trace_id"],
            profile=profile_to_api(profile, version=self.service.repository.count_events_for_profile(profile.id), next_question=self.service._next_question(profile), evidence_summary=summary),
            event=event_to_api(event),
        )
        self._record(state, "persist_event", 7, "completed", "持久化画像与证据事件", "画像事件已安全持久化。", {"artifact_id": str(profile.id), "event_status": event.status}, started)
        return {"event": event, "response": response}

    @staticmethod
    def _normalized_value(value: Any) -> str:
        if isinstance(value, list):
            return "|".join(sorted(str(item).strip().lower() for item in value if str(item).strip()))
        return " ".join(str(value or "").split()).lower()

    @staticmethod
    def _sanitize_updates(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, Any] = {}
        for key, raw in value.items():
            if key not in PROFILE_DIMENSIONS:
                continue
            if key == "weak_points":
                if isinstance(raw, list):
                    items = [safe_text(item, limit=80) for item in raw]
                else:
                    items = [safe_text(raw, limit=80)]
                clean = list(dict.fromkeys(item for item in items if item and not contains_sensitive_text(item)))[:10]
                if clean:
                    result[key] = clean
                continue
            text = safe_text(raw, limit=200)
            if text and not contains_sensitive_text(text):
                result[key] = text
        return result

    def _risks(self, updates: dict[str, Any]) -> list[str]:
        risks: list[str] = []
        for key, value in updates.items():
            if key not in PROFILE_DIMENSIONS:
                risks.append("unknown_dimension")
            if contains_sensitive_text(self._normalized_value(value)):
                risks.append("sensitive_output")
        return list(dict.fromkeys(risks))

    def _run_node(self, state: ProfileState, name: str, index: int, input_summary: str, work: Callable):
        started = perf_counter()
        try:
            result, output_summary, status, metadata = work()
        except Exception as exc:
            self._record(state, name, index, "failed", input_summary, "节点执行失败，已记录安全错误摘要。", {"error_code": exc.__class__.__name__}, started)
            raise
        self._record(state, name, index, status, input_summary, output_summary, metadata, started)
        return result

    def _record(self, state: ProfileState, name: str, index: int, status: str, input_summary: str, output_summary: str, metadata: dict[str, Any], started: float) -> None:
        recorder = self.service.trace_recorder
        if recorder is None:
            return
        recorder.record(
            trace_id=state["trace_id"],
            user_id=int(state["user_id"]),
            course_id=state.get("course_id"),
            agent_name=name,
            step_index=index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=max(0, int((perf_counter() - started) * 1000)),
            workflow=self.workflow,
            artifact_type="student_profile",
            artifact_id=metadata.get("artifact_id"),
            metadata={"operation": state.get("operation"), **metadata},
        )
