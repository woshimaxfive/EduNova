from dataclasses import replace

import pytest

from backend.app.services.answer_context_budget import (
    AnswerContextBudget,
    AnswerContextBudgetError,
    estimate_messages,
    fit_answer_context,
)


def render(history, sections, reduced):
    return [
        {"role": "system", "content": "固定规则"},
        *history,
        {"role": "user", "content": "\n".join([
            "\n".join(sections["memory"]),
            "\n".join(sections["web"]),
            "\n".join(sections["course"]),
            "当前问题：必须保留",
            "已压缩" if reduced else "",
        ])},
    ]


def budget(**changes):
    return replace(AnswerContextBudget(
        window=200, output_reserve=20, safety_margin=10,
        history=60, memory=40, web=70, course=100,
    ), **changes)


def test_removes_old_history_before_memory_and_sources_and_keeps_question():
    history = [{"role": "user", "content": f"旧历史 {index} " + "x" * 30} for index in range(5)]
    sections = {"memory": ["记忆 " + "m" * 35], "web": ["外部 " + "w" * 35, "外部2 " + "w" * 35],
                "course": ["课程证据 " + "c" * 35, "课程证据2 " + "c" * 35]}
    result = fit_answer_context(history, sections, render, budget())
    assert estimate_messages(result) <= budget().input_limit
    assert "当前问题：必须保留" in result[-1]["content"]
    assert "课程证据" in result[-1]["content"]
    assert "旧历史 0" not in repr(result)
    assert "记忆" not in result[-1]["content"] or "外部" not in result[-1]["content"]


def test_empty_history_does_not_create_a_second_system_message():
    result = fit_answer_context([], {"memory": [], "web": [], "course": []}, render, budget())
    assert [item["role"] for item in result] == ["system", "user"]
    assert sum(item["role"] == "system" for item in result) == 1


def test_keeps_one_course_block_and_raises_when_that_block_cannot_fit():
    tiny = budget(window=80, output_reserve=20, safety_margin=10, course=100)
    with pytest.raises(AnswerContextBudgetError, match="超过上下文预算"):
        fit_answer_context([], {"memory": [], "web": [], "course": ["无法省略的课程证据 " + "c" * 200]}, render, tiny)


def test_budget_rejects_invalid_window_reserve_combination():
    with pytest.raises(ValueError):
        AnswerContextBudget(window=100, output_reserve=90, safety_margin=20)
