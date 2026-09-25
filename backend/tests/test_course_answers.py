from __future__ import annotations

import json
from typing import Any

from backend.app.services.course_answers import ConversationContext, CourseAnswerProgress, CourseAnswerService


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


class SequentialModelSettingsService(FakeModelSettingsService):
    def __init__(self, contents: list[str]) -> None:
        super().__init__(contents[0])
        self.contents = iter(contents)

    def chat_completion(self, user: Any, messages: list[dict[str, str]], **_: Any) -> str:
        self.calls.append(messages)
        return next(self.contents)

    def chat_completion_stream(self, user: Any, messages: list[dict[str, str]], **_: Any):
        self.calls.append(messages)
        content = next(self.contents)
        return iter([content])


def test_course_progress_never_releases_unchecked_content() -> None:
    model = SequentialModelSettingsService([
        "访问仅需 999 纳秒。",
        "Cache 保存近期常用数据。",
    ])
    stream = CourseAnswerService(model).stream(
        user=object(), question="解释缓存", citations=[_citation()], include_progress=True,
    )
    events = list(stream.tokens)
    assert [item.stage for item in events if isinstance(item, CourseAnswerProgress)] == [
        "answer_receiving", "answer_checking", "answer_repairing",
    ]
    assert all(isinstance(item, CourseAnswerProgress) for item in events[:-1])
    assert events[-1] == "Cache 保存近期常用数据。"
    assert "999" not in repr(events)
    assert len(model.calls) == 2


def test_course_progress_does_not_leak_partial_answer_on_provider_failure() -> None:
    from backend.app.providers.openai_compatible import ModelProviderError
    from backend.app.services.course_answers import CourseAnswerGenerationError
    import pytest

    class InterruptedModel(FakeModelSettingsService):
        def chat_completion_stream(self, **kwargs):
            yield "未核对的正文"
            raise ModelProviderError("interrupted")

    stream = CourseAnswerService(InterruptedModel("")).stream(
        user=object(), question="解释缓存", citations=[_citation()], include_progress=True,
    )
    assert isinstance(next(stream.tokens), CourseAnswerProgress)
    with pytest.raises(CourseAnswerGenerationError):
        next(stream.tokens)


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


def test_course_answer_repairs_quantitative_claims_missing_from_citations() -> None:
    model = SequentialModelSettingsService(
        [
            "L1 命中率通常达到 90%，访问只需 2 个周期。",
            "Cache 保存近期常用数据，未命中时再访问主存，因此能在速度与容量之间取得平衡。",
        ]
    )
    service = CourseAnswerService(model)

    result = service.generate(user=object(), question="为什么存储层次有效？", citations=[_citation()])

    assert "90%" not in result.content
    assert "2 个周期" not in result.content
    assert "速度与容量" in result.content
    assert len(model.calls) == 2
    assert "未被证据逐字支持" in model.calls[1][0]["content"]


def test_course_answer_keeps_quantitative_claims_present_in_citations() -> None:
    model = FakeModelSettingsService("教材示例说明命中率为 80%。")
    service = CourseAnswerService(model)
    citation = {**_citation(), "content": "在该教材示例中，命中率为80%。"}

    result = service.generate(user=object(), question="教材示例的命中率是多少？", citations=[citation])

    assert "80%" in result.content
    assert len(model.calls) == 1


def test_course_answer_prompt_includes_available_material_page_number() -> None:
    messages = CourseAnswerService._build_messages(
        "请标明教材页码。",
        [{**_citation(), "page_number": 4}],
    )

    assert "页码：教材第 4 页" in messages[-1]["content"]
    assert "不得声称资料没有页码" in messages[0]["content"]


def test_course_answer_repairs_false_page_availability_denial() -> None:
    model = SequentialModelSettingsService(
        [
            "当前资料没有具体页码，因此无法标明页码。",
            "根据教材第 4 页，TCP 通过确认与重传机制提高传输可靠性。",
        ]
    )
    service = CourseAnswerService(model)

    result = service.generate(
        user=object(),
        question="请解释 TCP 可靠传输并标明页码。",
        citations=[
            {
                **_citation(),
                "section_title": "TCP 可靠传输",
                "page_number": 4,
                "content": "TCP 通过确认与重传机制提高传输可靠性。",
            }
        ],
    )

    assert "教材第 4 页" in result.content
    assert "没有具体页码" not in result.content
    assert len(model.calls) == 2
    assert "课程证据带有页码" in model.calls[1][0]["content"]


