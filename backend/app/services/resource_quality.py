from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Iterable

from backend.app.services.resource_artifacts import validate_resource_content
from backend.app.services.resource_safety import sensitive_output_flags


RESOURCE_PROMPT_VERSION = "resource-v4.5"
RESOURCE_REVIEW_PROMPT_VERSION = "resource-review-v4.0"
STRICT_MODEL_TYPES = {"quiz", "code", "animation"}
EVIDENCE_FALLBACK_TYPES = {"doc", "mindmap", "slide"}
TRIVIAL_DISTRACTORS = {
    "无关概念",
    "无关提示",
    "跳过资料依据",
    "只背结论",
    "只背题干",
    "与知识点无关的记忆",
}
FORBIDDEN_OUTPUT_MARKERS = (
    "系统提示词",
    "system prompt",
    "模型输入",
    "api key",
    "sk-",
    "资料原文",
    "raw prompt",
)


def normalized_text(value: object) -> str:
    return re.sub(r"[^0-9a-zA-Z一-龥]+", "", str(value or "").casefold())


def text_similarity(left: object, right: object) -> float:
    left_text = normalized_text(left)
    right_text = normalized_text(right)
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def artifact_text(artifact: object) -> str:
    if not isinstance(artifact, (dict, list)):
        return str(artifact or "")
    return json.dumps(artifact, ensure_ascii=False, sort_keys=True)


def meaningful_model_delta(candidate: dict[str, Any], draft: dict[str, Any]) -> bool:
    return text_similarity(candidate.get("artifact"), draft.get("artifact")) < 0.94


def quality_risks(
    resource_type: str,
    content: dict[str, Any],
    *,
    topic: str,
    evidence_terms: Iterable[str],
    valid_citation_refs: set[int],
) -> list[str]:
    risks = list(validate_resource_content(resource_type, content))
    artifact = content.get("artifact")
    text = f"{content.get('markdown') or ''}\n{artifact_text(artifact)}"
    if sensitive_output_flags(text, FORBIDDEN_OUTPUT_MARKERS):
        risks.append("sensitive_output")

    evidence_rows = [str(term) for term in evidence_terms]
    topic_tokens = _semantic_terms(topic)
    evidence_tokens = {token for term in evidence_rows for token in _semantic_terms(term)}
    normalized_candidate = normalized_text(text)
    if topic_tokens and not _matches_semantics(topic, text, topic_tokens, normalized_candidate):
        risks.append("off_topic")

    refs = _citation_refs(artifact)
    if valid_citation_refs and (not refs or any(ref not in valid_citation_refs for ref in refs)):
        risks.append("citation_mismatch")
    # Exact wording overlap is not a sound citation test for model-generated teaching
    # material: a correct paraphrase can share no long substring with the excerpt. When
    # references are present and belong to the retrieved evidence set, semantic support is
    # reviewed by ReviewAgent. Retain the lexical fallback only when there is no verifiable
    # citation binding at all.
    if (
        evidence_tokens
        and not valid_citation_refs
        and not _matches_semantics(" ".join(evidence_rows), text, evidence_tokens, normalized_candidate)
    ):
        risks.append("citation_mismatch")

    if resource_type == "quiz" and isinstance(artifact, dict):
        risks.extend(_quiz_risks(artifact))
    if resource_type == "code" and isinstance(artifact, dict):
        risks.extend(_code_risks(artifact, topic=topic, evidence_terms=evidence_rows))
    if resource_type == "animation" and isinstance(artifact, dict):
        risks.extend(_animation_risks(artifact))
    return list(dict.fromkeys(risks))


def quality_summary(
    *,
    risks: list[str],
    prompt_version: str,
    source_coverage: float,
    model_delta: bool,
    code_verification: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": "passed" if not risks else "failed",
        "risk_flags": list(dict.fromkeys(risks)),
        "prompt_version": prompt_version,
        "source_coverage": round(max(0.0, min(source_coverage, 1.0)), 3),
        "model_delta": model_delta,
        "code_verification": code_verification,
    }


def _semantic_terms(value: object) -> set[str]:
    text = str(value or "")
    terms = {
        item.casefold()
        for item in re.findall(r"[A-Za-z][A-Za-z0-9*+_.-]{1,24}", text)
        if len(item.strip()) >= 2
    }
    for segment in re.findall(r"[一-龥]{2,16}", text):
        terms.add(segment.casefold())
        for size in range(2, min(4, len(segment)) + 1):
            terms.update(segment[index : index + size].casefold() for index in range(len(segment) - size + 1))
    stop = {"课程", "学习", "知识", "内容", "资料", "当前", "理解", "步骤", "问题", "相关", "进行", "需要"}
    return {item for item in terms if item not in stop}


