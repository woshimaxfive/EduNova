from __future__ import annotations

from typing import Any

from backend.app.services.course_answers import ConversationContext, CourseAnswerService


class FakeModelSettingsService:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[list[dict[str, str]]] = []

    def chat_completion(self, user: Any, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.content

    def chat_completion_stream(self, user: Any, messages: list[dict[str, str]]):
        self.calls.append(messages)
        middle = len(self.content) // 2
        return iter([self.content[:middle], self.content[middle:]])


def test_course_answer_removes_echoed_model_context() -> None:
    service = CourseAnswerService(FakeModelSettingsService(_echoed_context_answer()))

    result = service.generate(user=object(), question="这门课最适合先复习哪些知识点？", citations=[_citation()])

    assert result.content.startswith("根据上述引用")
    assert "学生问题：" not in result.content
    assert "课程引用：" not in result.content
    assert "匹配度：" not in result.content
    assert "片段：" not in result.content


def test_course_answer_stream_removes_echoed_model_context() -> None:
    service = CourseAnswerService(FakeModelSettingsService(_echoed_context_answer()))

    stream = service.stream(user=object(), question="这门课最适合先复习哪些知识点？", citations=[_citation()])
    content = "".join(stream.tokens)

    assert content.startswith("根据上述引用")
    assert "学生问题：" not in content
    assert "课程引用：" not in content
    assert "匹配度：" not in content
    assert "片段：" not in content


def test_course_answer_removes_inline_source_metadata() -> None:
    service = CourseAnswerService(FakeModelSettingsService(_inline_source_answer()))

    result = service.generate(user=object(), question="请给我排序", citations=[_citation()])

    assert "匹配度：" not in result.content
    assert "来源：" not in result.content
    assert "片段：" not in result.content
    assert "符号知识表达：知识表示关注" in result.content


def test_course_answer_removes_numbered_source_detail_section() -> None:
    service = CourseAnswerService(FakeModelSettingsService(_numbered_source_detail_answer()))

    result = service.generate(user=object(), question="请解释一个知识点", citations=[_citation()])

    assert "来源：" not in result.content
    assert "章节：" not in result.content
    assert "片段：" not in result.content
    assert "人工智能导论内置课程包.md" not in result.content
    assert "概念解释" in result.content
    assert "易错点" in result.content
    assert "下一步练习" in result.content


def test_course_answer_includes_conversation_context_before_current_question() -> None:
    model = FakeModelSettingsService("根据上下文回答。")
    service = CourseAnswerService(model)
    context = ConversationContext(
        summary="学生前面一直在问启发式搜索和 A 星算法。",
        messages=[
            {"role": "user", "content": "启发式搜索是什么？"},
            {"role": "assistant", "content": "它用启发函数估计搜索方向。"},
        ],
        message_count=2,
        summary_used=True,
    )

    service.generate(
        user=object(),
        question="那这个怎么做题？",
        citations=[_citation()],
        conversation_context=context,
    )

    sent_messages = model.calls[0]
    assert [message["role"] for message in sent_messages] == ["system", "system", "user", "assistant", "user"]
    assert sent_messages[1]["content"] == "会话安全摘要：学生前面一直在问启发式搜索和 A 星算法。"
    assert sent_messages[2]["content"] == "启发式搜索是什么？"
    assert sent_messages[3]["content"] == "它用启发函数估计搜索方向。"
    assert "学生问题：那这个怎么做题？" in sent_messages[4]["content"]


def test_course_answer_stream_includes_conversation_context() -> None:
    model = FakeModelSettingsService("根据上下文流式回答。")
    service = CourseAnswerService(model)
    context = ConversationContext(
        messages=[
            {"role": "user", "content": "上一问是什么？"},
            {"role": "assistant", "content": "上一答。"},
        ],
        message_count=2,
    )

    stream = service.stream(
        user=object(),
        question="继续解释。",
        citations=[_citation()],
        conversation_context=context,
    )
    "".join(stream.tokens)

    sent_messages = model.calls[0]
    assert sent_messages[1] == {"role": "user", "content": "上一问是什么？"}
    assert sent_messages[2] == {"role": "assistant", "content": "上一答。"}
    assert "学生问题：继续解释。" in sent_messages[-1]["content"]


def _citation() -> dict[str, object]:
    return {
        "source_title": "人工智能导论内置课程包.md",
        "section_title": "符号知识表达",
        "score": 2.65,
        "content": "知识表示关注如何把事实、概念、关系和规则编码成机器可处理的结构。",
    }


def _echoed_context_answer() -> str:
    return """学生问题：这门课最适合先复习哪些知识点？

课程引用：

[1] 来源：人工智能导论内置课程包.md
章节：符号知识表达
匹配度：2.65
片段：知识表示关注如何把事实、概念、关系和规则编码成机器可处理的结构。

根据上述引用，可以先复习符号知识表达，再复习规则与推理，并用练习确认掌握度。"""


def _inline_source_answer() -> str:
    return (
        "1. 符号知识表达（匹配度：2.4667） - 来源：[1] - 片段："
        "知识表示关注如何把事实、概念、关系和规则编码成机器可处理的结构。"
        " 2. 规则与推理（匹配度：1.3449） - 来源：[2] - 片段："
        "产生式规则使用 IF-THEN 形式表达知识。"
    )


def _numbered_source_detail_answer() -> str:
    return (
        "**概念解释：** 符号知识表达关注如何把事实、概念、关系和规则编码成机器可处理的结构。"
        " **依据：** 1. 来源：人工智能导论内置课程包.md 2. 章节：符号知识表达 "
        "3. 片段：知识表示关注如何把事实、概念、关系和规则编码成机器可处理的结构。"
        " **易错点：** 不要把符号规则和统计学习混为一谈。"
        " **下一步练习：** 用自己的话写出一个 IF-THEN 规则。"
    )
