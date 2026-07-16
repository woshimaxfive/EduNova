from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ModelReasoning = Literal["disabled", "auto", "deep"]
ModelOutputMode = Literal["text", "json_object"]
ModelCreativity = Literal["stable", "balanced", "creative"]


@dataclass(frozen=True)
class ModelTaskProfile:
    task_type: str
    reasoning: ModelReasoning = "disabled"
    output_mode: ModelOutputMode = "json_object"
    creativity: ModelCreativity = "stable"
    timeout_seconds: float = 30.0
    max_attempts: int = 1

    @property
    def temperature(self) -> float:
        return {"stable": 0.1, "balanced": 0.35, "creative": 0.55}[self.creativity]


STRUCTURED_STABLE = ModelTaskProfile(task_type="structured", creativity="stable")