def _matches_semantics(source: object, candidate: object, terms: set[str], normalized_candidate: str) -> bool:
    matched_terms = {token for token in terms if normalized_text(token) in normalized_candidate}
    if len(matched_terms) >= min(2, len(terms)):
        return True
    source_text = str(source or "").casefold()
    candidate_text = str(candidate or "").casefold()
    aliases = (
        (("启发式搜索", "a*", "astar", "f(n)=g(n)+h(n)"), (r"启发式搜索", r"\ba\s*\*", r"astar", r"f\s*\(n\)")),
        (
            ("反向传播", "backprop", "back propagation"),
            (r"反向传播", r"back\s*prop", r"\bbackward\b", r"\bgradient\b", r"\bdw\d*\b"),
        ),
        (("前向传播", "forward propagation"), (r"前向传播", r"forward\s*prop")),
    )
    for source_aliases, candidate_patterns in aliases:
        if any(alias in source_text for alias in source_aliases) and any(re.search(pattern, candidate_text, re.IGNORECASE) for pattern in candidate_patterns):
            return True
    return False


def _citation_refs(value: object) -> set[int]:
    refs: set[int] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "citation_refs" and isinstance(item, list):
                refs.update(int(ref) for ref in item if str(ref).isdigit())
            else:
                refs.update(_citation_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(_citation_refs(item))
    return refs


def _quiz_risks(artifact: dict[str, Any]) -> list[str]:
    questions = artifact.get("questions")
    if not isinstance(questions, list) or len(questions) < 3:
        return ["incomplete_quiz"]
    risks: list[str] = []
    prompts: list[str] = []
    for question in questions:
        if not isinstance(question, dict):
            risks.append("malformed_content")
            continue
        prompt = str(question.get("prompt") or "").strip()
        if not prompt or any(text_similarity(prompt, previous) >= 0.84 for previous in prompts):
            risks.append("duplicate_questions")
        prompts.append(prompt)
        options = question.get("options")
        if question.get("type") in {"single_choice", "multiple_choice"}:
            if not isinstance(options, list) or len(options) < 3:
                risks.append("invalid_options")
                continue
            option_texts = [str(option.get("text") or "").strip() for option in options if isinstance(option, dict)]
            if len(option_texts) != len(options) or len({normalized_text(item) for item in option_texts}) != len(option_texts):
                risks.append("invalid_options")
            if any(item in TRIVIAL_DISTRACTORS for item in option_texts):
                risks.append("trivial_distractors")
            keys = {str(option.get("key") or "") for option in options if isinstance(option, dict)}
            answer = question.get("answer")
            answers = {str(item) for item in answer} if isinstance(answer, list) else {str(answer or "")}
            if not answers or not answers.issubset(keys):
                risks.append("invalid_answer")
        if len(str(question.get("explanation") or "").strip()) < 20:
            risks.append("incomplete_explanation")
    return risks


def _code_risks(artifact: dict[str, Any], *, topic: str, evidence_terms: list[str]) -> list[str]:
    files = artifact.get("files")
    entry = str(artifact.get("entry_file") or "")
    if not isinstance(files, list) or not entry:
        return ["malformed_content"]
    code = next((str(item.get("content") or "") for item in files if isinstance(item, dict) and item.get("path") == entry), "")
    if len(code.strip()) < 40 or not str(artifact.get("expected_output") or "").strip():
        return ["incomplete_code"]
    code_semantics = "\n".join(
        [
            entry,
            code,
            *[str(item) for item in artifact.get("instructions", []) if str(item).strip()],
            *[str(item) for item in artifact.get("tasks", []) if str(item).strip()],
        ]
    )
    topic_terms = _semantic_terms(topic)
    normalized_code = normalized_text(code_semantics)
    if topic_terms and not _matches_semantics(topic, code_semantics, topic_terms, normalized_code):
        return ["off_topic_code"]
    return []


def _animation_risks(artifact: dict[str, Any]) -> list[str]:
    scenes = artifact.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < 3:
        return ["incomplete_animation"]
    titles = [normalized_text(scene.get("title")) for scene in scenes if isinstance(scene, dict)]
    if len(titles) != len(scenes) or len(set(titles)) != len(titles):
        return ["duplicate_scenes"]
    if any(
        not isinstance(scene, dict) or not _is_safe_mermaid_flowchart(str(scene.get("diagram") or ""))
        for scene in scenes
    ):
        return ["invalid_animation_diagram"]
    return []


def _is_safe_mermaid_flowchart(source: str) -> bool:
    """Validate the small Mermaid subset accepted by the student renderer.

    Full Mermaid parsing stays in the existing frontend dependency. This backend gate
    catches malformed or active syntax before persistence and sends the candidate through
    the existing one-shot model repair path.
    """
    text = source.strip()
    if not re.match(r"^flowchart\s+(?:TB|TD|BT|RL|LR)\b", text, re.IGNORECASE):
        return False
    if len(text) > 4000 or re.search(r"%%\{|\b(?:click|href|linkStyle)\b|<\/?(?:script|iframe)", text, re.IGNORECASE):
        return False
    pairs = (("[", "]"), ("{", "}"), ("(", ")"))
    if any(text.count(opening) != text.count(closing) for opening, closing in pairs):
        return False
    # Mermaid closes an unquoted node label at the first `]`. Nested brackets such as
    # `Q[队列: [S]]` therefore pass a count-only check but fail in the browser.
    if re.search(r"\[(?!\")[^\]\n]*\[", text):
        return False
    # A vertical bar inside a node label (for example `[3, 5, |8|]`) is parsed as
    # edge-label syntax by Mermaid and is the concrete failure seen in production.
    if re.search(r"\[[^\]\n]*\|[^\]\n]*\]", text):
        return False
    return True
