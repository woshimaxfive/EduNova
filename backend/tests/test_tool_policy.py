from backend.app.agents.tool_policy import decide_tool_capabilities


def test_fallback_does_not_guess_semantic_intent() -> None:
    decision = decide_tool_capabilities("推荐一些 Java 学习视频")

    assert decision.search_required is False
    assert decision.reasoning_mode == "auto"
    assert decision.reason_codes == ("semantic_router_unavailable",)
    assert decision.decision_mode == "degraded"


def test_explicit_search_command_is_a_hard_override() -> None:
    decision = decide_tool_capabilities("请核实这个算法今年的最新应用")

    assert decision.search_required is True
    assert decision.reasoning_mode == "auto"
    assert decision.reason_codes == ("explicit_search",)
    assert decision.decision_mode == "forced"


def test_fallback_does_not_infer_deep_reasoning_from_keywords() -> None:
    decision = decide_tool_capabilities("比较 AVL 树和红黑树，分析它们适合什么场景")

    assert decision.search_required is False
    assert decision.reasoning_mode == "auto"


def test_legacy_true_flags_only_force_enable_capabilities() -> None:
    decision = decide_tool_capabilities("解释栈", force_search=True, force_deep=True)

    assert decision.search_required is True
    assert decision.reasoning_mode == "deep"
    assert decision.reason_codes[:2] == ("legacy_search", "legacy_deep")
