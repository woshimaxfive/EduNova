from backend.app.agents.tool_policy import decide_tool_capabilities


def test_plain_explanation_keeps_search_off_and_reasoning_adaptive() -> None:
    decision = decide_tool_capabilities("什么是二叉树？")

    assert decision.search_required is False
    assert decision.reasoning_mode == "auto"
    assert decision.reason_codes == ("default",)


def test_fresh_information_enables_search_without_forcing_deep_reasoning() -> None:
    decision = decide_tool_capabilities("帮我核实一下这个算法今年的最新应用")

    assert decision.search_required is True
    assert decision.reasoning_mode == "auto"
    assert "fresh_information" in decision.reason_codes


def test_complex_comparison_enables_deep_reasoning_without_unneeded_search() -> None:
    decision = decide_tool_capabilities("比较 AVL 树和红黑树，分析它们为什么适合不同场景")

    assert decision.search_required is False
    assert decision.reasoning_mode == "deep"
    assert "complex_reasoning" in decision.reason_codes


def test_course_evidence_fallback_requires_confirmed_course_relevance() -> None:
    unrelated = decide_tool_capabilities(
        "量子通信怎么复习？",
        has_course_evidence=False,
        course_related=False,
    )
    related = decide_tool_capabilities(
        "数据结构与算法有哪些新应用？",
        has_course_evidence=False,
        course_related=True,
    )

    assert unrelated.search_required is False
    assert related.search_required is True
    assert "course_evidence_fallback" in related.reason_codes


def test_legacy_true_flags_only_force_enable_capabilities() -> None:
    decision = decide_tool_capabilities("解释栈", force_search=True, force_deep=True)

    assert decision.search_required is True
    assert decision.reasoning_mode == "deep"
    assert decision.reason_codes[:2] == ("legacy_search", "legacy_deep")