def test_course_answer_stream_falls_back_when_repair_still_invents_numbers() -> None:
    model = SequentialModelSettingsService(
        [
            "主存访问需要 100 纳秒。",
            "修订后仍声称主存访问需要 80 纳秒。",
        ]
    )
    service = CourseAnswerService(model)

    content = "".join(service.stream(user=object(), question="解释主存访问。", citations=[_citation()]).tokens)

    assert "100 纳秒" not in content
    assert "80 纳秒" not in content
    assert "不足以支持刚才生成内容中的精确性能数字" in content


def test_course_answer_repairs_external_domains_missing_from_sources() -> None:
    model = SequentialModelSettingsService(
        [
            "可以访问 icourse163.org，也推荐未检索到的 example.com。",
            "可以访问本次检索到的 icourse163.org 课程。",
        ]
    )
    service = CourseAnswerService(model)
    citation = {
        **_citation(),
        "source_type": "web",
        "title": "中国大学 MOOC 课程",
        "url": "https://www.icourse163.org/course/example",
    }

    result = service.generate(user=object(), question="有哪些在线课程？", citations=[citation])

    assert "icourse163.org" in result.content
    assert "example.com" not in result.content
    assert len(model.calls) == 2


def test_course_answer_keeps_web_supplements_when_course_citations_fill_primary_limit() -> None:
    citations = [
        {
            **_citation(),
            "source_title": f"课程资料 {index}",
            "content": f"课程片段 {index}",
        }
        for index in range(5)
    ]
    citations.extend(
        [
            {
                "source_type": "web",
                "source_title": "国内算法可视化资源",
                "title": "国内算法可视化资源",
                "url": "https://example.edu.cn/visualization",
                "snippet": "提供数据结构和算法可视化演示。",
            }
        ]
    )

    messages = CourseAnswerService._build_messages("请联网核实可视化资源", citations)
    prompt = messages[-1]["content"]

    assert "课程资料 4" in prompt
    assert "国内算法可视化资源" in prompt
    assert "https://example.edu.cn/visualization" in prompt
    assert "本次没有使用外部网页" not in prompt


def test_course_answer_removes_inline_source_metadata() -> None:
    service = CourseAnswerService(FakeModelSettingsService(_inline_source_answer()))

    result = service.generate(user=object(), question="请给我排序", citations=[_citation()])

    assert "匹配度：" not in result.content
    assert "来源：" not in result.content
    assert "片段：" not in result.content
    assert "符号知识表达：知识表示关注" in result.content


def test_course_answer_and_stream_preserve_nested_python_indentation() -> None:
    code = "def pair_count(n):\n    count = 0\n    for i in range(n):\n        for j in range(i):\n            count += 1\n    return count"
    original = f"计算总执行次数：\n\n```python\n{code}\n```\n\n- 分析\n    - 求和\n匹配度：2.65"
    service = CourseAnswerService(FakeModelSettingsService(original))

    result = service.generate(user=object(), question="解释循环计数", citations=[_citation()])
    streamed = "".join(service.stream(user=object(), question="解释循环计数", citations=[_citation()]).tokens)

    for answer in (result.content, streamed):
        assert code in answer
        assert "\n    - 求和" in answer
        assert "匹配度：" not in answer
        compile(answer.split("```python\n", 1)[1].split("```", 1)[0], "answer.py", "exec")


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
    assert context.summary not in sent_messages[0]["content"]
    assert context.summary in sent_messages[-1]["content"]
    assert sent_messages[1]["content"] == "启发式搜索是什么？"
    assert sent_messages[2]["content"] == "它用启发函数估计搜索方向。"
    assert "学生问题：那这个怎么做题？" in sent_messages[3]["content"]
    assert sum(message["role"] == "system" for message in sent_messages) == 1


def test_home_answer_keeps_summary_in_current_turn_not_system_message() -> None:
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
    assert context.summary not in sent_messages[0]["content"]
    assert context.summary in sent_messages[-1]["content"]
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


