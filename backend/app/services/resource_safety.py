"""Resource output checks with content-free diagnostics and credential boundaries."""
from __future__ import annotations

import re
from collections.abc import Iterable


SENSITIVE_MARKERS = (
    "系统提示词", "system prompt", "模型输入", "model input", "api key",
    "sk-", "资料原文", "source text", "raw prompt",
)
_RULE_NAMES = dict(zip(SENSITIVE_MARKERS, (
    "system_prompt_zh", "system_prompt_en", "model_input_zh", "model_input_en",
    "api_key_label", "credential_prefix", "source_original_zh", "source_text_en", "raw_prompt",
), strict=True))
# ASCII identifier boundaries preserve protection next to Chinese prose while
# avoiding ordinary node names such as task-1. A bare credential prefix is blocked.
_CREDENTIAL_PREFIX = re.compile(r"(?<![a-z0-9_])sk-", re.IGNORECASE)


def sensitive_output_flags(value: str, markers: Iterable[str] = SENSITIVE_MARKERS) -> list[str]:
    lowered = value.casefold()
    return [f"sensitive_{_RULE_NAMES[marker]}" for marker in markers
            if (_CREDENTIAL_PREFIX.search(value) if marker == "sk-" else marker in lowered)]
