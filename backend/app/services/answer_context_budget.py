"""Whole-request text budget; domain retention policy over existing LangChain utilities.

These estimates are not provider usage, exact tokenizer counts or a billing cap.
"""
from dataclasses import dataclass
import logging
from typing import Callable

from langchain_core.messages import trim_messages
from langchain_core.messages.utils import count_tokens_approximately

from backend.app.core.config import get_settings


logger = logging.getLogger(__name__)
Messages = list[dict[str, str]]
Sections = dict[str, list[str]]


class AnswerContextBudgetError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnswerContextBudget:
    window: int = 16384
    output_reserve: int = 4096
    safety_margin: int = 512
    history: int = 3000
    memory: int = 1800
    web: int = 4000
    course: int = 8000

    def __post_init__(self):
        if min(self.window, self.output_reserve) <= 0 or min(
            self.safety_margin, self.history, self.memory, self.web, self.course
        ) < 0 or self.input_limit <= 0:
            raise ValueError("Invalid answer context budget")

    @property
    def input_limit(self) -> int:
        return self.window - self.output_reserve - self.safety_margin

    @classmethod
    def configured(cls):
        settings = get_settings()
        return cls(window=settings.tutor_context_window_tokens,
                   output_reserve=settings.tutor_output_reserve_tokens)


def estimate_messages(messages) -> int:
    # Avoid the English-oriented four-characters-per-token default for Chinese.
    # A conservative heuristic, not a guaranteed bound for arbitrary tokenizers.
    return count_tokens_approximately(messages, chars_per_token=1.0, extra_tokens_per_message=8)


def _trim_history(messages: Messages, limit: int) -> Messages:
    if estimate_messages(messages) <= limit:
        return list(messages)
    trimmed = trim_messages(messages, max_tokens=max(0, limit), token_counter=estimate_messages,
                            strategy="last", allow_partial=False, start_on="human")
    return [{"role": "user" if item.type == "human" else "assistant", "content": str(item.content)}
            for item in trimmed]


def fit_answer_context(
    history: Messages,
    sections: Sections,
    render: Callable[[Messages, Sections, bool], Messages],
    budget: AnswerContextBudget | None = None,
) -> Messages:
    """Remove whole messages/blocks, never cut source metadata away from evidence."""
    policy = budget or AnswerContextBudget.configured()
    retained = {name: list(blocks) for name, blocks in sections.items()}
    recent = _trim_history(history, policy.history)
    for name in ("memory", "web", "course"):
        minimum = 1 if name == "course" and retained[name] else 0
        while len(retained[name]) > minimum and estimate_messages([
            {"role": "user", "content": "\n\n".join(retained[name])}
        ]) > getattr(policy, name):
            retained[name].pop()

    def changed():
        return recent != history or retained != sections

    def assembled():
        return render(recent, retained, changed())

    before = estimate_messages(render(history, sections, False))
    messages = assembled()
    while estimate_messages(messages) > policy.input_limit:
        if recent:
            recent = _trim_history(recent, estimate_messages(recent) - 1)
        elif retained["memory"]:
            retained["memory"].clear()
        elif retained["web"]:
            retained["web"].pop()
        elif len(retained["course"]) > 1:
            retained["course"].pop()
        else:
            # System rules, question, resource context and one course source survive.
            # Do not send a misleading partial question or invent evidence.
            raise AnswerContextBudgetError(
                "当前问题、学习资源与必要依据超过上下文预算，请缩短问题或减少所选内容后重试。"
            )
        messages = assembled()
    if changed():
        logger.info("answer_context_budget_applied estimated_before=%s estimated_after=%s input_limit=%s "
                    "history_removed=%s memory_removed=%s web_removed=%s course_removed=%s",
                    before, estimate_messages(messages), policy.input_limit, len(history) - len(recent),
                    len(sections["memory"]) - len(retained["memory"]),
                    len(sections["web"]) - len(retained["web"]),
                    len(sections["course"]) - len(retained["course"]))
    return messages


BUDGET_NOTICE = "上下文预算提示：部分旧历史、记忆或来源已省略。只依据本次实际提供的片段回答，不推测省略内容。"