def test_course_review_receives_evidence_text_for_claim_level_grounding() -> None:
    model = FakeModelSettingsService(
        '{"review_status":"revise","confidence":0.9,"risk_flags":["citation_mismatch"],'
        '"safety_summary":"来源不支持：回答增加了课程片段没有出现的历史结论。"}'
    )
    service = CourseAnswerService(model)
    citation = {
        **_citation(),
        "section_title": "近代化探索",
        "content": "辛亥革命推动政治制度发生重大转折，社会改造仍不充分。",
    }

    result = service.review_home(
        user=object(),
        question="辛亥革命的局限是什么？",
        answer="教材指出革命彻底改变了全部社会结构。",
        citations=[citation],
    )
    payload = json.loads(model.calls[0][-1]["content"])

    assert payload["sources"][0]["excerpt"] == citation["content"]
    assert result is not None
    assert result.review_status == "revise"
    assert result.risk_flags == ["citation_mismatch"]
    assert "逐条对照" in model.calls[0][0]["content"]


def test_course_review_contract_separates_source_facts_from_generated_learning_actions() -> None:
    model = FakeModelSettingsService(
        '{"review_status":"passed","confidence":0.9,"risk_flags":[],"safety_summary":"事实引用与学习行动边界清晰。"}'
    )
    service = CourseAnswerService(model)

    result = service.review_home(
        user=object(),
        question="请比较分类和回归，并制定三步复习方案；所有事实只依据资料。",
        answer=(
            "资料明确说明分类预测离散类别，回归预测连续数值。\n\n"
            "复习建议（基于当前资料生成）：第一步背诵定义，第二步做关键词映射，第三步完成自测。"
        ),
        citations=[{**_citation(), "content": "分类预测离散类别，回归预测连续数值。"}],
    )

    prompt = model.calls[0][0]["content"]
    assert result is not None
    assert result.review_status == "passed"
    assert "复习步骤、练习建议或行动计划" in prompt
    assert "不得仅因未出现在 sources 中就判定 citation_mismatch" in prompt


def test_course_review_with_no_sources_does_not_infer_course_attribution() -> None:
    model = FakeModelSettingsService(
        '{"review_status":"passed","confidence":0.8,"risk_flags":[],"safety_summary":"回答未声称课程资料依据。"}'
    )
    service = CourseAnswerService(model)

    result = service.review_home(
        user=object(),
        question="请比较决策树和神经网络，并制定复习计划。",
        answer="决策树便于解释，神经网络适合学习复杂模式。复习建议：先比较假设，再做两道练习。",
        citations=[],
    )

    payload = json.loads(model.calls[0][-1]["content"])
    prompt = model.calls[0][0]["content"]
    assert payload["sources"] == []
    assert result is not None
    assert result.risk_flags == []
    assert "当 sources 为空时" in prompt


def test_course_repair_contract_does_not_hide_facts_present_in_evidence() -> None:
    model = FakeModelSettingsService("<final_answer>资料明确说明辛亥革命的局限是社会改造仍不充分。</final_answer>")
    service = CourseAnswerService(model)

    repaired = service.repair_home(
        user=object(),
        question="严格按资料说明辛亥革命的局限。",
        draft="资料未说明。",
        citations=[{**_citation(), "content": "辛亥革命的局限是社会改造仍不充分。"}],
        risk_flags=["citation_mismatch"],
    )

    assert repaired == "资料明确说明辛亥革命的局限是社会改造仍不充分。"
    assert "不得把证据已明确写出的内容误报" in model.calls[0][0]["content"]


def test_course_repair_contract_keeps_generated_learning_actions_explicit() -> None:
    model = FakeModelSettingsService(
        "<final_answer>资料明确说明分类预测离散类别，回归预测连续数值。\n\n复习建议（基于当前资料生成）：先辨别预测目标，再做分类与回归练习。</final_answer>"
    )
    service = CourseAnswerService(model)

    repaired = service.repair_home(
        user=object(),
        question="请比较分类和回归并制定复习方案。",
        draft="分类预测离散类别，回归预测连续数值。复习建议：先辨别预测目标。",
        citations=[{**_citation(), "content": "分类预测离散类别，回归预测连续数值。"}],
        risk_flags=["citation_mismatch"],
    )

    assert repaired is not None
    assert "复习建议（基于当前资料生成）" in repaired
    assert "行动计划属于助手生成的学习行动" in model.calls[0][0]["content"]


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
