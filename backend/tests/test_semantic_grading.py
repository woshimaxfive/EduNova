from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.models import User
from backend.app.services.semantic_grading import SemanticShortAnswerGrader


@dataclass
class FakeModelService:
    response: str
    calls: list[list[dict[str, str]]] = field(default_factory=list)

    def chat_completion(self, _user: User, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.response


def make_user() -> User:
    return User(id=1, account="grader", hashed_password="unused", display_name="评分学生", role="student")


def make_item(question_id: str = "q1") -> dict:
    return {
        "question_id": question_id,
        "question": "启发函数有什么作用？",
        "knowledge_point": "启发式搜索",
        "student_answer": "估算当前状态到目标还需要付出的代价。",
        "reference_answer": "估计剩余路径代价。",
        "course_evidence": "启发函数用于估计到目标的剩余代价。",
        "rubric": "核心含义正确即可得分。",
        "allowed_evidence_refs": ["501"],
    }


def test_semantic_grader_accepts_semantically_equivalent_answer_result() -> None:
    model = FakeModelService(
        '{"grades":[{"question_id":"q1","score":92,"is_correct":true,'
        '"matched_concepts":["剩余代价估计"],"missing_concepts":[],"misconception":"",'
        '"feedback":"语义与课程定义一致。","evidence_refs":["501"],"confidence":0.94}]}'
    )

    result = SemanticShortAnswerGrader(model).grade(user=make_user(), items=[make_item()])

    assert result is not None
    assert result["q1"]["score"] == 92
    assert result["q1"]["matched_concepts"] == ["剩余代价估计"]
    assert len(model.calls) == 1


def test_semantic_grader_rejects_missing_items_and_forged_refs_but_derives_correctness_from_score() -> None:
    missing = FakeModelService('{"grades":[]}')
    forged = FakeModelService(
        '{"grades":[{"question_id":"q1","score":80,"is_correct":true,'
        '"matched_concepts":[],"missing_concepts":[],"misconception":"",'
        '"feedback":"正确。","evidence_refs":["forged"],"confidence":0.8}]}'
    )
    inconsistent = FakeModelService(
        '{"grades":[{"question_id":"q1","score":35,"is_correct":true,'
        '"matched_concepts":[],"missing_concepts":["启发函数"],"misconception":"概念错误",'
        '"feedback":"需要复习。","evidence_refs":[],"confidence":0.8}]}'
    )

    assert SemanticShortAnswerGrader(missing).grade(user=make_user(), items=[make_item()]) is None
    assert SemanticShortAnswerGrader(forged).grade(user=make_user(), items=[make_item()]) is None
    normalized = SemanticShortAnswerGrader(inconsistent).grade(user=make_user(), items=[make_item()])
    assert normalized is not None
    assert normalized["q1"]["score"] == 35
    assert normalized["q1"]["is_correct"] is False
