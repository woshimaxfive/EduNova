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


class ThinkingAwareModelSettingsService(FakeModelSettingsService):
    def __init__(self, content: str) -> None:
        super().__init__(content)
        self.thinking_types: list[str] = []

    def chat_completion(
        self,
        user: Any,
        messages: list[dict[str, str]],
        thinking_type: str = "disabled",
    ) -> str:
        self.thinking_types.append(thinking_type)
        return super().chat_completion(user, messages)

    def chat_completion_stream(
        self,
        user: Any,
        messages: list[dict[str, str]],
        thinking_type: str = "disabled",
    ):
        self.thinking_types.append(thinking_type)
        return super().chat_completion_stream(user, messages)


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
    assert [message["role"] for message in sent_messages] == ["system", "user", "assistant", "user"]
    assert "会话安全摘要：学生前面一直在问启发式搜索和 A 星算法。" in sent_messages[0]["content"]
    assert sent_messages[1]["content"] == "启发式搜索是什么？"
    assert sent_messages[2]["content"] == "它用启发函数估计搜索方向。"
    assert "学生问题：那这个怎么做题？" in sent_messages[3]["content"]
    assert sum(message["role"] == "system" for message in sent_messages) == 1


def test_home_answer_merges_long_conversation_summary_into_single_system_message() -> None:
    model = FakeModelSettingsService("继续回答。")
    service = CourseAnswerService(model)
    context = ConversationContext(
        summary="学生此前关注反向传播，已建议先复习链式法则。",
        messages=[
            {"role": "user", "content": "反向传播是什么？"},
            {"role": "assistant", "content": "它用链式法则计算梯度。"},
        ],
        message_count=2,
        summary_used=True,
    )

    service.generate_home(
        user=object(),
        question="继续讲。",
        conversation_context=context,
    )

    sent_messages = model.calls[0]
    assert [message["role"] for message in sent_messages] == ["system", "user", "assistant", "user"]
    assert "会话安全摘要：学生此前关注反向传播，已建议先复习链式法则。" in sent_messages[0]["content"]
    assert "不能声称无法记住或访问这些已提供的内容" in sent_messages[0]["content"]
    assert sum(message["role"] == "system" for message in sent_messages) == 1


def test_home_answer_extracts_only_final_answer_boundary_and_requests_markdown() -> None:
    model = FakeModelSettingsService(
        "内部规划不应展示<final_answer>## 机器学习\n\n机器学习从数据中归纳可泛化规律。</final_answer>尾部说明"
    )
    service = CourseAnswerService(model)

    result = service.generate_home(user=object(), question="什么是机器学习？")

    assert result.content == "## 机器学习\n\n机器学习从数据中归纳可泛化规律。"
    assert "内部规划" not in result.content
    assert "只输出 <final_answer>" in model.calls[0][0]["content"]


def test_home_answer_keeps_unbounded_prompt_echo_visible_to_graph_review() -> None:
    echoed = "学生问题：什么是机器学习？ 工具状态：未联网 可用来源摘要：资料开头 工具提示：无。"

    assert CourseAnswerService._sanitize_home_answer(echoed) == echoed


def test_home_review_returns_none_for_invalid_json_instead_of_fabricating_passed() -> None:
    service = CourseAnswerService(FakeModelSettingsService("这不是审核 JSON"))

    result = service.review_home(
        user=object(),
        question="什么是机器学习？",
        answer="机器学习从数据中归纳规律。",
        citations=[],
    )

    assert result is None


def test_home_review_filters_unknown_risk_flags_and_forces_revision() -> None:
    service = CourseAnswerService(
        FakeModelSettingsService(
            '{"review_status":"passed","confidence":1.4,"risk_flags":["prompt_echo","unknown"],'
            '"safety_summary":"需要修订"}'
        )
    )

    result = service.review_home(
        user=object(),
        question="什么是机器学习？",
        answer="学生问题：什么是机器学习？",
        citations=[],
    )

    assert result is not None
    assert result.review_status == "revise"
    assert result.confidence == 1.0
    assert result.risk_flags == ["prompt_echo"]


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


def test_home_and_course_answers_map_adaptive_reasoning_to_provider_thinking() -> None:
    model = ThinkingAwareModelSettingsService("回答。")
    service = CourseAnswerService(model)

    service.generate_home(user=object(), question="简单解释", deep_thinking=False)
    service.generate_home(user=object(), question="复杂分析", deep_thinking=True)
    service.generate(user=object(), question="简单解释", citations=[_citation()], reasoning_mode="auto")
    stream = service.stream(user=object(), question="复杂分析", citations=[_citation()], reasoning_mode="deep")
    "".join(stream.tokens)

    assert model.thinking_types == ["auto", "enabled", "auto", "enabled"]


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
